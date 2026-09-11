from __future__ import annotations

from collections.abc import Mapping, Sequence

import chromadb
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


class FakeClient:
    def __init__(self, collection: FakeCollection) -> None:
        self.collection = collection
        self.collection_arguments: dict[str, object] = {}

    def get_or_create_collection(
        self,
        *,
        name: str,
        embedding_function: object,
        configuration: Mapping[str, object],
    ) -> FakeCollection:
        self.collection_arguments = {
            "name": name,
            "embedding_function": embedding_function,
            "configuration": configuration,
        }
        return self.collection


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


def test_chroma_repository_uses_http_client_in_local_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []
    client = FakeClient(FakeCollection())

    def fake_http_client(*, host: str, port: int, ssl: bool) -> FakeClient:
        calls.append({"host": host, "port": port, "ssl": ssl})
        return client

    monkeypatch.setattr(chromadb, "HttpClient", fake_http_client)

    ChromaKnowledgeRepository(
        ChromaSettings(host="chroma.internal", port=9000, ssl=True)
    )

    assert calls == [{"host": "chroma.internal", "port": 9000, "ssl": True}]
    assert client.collection_arguments["name"] == "medquad_knowledge_minilm_v1"


def test_chroma_repository_uses_cloud_client_in_cloud_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []
    client = FakeClient(FakeCollection())

    def fake_cloud_client(
        *,
        tenant: str | None,
        database: str | None,
        api_key: str | None,
        cloud_host: str,
        cloud_port: int,
        enable_ssl: bool,
    ) -> FakeClient:
        calls.append(
            {
                "tenant": tenant,
                "database": database,
                "api_key": api_key,
                "cloud_host": cloud_host,
                "cloud_port": cloud_port,
                "enable_ssl": enable_ssl,
            }
        )
        return client

    monkeypatch.setattr(chromadb, "CloudClient", fake_cloud_client)

    ChromaKnowledgeRepository(
        ChromaSettings(
            mode="cloud",
            host="api.trychroma.com",
            port=443,
            ssl=True,
            api_key="api-key",
            tenant="tenant-id",
            database="medical-database",
        )
    )

    assert calls == [
        {
            "tenant": "tenant-id",
            "database": "medical-database",
            "api_key": "api-key",
            "cloud_host": "api.trychroma.com",
            "cloud_port": 443,
            "enable_ssl": True,
        }
    ]
    assert client.collection_arguments == {
        "name": "medquad_knowledge_minilm_v1",
        "embedding_function": None,
        "configuration": {"hnsw": {"space": "cosine"}},
    }


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
