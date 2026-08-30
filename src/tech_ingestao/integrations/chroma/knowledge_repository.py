"""Implementação ChromaDB do repositório vetorial."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol, cast

import chromadb

from tech_ingestao.config.settings import ChromaSettings
from tech_ingestao.errors import KnowledgeStoreError
from tech_ingestao.models.knowledge import (
    KnowledgeDocument,
    KnowledgeSearchResult,
    MetadataValue,
)


class _ChromaCollection(Protocol):
    def upsert(
        self,
        *,
        ids: Sequence[str],
        embeddings: Sequence[Sequence[float]],
        metadatas: Sequence[Mapping[str, MetadataValue]],
        documents: Sequence[str],
    ) -> None: ...

    def query(
        self,
        *,
        query_embeddings: Sequence[Sequence[float]],
        n_results: int,
        include: Sequence[str],
    ) -> Mapping[str, object]: ...

    def count(self) -> int: ...


def _first_batch(result: Mapping[str, object], key: str) -> list[object]:
    value = result.get(key)
    if not isinstance(value, list) or not value or not isinstance(value[0], list):
        raise KnowledgeStoreError(f"Resposta inválida do ChromaDB no campo {key}.")
    return cast(list[object], value[0])


def _metadata_value(value: object) -> MetadataValue | None:
    if isinstance(value, (str, int, float, bool)):
        return value
    return None


def _normalize_metadata(value: object) -> dict[str, MetadataValue]:
    if not isinstance(value, dict):
        raise KnowledgeStoreError("Resposta inválida do ChromaDB no campo metadatas.")
    normalized: dict[str, MetadataValue] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            continue
        metadata_value = _metadata_value(item)
        if metadata_value is not None:
            normalized[key] = metadata_value
    return normalized


class ChromaKnowledgeRepository:
    """Usa embeddings prontos para não acoplar o ChromaDB à OpenAI."""

    def __init__(
        self,
        settings: ChromaSettings,
        *,
        collection: _ChromaCollection | None = None,
    ) -> None:
        if collection is not None:
            self._collection = collection
            return
        try:
            client = chromadb.HttpClient(
                host=settings.host,
                port=settings.port,
                ssl=settings.ssl,
            )
            chroma_collection = client.get_or_create_collection(
                name=settings.collection,
                embedding_function=None,
                configuration={"hnsw": {"space": "cosine"}},
            )
        except Exception as error:
            raise KnowledgeStoreError("Não foi possível conectar ao ChromaDB.") from error
        self._collection = cast(_ChromaCollection, chroma_collection)

    def upsert(
        self,
        documents: Sequence[KnowledgeDocument],
        embeddings: Sequence[Sequence[float]],
    ) -> None:
        if len(documents) != len(embeddings):
            raise KnowledgeStoreError("Documentos e embeddings devem ter o mesmo tamanho.")
        if not documents:
            return
        try:
            self._collection.upsert(
                ids=[document.record_id for document in documents],
                embeddings=[list(embedding) for embedding in embeddings],
                metadatas=[document.metadata for document in documents],
                documents=[document.text for document in documents],
            )
        except Exception as error:
            raise KnowledgeStoreError("O lote não pôde ser gravado no ChromaDB.") from error

    def query(
        self,
        embedding: Sequence[float],
        *,
        limit: int,
    ) -> tuple[KnowledgeSearchResult, ...]:
        try:
            result = self._collection.query(
                query_embeddings=[list(embedding)],
                n_results=limit,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as error:
            raise KnowledgeStoreError("A consulta ao ChromaDB falhou.") from error

        ids = _first_batch(result, "ids")
        documents = _first_batch(result, "documents")
        metadatas = _first_batch(result, "metadatas")
        distances = _first_batch(result, "distances")
        if not (len(ids) == len(documents) == len(metadatas) == len(distances)):
            raise KnowledgeStoreError("O ChromaDB retornou colunas com tamanhos diferentes.")

        normalized: list[KnowledgeSearchResult] = []
        for record_id, document, metadata, distance in zip(
            ids,
            documents,
            metadatas,
            distances,
            strict=True,
        ):
            if not isinstance(record_id, str) or not isinstance(document, str):
                raise KnowledgeStoreError("O ChromaDB retornou um registro sem texto ou ID.")
            if not isinstance(distance, (int, float)):
                raise KnowledgeStoreError("O ChromaDB retornou uma distância inválida.")
            normalized.append(
                KnowledgeSearchResult(
                    record_id=record_id,
                    text=document,
                    metadata=_normalize_metadata(metadata),
                    distance=float(distance),
                )
            )
        return tuple(normalized)

    def count(self) -> int:
        try:
            return self._collection.count()
        except Exception as error:
            message = "Não foi possível contar os registros no ChromaDB."
            raise KnowledgeStoreError(message) from error
