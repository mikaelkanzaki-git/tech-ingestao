"""Transformação de documentos MedQuAD em registros canônicos versionados."""

from __future__ import annotations

import hashlib
from uuid import UUID, uuid5

from tech_ingestao.models.canonical import (
    CanonicalMedicalRecord,
    CanonicalSource,
    CurationMetadata,
)
from tech_ingestao.models.medquad import MedQuADDocument
from tech_ingestao.services.pii_service import redact_pii

MEDQUAD_DATASET_NAME = "MedQuAD"
MEDQUAD_LICENSE = "CC-BY-4.0"
_CANONICAL_ID_NAMESPACE = UUID("e76a4554-385b-5bfd-9ba8-11f043b3633c")


def _stable_id(kind: str, *parts: object) -> str:
    identity = ":".join([MEDQUAD_DATASET_NAME.casefold(), kind, *(str(part) for part in parts)])
    return str(uuid5(_CANONICAL_ID_NAMESPACE, identity))


def _content_hash(question: str, answer: str) -> str:
    content = f"{question}\u241f{answer}"
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def canonicalize_medquad_document(
    document: MedQuADDocument,
    *,
    collection: str,
    relative_path: str,
    upstream_repository: str | None,
    upstream_revision: str | None,
) -> tuple[CanonicalMedicalRecord, ...]:
    """Converte somente pares válidos e mantém o documento como unidade de split."""

    document_id = _stable_id("document", relative_path)
    records: list[CanonicalMedicalRecord] = []
    for pair in document.pairs:
        if not pair.question or not pair.answer:
            continue

        focus = redact_pii(document.focus or "")
        question = redact_pii(pair.question)
        answer = redact_pii(pair.answer)
        synonyms = tuple(redact_pii(value) for value in document.synonyms)
        pii_types = tuple(
            dict.fromkeys(
                (
                    *focus.detected_types,
                    *question.detected_types,
                    *answer.detected_types,
                    *(pii_type for value in synonyms for pii_type in value.detected_types),
                )
            )
        )
        transformations: tuple[str, ...] = ("whitespace_normalized",)
        if pii_types:
            transformations += ("pii_redacted",)

        record_id = _stable_id(
            "record",
            relative_path,
            pair.position,
            pair.pair_id or "",
            pair.question_id or "",
        )
        records.append(
            CanonicalMedicalRecord(
                record_id=record_id,
                document_id=document_id,
                content_sha256=_content_hash(question.text, answer.text),
                language="en",
                focus=focus.text or None,
                category=document.category,
                question_type=pair.question_type,
                question=question.text,
                answer=answer.text,
                synonyms=tuple(value.text for value in synonyms),
                umls_cuis=document.umls_cuis,
                umls_semantic_types=document.umls_semantic_types,
                umls_semantic_groups=document.umls_semantic_groups,
                source=CanonicalSource(
                    dataset=MEDQUAD_DATASET_NAME,
                    collection=collection,
                    relative_path=relative_path,
                    upstream_repository=upstream_repository,
                    upstream_revision=upstream_revision,
                    upstream_document_id=document.document_id,
                    upstream_pair_id=pair.pair_id,
                    upstream_question_id=pair.question_id,
                    publisher=document.publisher,
                    url=document.source_url,
                    license=MEDQUAD_LICENSE,
                ),
                curation=CurationMetadata(
                    pii_status="redacted" if pii_types else "not_detected",
                    pii_types=pii_types,
                    transformations=transformations,
                ),
            )
        )
    return tuple(records)
