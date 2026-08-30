"""Contrato do armazenamento da base de conhecimento."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from tech_ingestao.models.knowledge import KnowledgeDocument, KnowledgeSearchResult


class KnowledgeRepository(Protocol):
    """Operações vetoriais necessárias sem expor o SDK escolhido."""

    def upsert(
        self,
        documents: Sequence[KnowledgeDocument],
        embeddings: Sequence[Sequence[float]],
    ) -> None: ...

    def query(
        self,
        embedding: Sequence[float],
        *,
        limit: int,
    ) -> tuple[KnowledgeSearchResult, ...]: ...

    def count(self) -> int: ...
