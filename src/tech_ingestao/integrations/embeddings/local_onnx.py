"""Embeddings locais usando o modelo ONNX incluído pelo ChromaDB."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, cast

from tech_ingestao.config.settings import LocalEmbeddingSettings
from tech_ingestao.errors import EmbeddingError


class _EmbeddingFunction(Protocol):
    def __call__(self, input: list[str]) -> Sequence[Sequence[float]]: ...


class LocalOnnxEmbeddingClient:
    """Executa all-MiniLM-L6-v2 localmente, sem chave ou API externa."""

    def __init__(
        self,
        settings: LocalEmbeddingSettings,
        *,
        embedding_function: _EmbeddingFunction | None = None,
    ) -> None:
        self._settings = settings
        if embedding_function is None:
            from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2

            self._embedding_function = cast(_EmbeddingFunction, ONNXMiniLM_L6_V2())
        else:
            self._embedding_function = embedding_function

    def embed(self, texts: Sequence[str]) -> tuple[tuple[float, ...], ...]:
        if not texts:
            return ()
        if any(not text.strip() for text in texts):
            raise EmbeddingError("O modelo local não aceita textos vazios.")
        try:
            raw_embeddings = self._embedding_function(input=list(texts))
            embeddings = tuple(
                tuple(float(value) for value in embedding)
                for embedding in raw_embeddings
            )
        except Exception as error:
            raise EmbeddingError("Não foi possível gerar embeddings localmente.") from error
        if len(embeddings) != len(texts):
            raise EmbeddingError("O modelo local retornou uma quantidade inesperada de vetores.")
        if any(len(embedding) != self._settings.dimensions for embedding in embeddings):
            raise EmbeddingError("O modelo local retornou embeddings com dimensão inesperada.")
        return embeddings
