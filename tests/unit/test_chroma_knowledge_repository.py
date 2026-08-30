from __future__ import annotations

from collections.abc import Mapping, Sequence

import pytest

from tech_ingestao.config.settings import ChromaSettings
from tech_ingestao.errors import KnowledgeStoreError
from tech_ingestao.integrations.chroma.knowledge_repository import ChromaKnowledgeRepository
from tech_ingestao.models.knowledge import KnowledgeDocument, MetadataValue


class FakeCollection:
    def __init__(self) -> None:
        self.upserted_ids: list[str] = []
        self.upserted_embeddings: Sequence[Sequence[float]] = []
        self.query_result: Mapping[str, object] = {
            "ids": [["record-1"]],
            "documents": [["Question: Q\nAnswer: A"]],
            "metadatas": [[{"publisher": "NIH", "ignored": None}]],
            "distances": [[0.25]],
        }
        self.failure: Exception | None = None

    def upsert(
        self,
        *,
        ids: Sequence[str],
        embeddings: Sequence[Sequence[float]],
        metadatas: Sequence[Mapping[str, MetadataValue]],
        documents: Sequence[str],
    ) -> None:
        if self.failure:
            raise self.failure
        assert len(ids) == len(embeddings) == len(metadatas) == len(documents)
        self.upserted_ids.extend(ids)
        self.upserted_embeddings = embeddings

    def query(
        self,
        *,
        query_embeddings: Sequence[Sequence[float]],
        n_results: int,
        include: Sequence[str],
    ) -> Mapping[str, object]:
        if self.failure:
            raise self.failure
        assert query_embeddings == [[0.1, 0.2]]
        assert n_results == 2
        assert include == ["documents", "metadatas", "distances"]
        return self.query_result

    def count(self) -> int:
        if self.failure:
            raise self.failure
        return len(self.upserted_ids)


def _document() -> KnowledgeDocument:
    return KnowledgeDocument(
        record_id="record-1",
        text="Question: Q\nAnswer: A",
        metadata={"publisher": "NIH"},
    )


def test_chroma_repository_upserts_queries_and_counts() -> None:
    collection = FakeCollection()
    repository = ChromaKnowledgeRepository(ChromaSettings(), collection=collection)

    repository.upsert([_document()], ((0.1, 0.2),))
    results = repository.query((0.1, 0.2), limit=2)

    assert collection.upserted_ids == ["record-1"]
    assert collection.upserted_embeddings == [[0.1, 0.2]]
    assert repository.count() == 1
    assert results[0].record_id == "record-1"
    assert results[0].metadata == {"publisher": "NIH"}
    assert results[0].distance == 0.25


def test_chroma_repository_ignores_empty_upsert_and_rejects_mismatch() -> None:
    collection = FakeCollection()
    repository = ChromaKnowledgeRepository(ChromaSettings(), collection=collection)

    repository.upsert([], [])
    assert collection.upserted_ids == []
    with pytest.raises(KnowledgeStoreError, match="mesmo tamanho"):
        repository.upsert([_document()], [])


@pytest.mark.parametrize("operation", ["upsert", "query", "count"])
def test_chroma_repository_normalizes_collection_failures(operation: str) -> None:
    collection = FakeCollection()
    collection.failure = RuntimeError("server details")
    repository = ChromaKnowledgeRepository(ChromaSettings(), collection=collection)

    with pytest.raises(KnowledgeStoreError) as raised:
        if operation == "upsert":
            repository.upsert([_document()], [[0.1, 0.2]])
        elif operation == "query":
            repository.query([0.1, 0.2], limit=2)
        else:
            repository.count()

    assert "server details" not in str(raised.value)


@pytest.mark.parametrize(
    "result",
    [
        {},
        {
            "ids": [["record-1"]],
            "documents": [[]],
            "metadatas": [[{}]],
            "distances": [[0.1]],
        },
        {
            "ids": [[1]],
            "documents": [["text"]],
            "metadatas": [[{}]],
            "distances": [[0.1]],
        },
        {
            "ids": [["record-1"]],
            "documents": [["text"]],
            "metadatas": [["invalid"]],
            "distances": [[0.1]],
        },
        {
            "ids": [["record-1"]],
            "documents": [["text"]],
            "metadatas": [[{}]],
            "distances": [["near"]],
        },
    ],
)
def test_chroma_repository_rejects_invalid_query_payload(result: Mapping[str, object]) -> None:
    collection = FakeCollection()
    collection.query_result = result
    repository = ChromaKnowledgeRepository(ChromaSettings(), collection=collection)

    with pytest.raises(KnowledgeStoreError, match=r"inválid|diferentes|sem texto"):
        repository.query([0.1, 0.2], limit=2)
