from __future__ import annotations

from collections.abc import Sequence

import pytest

from tech_ingestao.config.settings import LocalEmbeddingSettings
from tech_ingestao.errors import EmbeddingError
from tech_ingestao.integrations.embeddings.local_onnx import LocalOnnxEmbeddingClient


class FakeEmbeddingFunction:
    def __init__(
        self,
        embeddings: Sequence[Sequence[float]] = (),
        *,
        fail: bool = False,
    ) -> None:
        self.embeddings = embeddings
        self.fail = fail
        self.received: list[str] = []

    def __call__(self, input: list[str]) -> Sequence[Sequence[float]]:
        self.received = input
        if self.fail:
            raise RuntimeError("internal detail")
        return self.embeddings


def test_local_embedding_client_normalizes_vectors() -> None:
    function = FakeEmbeddingFunction(((1, 2), (3, 4)))
    client = LocalOnnxEmbeddingClient(
        LocalEmbeddingSettings(dimensions=2),
        embedding_function=function,
    )

    result = client.embed(["first", "second"])

    assert result == ((1.0, 2.0), (3.0, 4.0))
    assert function.received == ["first", "second"]


def test_local_embedding_client_handles_empty_input_and_rejects_empty_text() -> None:
    function = FakeEmbeddingFunction()
    client = LocalOnnxEmbeddingClient(
        LocalEmbeddingSettings(dimensions=2),
        embedding_function=function,
    )

    assert client.embed([]) == ()
    with pytest.raises(EmbeddingError, match="textos vazios"):
        client.embed([" "])


def test_local_embedding_client_hides_runtime_failure() -> None:
    client = LocalOnnxEmbeddingClient(
        LocalEmbeddingSettings(dimensions=2),
        embedding_function=FakeEmbeddingFunction(fail=True),
    )

    with pytest.raises(EmbeddingError, match="localmente") as raised:
        client.embed(["question"])
    assert "internal detail" not in str(raised.value)


@pytest.mark.parametrize(
    "embeddings",
    [
        ((1.0, 2.0),),
        ((1.0,), (2.0,)),
    ],
)
def test_local_embedding_client_rejects_inconsistent_shape(
    embeddings: Sequence[Sequence[float]],
) -> None:
    client = LocalOnnxEmbeddingClient(
        LocalEmbeddingSettings(dimensions=2),
        embedding_function=FakeEmbeddingFunction(embeddings),
    )

    with pytest.raises(EmbeddingError, match=r"quantidade|dimensão"):
        client.embed(["first", "second"])
