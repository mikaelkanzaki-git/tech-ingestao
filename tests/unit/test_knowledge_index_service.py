from __future__ import annotations

from collections.abc import Sequence

import pytest

from tech_ingestao.errors import KnowledgeIndexError
from tech_ingestao.models.canonical import CanonicalMedicalRecord, CanonicalSource
from tech_ingestao.models.knowledge import KnowledgeDocument, KnowledgeSearchResult
from tech_ingestao.services.knowledge_index_service import (
    KnowledgeIndexService,
    build_knowledge_document,
)


def _record(index: int = 1, *, focus: str | None = "Diabetes") -> CanonicalMedicalRecord:
    return CanonicalMedicalRecord(
        record_id=f"record-{index}",
        document_id=f"document-{index}",
        content_sha256=f"hash-{index}",
        language="en",
        focus=focus,
        category=None,
        question_type="symptoms",
        question=f"Question {index}?",
        answer=f"Answer {index}.",
        synonyms=(),
        umls_cuis=(),
        umls_semantic_types=(),
        umls_semantic_groups=(),
        source=CanonicalSource(
            dataset="MedQuAD",
            collection="collection",
            relative_path=f"collection/{index}.xml",
            upstream_repository="https://example.test/MedQuAD.git",
            upstream_revision="abc123",
            upstream_document_id=str(index),
            upstream_pair_id="1",
            upstream_question_id=f"{index}-1",
            publisher="NIH",
            url="https://example.test/source",
            license="CC-BY-4.0",
        ),
    )


class FakeEmbeddingService:
    def __init__(self, *, drop_last: bool = False) -> None:
        self.calls: list[list[str]] = []
        self.drop_last = drop_last

    def embed(self, texts: Sequence[str]) -> tuple[tuple[float, ...], ...]:
        self.calls.append(list(texts))
        embeddings = tuple((float(index), 1.0) for index, _ in enumerate(texts))
        return embeddings[:-1] if self.drop_last else embeddings


class FakeKnowledgeRepository:
    def __init__(self) -> None:
        self.upserts: list[tuple[list[KnowledgeDocument], list[Sequence[float]]]] = []

    def upsert(
        self,
        documents: Sequence[KnowledgeDocument],
        embeddings: Sequence[Sequence[float]],
    ) -> None:
        self.upserts.append((list(documents), list(embeddings)))

    def query(
        self,
        embedding: Sequence[float],
        *,
        limit: int,
    ) -> tuple[KnowledgeSearchResult, ...]:
        return (
            KnowledgeSearchResult(
                record_id="result",
                text="Answer",
                metadata={"limit": limit, "first_dimension": embedding[0]},
                distance=0.1,
            ),
        )

    def count(self) -> int:
        return sum(len(documents) for documents, _ in self.upserts)


def test_build_knowledge_document_flattens_metadata_and_formats_text() -> None:
    document = build_knowledge_document(_record(), split="train")

    assert document.record_id == "record-1"
    assert document.text == "Medical topic: Diabetes\nQuestion: Question 1?\nAnswer: Answer 1."
    assert document.metadata["source_url"] == "https://example.test/source"
    assert document.metadata["split"] == "train"
    assert "category" not in document.metadata
    assert all(not isinstance(value, (dict, list)) for value in document.metadata.values())


def test_build_knowledge_document_omits_missing_focus_section() -> None:
    document = build_knowledge_document(_record(focus=None), split="test")

    assert document.text.startswith("Question:")


def test_index_batches_records_and_returns_collection_count() -> None:
    embeddings = FakeEmbeddingService()
    repository = FakeKnowledgeRepository()
    service = KnowledgeIndexService(embeddings, repository)

    summary = service.index([_record(1), _record(2), _record(3)], split="train", batch_size=2)

    assert summary.as_dict() == {
        "indexed_records": 3,
        "batches": 2,
        "collection_records": 3,
    }
    assert [len(batch) for batch, _ in repository.upserts] == [2, 1]
    assert [len(call) for call in embeddings.calls] == [2, 1]


def test_index_rejects_invalid_batch_and_mismatched_embeddings() -> None:
    repository = FakeKnowledgeRepository()
    service = KnowledgeIndexService(FakeEmbeddingService(), repository)
    with pytest.raises(KnowledgeIndexError, match="batch_size"):
        service.index([_record()], split="train", batch_size=0)

    mismatched = KnowledgeIndexService(FakeEmbeddingService(drop_last=True), repository)
    with pytest.raises(KnowledgeIndexError, match="quantidade"):
        mismatched.index([_record()], split="train")


def test_search_embeds_query_and_returns_repository_result() -> None:
    embeddings = FakeEmbeddingService()
    service = KnowledgeIndexService(embeddings, FakeKnowledgeRepository())

    results = service.search("  diabetes symptoms  ", limit=3)

    assert results[0].metadata["limit"] == 3
    assert embeddings.calls == [["diabetes symptoms"]]


@pytest.mark.parametrize(("query", "limit"), [(" ", 5), ("query", 0)])
def test_search_rejects_invalid_input(query: str, limit: int) -> None:
    service = KnowledgeIndexService(FakeEmbeddingService(), FakeKnowledgeRepository())

    with pytest.raises(KnowledgeIndexError):
        service.search(query, limit=limit)


def test_search_requires_exactly_one_embedding() -> None:
    service = KnowledgeIndexService(
        FakeEmbeddingService(drop_last=True),
        FakeKnowledgeRepository(),
    )

    with pytest.raises(KnowledgeIndexError, match="embedding da consulta"):
        service.search("question")
