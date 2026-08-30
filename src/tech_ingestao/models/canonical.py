"""Schema canônico independente de MedQuAD, banco vetorial ou provedor de LLM."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

CANONICAL_SCHEMA_VERSION = "1.1"

PiiType = Literal[
    "email_address",
    "phone_number",
    "us_ssn",
    "brazilian_cpf",
    "medical_record_number",
    "patient_name",
    "date_of_birth",
]


@dataclass(frozen=True, slots=True)
class CanonicalSource:
    """Procedência necessária para atribuição, auditoria e explainability."""

    dataset: str
    collection: str
    relative_path: str
    upstream_repository: str | None
    upstream_revision: str | None
    upstream_document_id: str | None
    upstream_pair_id: str | None
    upstream_question_id: str | None
    publisher: str | None
    url: str | None
    license: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "dataset": self.dataset,
            "collection": self.collection,
            "relative_path": self.relative_path,
            "upstream_repository": self.upstream_repository,
            "upstream_revision": self.upstream_revision,
            "upstream_document_id": self.upstream_document_id,
            "upstream_pair_id": self.upstream_pair_id,
            "upstream_question_id": self.upstream_question_id,
            "publisher": self.publisher,
            "url": self.url,
            "license": self.license,
        }


@dataclass(frozen=True, slots=True)
class CurationMetadata:
    """Estado explícito da curadoria e da verificação de identificadores pessoais."""

    status: Literal["accepted"] = "accepted"
    pii_status: Literal["not_evaluated", "not_detected", "detected", "redacted"] = (
        "not_evaluated"
    )
    pii_types: tuple[PiiType, ...] = ()
    transformations: tuple[str, ...] = ("whitespace_normalized",)
    quality_flags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.pii_status == "redacted" and not self.pii_types:
            raise ValueError("O status redacted requer ao menos um tipo de PII.")
        if self.pii_status == "not_detected" and self.pii_types:
            raise ValueError("O status not_detected não aceita tipos de PII.")

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "pii_status": self.pii_status,
            "pii_types": list(self.pii_types),
            "transformations": list(self.transformations),
            "quality_flags": list(self.quality_flags),
        }


@dataclass(frozen=True, slots=True)
class CanonicalMedicalRecord:
    """Um par médico aceito, rastreável até seu documento de origem."""

    record_id: str
    document_id: str
    content_sha256: str
    language: str
    focus: str | None
    category: str | None
    question_type: str | None
    question: str
    answer: str
    synonyms: tuple[str, ...]
    umls_cuis: tuple[str, ...]
    umls_semantic_types: tuple[str, ...]
    umls_semantic_groups: tuple[str, ...]
    source: CanonicalSource
    curation: CurationMetadata = CurationMetadata()
    schema_version: str = CANONICAL_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not self.question.strip():
            raise ValueError("CanonicalMedicalRecord requer uma pergunta não vazia.")
        if not self.answer.strip():
            raise ValueError("CanonicalMedicalRecord requer uma resposta não vazia.")

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "record_id": self.record_id,
            "document_id": self.document_id,
            "content_sha256": self.content_sha256,
            "language": self.language,
            "focus": self.focus,
            "category": self.category,
            "question_type": self.question_type,
            "question": self.question,
            "answer": self.answer,
            "synonyms": list(self.synonyms),
            "umls_cuis": list(self.umls_cuis),
            "umls_semantic_types": list(self.umls_semantic_types),
            "umls_semantic_groups": list(self.umls_semantic_groups),
            "source": self.source.as_dict(),
            "curation": self.curation.as_dict(),
        }
