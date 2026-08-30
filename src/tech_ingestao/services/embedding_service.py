"""Contrato de geração de vetores consumido pela indexação e pela busca."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol


class EmbeddingService(Protocol):
    """Gera embeddings preservando a ordem das entradas."""

    def embed(self, texts: Sequence[str]) -> tuple[tuple[float, ...], ...]: ...
