"""Contrato do gerador de embeddings usado pelos casos de uso."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol


class EmbeddingClient(Protocol):
    """Gera vetores sem expor ONNX ou ChromaDB à camada de serviços."""

    def embed(self, texts: Sequence[str]) -> tuple[tuple[float, ...], ...]: ...
