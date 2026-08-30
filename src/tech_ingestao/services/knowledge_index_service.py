"""Formatação, indexação em lotes e consulta da base de conhecimento."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from tech_ingestao.errors import KnowledgeIndexError
from tech_ingestao.models.canonical import CanonicalMedicalRecord
from tech_ingestao.models.knowledge import (
    KnowledgeDocument,
    KnowledgeIndexSummary,
    KnowledgeSearchResult,
    MetadataValue,
)
from tech_ingestao.repositories.knowledge_repository import KnowledgeRepository
from tech_ingestao.services.embedding_service import EmbeddingService


def _metadata(record: CanonicalMedicalRecord, split: str) -> dict[str, MetadataValue]:
    source = record.source
    values: dict[str, MetadataValue | None] = {
        "schema_version": record.schema_version,
        "document_id": record.document_id,
        "content_sha256": record.content_sha256,
        "language": record.language,
        "focus": record.focus,
        "category": record.category,
        "question_type": record.question_type,
        "dataset": source.dataset,
        "collection": source.collection,
        "relative_path": source.relative_path,
        "upstream_revision": source.upstream_revision,
        "publisher": source.publisher,
        "source_url": source.url,
        "license": source.license,
        "split": split,
    }
    return {key: value for key, value in values.items() if value is not None}


def build_knowledge_document(record: CanonicalMedicalRecord, *, split: str) -> KnowledgeDocument:
    """Converte o registro canônico sem carregar estruturas aninhadas no ChromaDB."""

    sections = []
    if record.focus:
        sections.append(f"Medical topic: {record.focus}")
    sections.extend((f"Question: {record.question}", f"Answer: {record.answer}"))
    return KnowledgeDocument(
        record_id=record.record_id,
        text="\n".join(sections),
        metadata=_metadata(record, split),
    )


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
        embedding_service: EmbeddingService,
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

        documents = tuple(build_knowledge_document(record, split=split) for record in records)
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
            indexed_records=len(documents),
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
