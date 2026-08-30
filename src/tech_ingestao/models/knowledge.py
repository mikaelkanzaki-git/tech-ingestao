"""Modelos independentes do provedor de embeddings e do banco vetorial."""

from __future__ import annotations

from dataclasses import dataclass

MetadataValue = str | int | float | bool


@dataclass(frozen=True, slots=True)
class KnowledgeDocument:
    """Documento pronto para receber um embedding e ser indexado."""

    record_id: str
    text: str
    metadata: dict[str, MetadataValue]


@dataclass(frozen=True, slots=True)
class KnowledgeSearchResult:
    """Resultado normalizado de uma consulta semântica."""

    record_id: str
    text: str
    metadata: dict[str, MetadataValue]
    distance: float

    def as_dict(self) -> dict[str, object]:
        return {
            "record_id": self.record_id,
            "text": self.text,
            "metadata": self.metadata,
            "distance": self.distance,
        }


@dataclass(frozen=True, slots=True)
class KnowledgeIndexSummary:
    """Evidência da execução idempotente dos lotes."""

    indexed_records: int
    batches: int
    collection_records: int

    def as_dict(self) -> dict[str, int]:
        return {
            "indexed_records": self.indexed_records,
            "batches": self.batches,
            "collection_records": self.collection_records,
        }
