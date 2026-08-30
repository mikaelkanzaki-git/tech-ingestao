"""Modelos produzidos pela preparação do dataset."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tech_ingestao.models.canonical import CanonicalMedicalRecord, PiiType


@dataclass(frozen=True, slots=True)
class DuplicateRemoval:
    """Rastreia qual registro foi removido e qual registro equivalente permaneceu."""

    content_sha256: str
    kept_record_id: str
    kept_document_id: str
    dropped_record_id: str
    dropped_document_id: str

    def as_dict(self) -> dict[str, str]:
        return {
            "content_sha256": self.content_sha256,
            "kept_record_id": self.kept_record_id,
            "kept_document_id": self.kept_document_id,
            "dropped_record_id": self.dropped_record_id,
            "dropped_document_id": self.dropped_document_id,
        }


@dataclass(frozen=True, slots=True)
class PiiAuditFinding:
    """Evidência de redação que nunca armazena o identificador encontrado."""

    record_id: str
    document_id: str
    source_relative_path: str
    upstream_pair_id: str | None
    detected_types: tuple[PiiType, ...]

    def as_dict(self) -> dict[str, str | list[str] | None]:
        return {
            "record_id": self.record_id,
            "document_id": self.document_id,
            "source_relative_path": self.source_relative_path,
            "upstream_pair_id": self.upstream_pair_id,
            "detected_types": list(self.detected_types),
            "action": "redacted",
        }


@dataclass(frozen=True, slots=True)
class PreparedDataset:
    """Registros curados, divisões e evidências de integridade."""

    canonical_records: tuple[CanonicalMedicalRecord, ...]
    train_records: tuple[CanonicalMedicalRecord, ...]
    validation_records: tuple[CanonicalMedicalRecord, ...]
    test_records: tuple[CanonicalMedicalRecord, ...]
    duplicate_removals: tuple[DuplicateRemoval, ...]
    pii_findings: tuple[PiiAuditFinding, ...]
    manifest: dict[str, Any]
