"""Formatação, indexação em lotes e consulta da base de conhecimento."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import TYPE_CHECKING

from tech_ingestao.errors import KnowledgeIndexError
from tech_ingestao.integrations.embeddings.client import EmbeddingClient
from tech_ingestao.models.knowledge import (
    KnowledgeIndexSummary,
    KnowledgeSearchResult,
)
from tech_ingestao.repositories.knowledge_repository import KnowledgeRepository
from tech_ingestao.services.knowledge_chunking_service import build_knowledge_documents

if TYPE_CHECKING:
    from tech_ingestao.models.canonical import CanonicalMedicalRecord
    from tech_ingestao.models.knowledge import KnowledgeDocument


def _batches(
    values: Sequence[KnowledgeDocument],
    batch_size: int,
) -> Iterable[Sequence[KnowledgeDocument]]:
    for start in range(0, len(values), batch_size):
        yield values[start : start + batch_size]


class KnowledgeIndexService:
    """Coordena embeddings externos e upserts idempotentes no repositório."""

    def __init__(
        self,
        embedding_service: EmbeddingClient,
        repository: KnowledgeRepository,
    ) -> None:
        self._embedding_service = embedding_service
        self._repository = repository

    def index(
        self,
        records: Sequence[CanonicalMedicalRecord],
        *,
        split: str,
        batch_size: int = 100,
    ) -> KnowledgeIndexSummary:
        if batch_size <= 0:
            raise KnowledgeIndexError("batch_size deve ser maior que zero.")

        try:
            documents_by_record = tuple(
                build_knowledge_documents(record, split=split) for record in records
            )
        except ValueError as error:
            raise KnowledgeIndexError(
                "Um registro não pôde ser dividido nos limites seguros de indexação."
            ) from error
        documents = tuple(
            document for record_documents in documents_by_record for document in record_documents
        )
        batch_count = 0
        for batch in _batches(documents, batch_size):
            embeddings = self._embedding_service.embed([document.text for document in batch])
            if len(embeddings) != len(batch):
                raise KnowledgeIndexError(
                    "O provedor retornou uma quantidade de embeddings diferente do lote."
                )
            self._repository.upsert(batch, embeddings)
            batch_count += 1

        return KnowledgeIndexSummary(
            indexed_records=len(records),
            indexed_documents=len(documents),
            chunked_records=sum(
                len(record_documents) > 1 for record_documents in documents_by_record
            ),
            batches=batch_count,
            collection_records=self._repository.count(),
        )

    def search(self, query: str, *, limit: int = 5) -> tuple[KnowledgeSearchResult, ...]:
        normalized_query = query.strip()
        if not normalized_query:
            raise KnowledgeIndexError("A consulta semântica não pode ser vazia.")
        if limit <= 0:
            raise KnowledgeIndexError("limit deve ser maior que zero.")

        embeddings = self._embedding_service.embed([normalized_query])
        if len(embeddings) != 1:
            raise KnowledgeIndexError("O provedor não retornou o embedding da consulta.")
        return self._repository.query(embeddings[0], limit=limit)
