from __future__ import annotations

from types import SimpleNamespace
from typing import cast
from unittest.mock import MagicMock

import pytest
from openai import OpenAI

from tech_ingestao.config.settings import OpenAIEmbeddingSettings
from tech_ingestao.errors import EmbeddingError
from tech_ingestao.integrations.embeddings.openai import OpenAIEmbeddingService


def _settings(dimensions: int = 2) -> OpenAIEmbeddingSettings:
    return OpenAIEmbeddingSettings(
        api_key="test-key",
        model="text-embedding-3-small",
        dimensions=dimensions,
    )


def test_embedding_service_preserves_response_index_order() -> None:
    client = MagicMock()
    client.embeddings.create.return_value = SimpleNamespace(
        data=[
            SimpleNamespace(index=1, embedding=[0.3, 0.4]),
            SimpleNamespace(index=0, embedding=[0.1, 0.2]),
        ]
    )
    service = OpenAIEmbeddingService(_settings(), client=cast(OpenAI, client))

    embeddings = service.embed(["first", "second"])

    assert embeddings == ((0.1, 0.2), (0.3, 0.4))
    client.embeddings.create.assert_called_once_with(
        input=["first", "second"],
        model="text-embedding-3-small",
        dimensions=2,
        encoding_format="float",
    )


def test_embedding_service_handles_empty_input_without_api_call() -> None:
    client = MagicMock()
    service = OpenAIEmbeddingService(_settings(), client=cast(OpenAI, client))

    assert service.embed([]) == ()
    client.embeddings.create.assert_not_called()


def test_embedding_service_rejects_empty_text() -> None:
    client = MagicMock()
    service = OpenAIEmbeddingService(_settings(), client=cast(OpenAI, client))

    with pytest.raises(EmbeddingError, match="textos vazios"):
        service.embed([" "])


def test_embedding_service_normalizes_sdk_failure() -> None:
    client = MagicMock()
    client.embeddings.create.side_effect = RuntimeError("credential leaked by SDK")
    service = OpenAIEmbeddingService(_settings(), client=cast(OpenAI, client))

    with pytest.raises(EmbeddingError, match="Não foi possível") as raised:
        service.embed(["question"])

    assert "credential leaked" not in str(raised.value)


@pytest.mark.parametrize(
    "data",
    [
        [SimpleNamespace(index=0, embedding=[0.1, 0.2])],
        [
            SimpleNamespace(index=0, embedding=[0.1]),
            SimpleNamespace(index=1, embedding=[0.2]),
        ],
    ],
)
def test_embedding_service_validates_response_shape(data: list[SimpleNamespace]) -> None:
    client = MagicMock()
    client.embeddings.create.return_value = SimpleNamespace(data=data)
    service = OpenAIEmbeddingService(_settings(), client=cast(OpenAI, client))

    with pytest.raises(EmbeddingError, match=r"quantidade|dimensão"):
        service.embed(["first", "second"])
