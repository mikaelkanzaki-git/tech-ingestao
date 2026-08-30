"""Geração explícita de embeddings pela API da OpenAI."""

from __future__ import annotations

from collections.abc import Sequence

from openai import OpenAI

from tech_ingestao.config.settings import OpenAIEmbeddingSettings
from tech_ingestao.errors import EmbeddingError


class OpenAIEmbeddingService:
    """Cliente pequeno para preservar a ordem e esconder detalhes do SDK."""

    def __init__(
        self,
        settings: OpenAIEmbeddingSettings,
        *,
        client: OpenAI | None = None,
    ) -> None:
        self._settings = settings
        self._client = client or OpenAI(api_key=settings.api_key)

    def embed(self, texts: Sequence[str]) -> tuple[tuple[float, ...], ...]:
        if not texts:
            return ()
        if any(not text.strip() for text in texts):
            raise EmbeddingError("A API de embeddings não aceita textos vazios.")

        try:
            response = self._client.embeddings.create(
                input=list(texts),
                model=self._settings.model,
                dimensions=self._settings.dimensions,
                encoding_format="float",
            )
        except Exception as error:
            raise EmbeddingError("Não foi possível gerar embeddings pela OpenAI.") from error

        ordered = sorted(response.data, key=lambda item: item.index)
        embeddings = tuple(tuple(item.embedding) for item in ordered)
        if len(embeddings) != len(texts):
            raise EmbeddingError("A OpenAI retornou uma quantidade inesperada de embeddings.")
        if any(len(embedding) != self._settings.dimensions for embedding in embeddings):
            raise EmbeddingError("A OpenAI retornou embeddings com dimensão inesperada.")
        return embeddings
