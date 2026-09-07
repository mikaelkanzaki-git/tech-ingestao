"""Curadoria, deduplicação e divisão reproduzível do dataset canônico."""

from __future__ import annotations

import hashlib
import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from tech_ingestao.errors import DatasetPreparationError
from tech_ingestao.integrations.medquad.git_metadata import read_git_metadata
from tech_ingestao.integrations.medquad.reader import (
    MalformedMedQuADDocumentError,
    MedQuADReader,
)
from tech_ingestao.models.canonical import CANONICAL_SCHEMA_VERSION, CanonicalMedicalRecord
from tech_ingestao.models.dataset import DuplicateRemoval, PreparedDataset
from tech_ingestao.services.canonicalization_service import canonicalize_medquad_document
from tech_ingestao.services.pii_service import build_pii_audit, build_pii_findings

SplitName = Literal["train", "validation", "test"]
SPLIT_MANIFEST_SCHEMA_VERSION = "1.0"


@dataclass(frozen=True, slots=True)
class SplitConfig:
    """Parâmetros que tornam a divisão reproduzível e auditável."""

    train_ratio: float = 0.8
    validation_ratio: float = 0.1
    test_ratio: float = 0.1
    seed: int = 42

    def __post_init__(self) -> None:
        ratios = (self.train_ratio, self.validation_ratio, self.test_ratio)
        if any(ratio <= 0 or ratio >= 1 for ratio in ratios):
            raise DatasetPreparationError("Cada proporção deve estar entre 0 e 1.")
        if not math.isclose(sum(ratios), 1.0, abs_tol=1e-9):
            raise DatasetPreparationError("As proporções de split devem somar 1.")

    def as_dict(self) -> dict[str, float | int]:
        return {
            "train_ratio": self.train_ratio,
            "validation_ratio": self.validation_ratio,
            "test_ratio": self.test_ratio,
            "seed": self.seed,
        }


def _collection_name(source_root: Path, xml_path: Path) -> str:
    relative = xml_path.relative_to(source_root)
    return relative.parts[0] if len(relative.parts) > 1 else "root"


def _record_order(record: CanonicalMedicalRecord) -> tuple[str, str, str, str]:
    return (
        record.source.relative_path,
        record.source.upstream_question_id or "",
        record.source.upstream_pair_id or "",
        record.record_id,
    )


def _deduplicate(
    records: list[CanonicalMedicalRecord],
) -> tuple[tuple[CanonicalMedicalRecord, ...], tuple[DuplicateRemoval, ...]]:
    kept_by_hash: dict[str, CanonicalMedicalRecord] = {}
    unique_records: list[CanonicalMedicalRecord] = []
    removals: list[DuplicateRemoval] = []

    for record in sorted(records, key=_record_order):
        kept = kept_by_hash.get(record.content_sha256)
        if kept is None:
            kept_by_hash[record.content_sha256] = record
            unique_records.append(record)
            continue
        removals.append(
            DuplicateRemoval(
                content_sha256=record.content_sha256,
                kept_record_id=kept.record_id,
                kept_document_id=kept.document_id,
                dropped_record_id=record.record_id,
                dropped_document_id=record.document_id,
            )
        )
    return tuple(unique_records), tuple(removals)


def _assign_split(document_id: str, config: SplitConfig) -> SplitName:
    digest = hashlib.sha256(f"{config.seed}:{document_id}".encode()).digest()
    position = int.from_bytes(digest[:8], byteorder="big") / 2**64
    if position < config.train_ratio:
        return "train"
    if position < config.train_ratio + config.validation_ratio:
        return "validation"
    return "test"


def _normalize_question(question: str) -> str:
    normalized = unicodedata.normalize("NFKC", question).casefold()
    normalized = " ".join(normalized.split())
    return re.sub(r"\s+([?!.,;:])", r"\1", normalized)


def _component_keys(
    records: tuple[CanonicalMedicalRecord, ...],
) -> tuple[dict[str, str], int]:
    """Agrupa documentos conectados por ao menos uma pergunta normalizada."""

    parent = {record.document_id: record.document_id for record in records}

    def find(document_id: str) -> str:
        root = document_id
        while parent[root] != root:
            root = parent[root]
        while parent[document_id] != document_id:
            previous = parent[document_id]
            parent[document_id] = root
            document_id = previous
        return root

    def union(left: str, right: str) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root == right_root:
            return
        kept, merged = sorted((left_root, right_root))
        parent[merged] = kept

    first_document_by_question: dict[str, str] = {}
    for record in sorted(records, key=_record_order):
        normalized_question = _normalize_question(record.question)
        first_document = first_document_by_question.setdefault(
            normalized_question, record.document_id
        )
        union(first_document, record.document_id)

    documents_by_root: dict[str, list[str]] = {}
    for document_id in parent:
        documents_by_root.setdefault(find(document_id), []).append(document_id)
    component_key_by_document = {
        document_id: min(documents)
        for documents in documents_by_root.values()
        for document_id in documents
    }
    return component_key_by_document, len(documents_by_root)


def _overlap_count(*values: set[str]) -> int:
    overlap: set[str] = set()
    for index, left in enumerate(values):
        for right in values[index + 1 :]:
            overlap.update(left & right)
    return len(overlap)


def _validation_report(splits: dict[SplitName, list[CanonicalMedicalRecord]]) -> dict[str, int]:
    document_sets = [{record.document_id for record in records} for records in splits.values()]
    record_sets = [{record.record_id for record in records} for records in splits.values()]
    content_sets = [{record.content_sha256 for record in records} for records in splits.values()]
    question_sets = [
        {_normalize_question(record.question) for record in records}
        for records in splits.values()
    ]
    return {
        "cross_split_document_overlap": _overlap_count(*document_sets),
        "cross_split_record_overlap": _overlap_count(*record_sets),
        "cross_split_content_overlap": _overlap_count(*content_sets),
        "cross_split_normalized_question_overlap": _overlap_count(*question_sets),
    }


def _collection_counts(records: list[CanonicalMedicalRecord]) -> dict[str, int]:
    counts = Counter(record.source.collection for record in records)
    return dict(sorted(counts.items()))


def _document_count(records: list[CanonicalMedicalRecord]) -> int:
    return len({record.document_id for record in records})


def prepare_medquad_dataset(
    source_root: Path,
    *,
    config: SplitConfig | None = None,
    reader: MedQuADReader | None = None,
) -> PreparedDataset:
    """Lê, canonicaliza, deduplica e divide o MedQuAD sem vazamento."""

    source_root = source_root.expanduser().resolve()
    if not source_root.exists():
        raise DatasetPreparationError(f"Diretório do MedQuAD não encontrado: {source_root}")
    if not source_root.is_dir():
        raise DatasetPreparationError(f"O caminho do MedQuAD não é um diretório: {source_root}")

    split_config = config or SplitConfig()
    dataset_reader = reader or MedQuADReader()
    xml_files = dataset_reader.discover(source_root)
    if not xml_files:
        raise DatasetPreparationError(f"Nenhum arquivo XML encontrado em: {source_root}")

    metadata = read_git_metadata(source_root)
    input_records: list[CanonicalMedicalRecord] = []
    for xml_path in xml_files:
        relative_path = xml_path.relative_to(source_root).as_posix()
        try:
            document = dataset_reader.read(xml_path)
        except MalformedMedQuADDocumentError as error:
            raise DatasetPreparationError(f"XML inválido em {relative_path}: {error}") from error
        input_records.extend(
            canonicalize_medquad_document(
                document,
                collection=_collection_name(source_root, xml_path),
                relative_path=relative_path,
                upstream_repository=metadata.repository,
                upstream_revision=metadata.revision,
            )
        )

    pii_audit = build_pii_audit(input_records)
    if pii_audit["unresolved_records"]:
        raise DatasetPreparationError(
            f"A auditoria de PII encontrou registros não resolvidos: {pii_audit}"
        )

    pii_findings = build_pii_findings(input_records)
    canonical_records, duplicate_removals = _deduplicate(input_records)
    final_pii_audit = build_pii_audit(canonical_records)
    pii_audit.update(
        {
            "records_after_deduplication": final_pii_audit["records_scanned"],
            "final_records_by_status": final_pii_audit["records_by_status"],
            "final_records_redacted": final_pii_audit["records_redacted"],
        }
    )
    splits: dict[SplitName, list[CanonicalMedicalRecord]] = {
        "train": [],
        "validation": [],
        "test": [],
    }
    component_keys, component_count = _component_keys(canonical_records)
    for record in canonical_records:
        split_key = component_keys[record.document_id]
        splits[_assign_split(split_key, split_config)].append(record)

    validation = _validation_report(splits)
    if any(validation.values()):
        raise DatasetPreparationError(f"Vazamento detectado entre splits: {validation}")

    record_counts = {name: len(records) for name, records in splits.items()}
    document_counts = {name: _document_count(records) for name, records in splits.items()}
    manifest: dict[str, Any] = {
        "schema_version": SPLIT_MANIFEST_SCHEMA_VERSION,
        "canonical_schema_version": CANONICAL_SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "dataset": {
            "name": "MedQuAD",
            "source_root": str(source_root),
            "upstream_repository": metadata.repository,
            "upstream_revision": metadata.revision,
        },
        "configuration": {
            **split_config.as_dict(),
            "split_unit": "document_question_component",
            "assignment_strategy": "sha256_seeded_component_threshold",
            "question_normalization": "unicode_nfkc_casefold_whitespace_punctuation",
            "deduplication_strategy": "content_sha256_keep_first_by_source",
        },
        "summary": {
            "xml_files": len(xml_files),
            "canonical_records_before_deduplication": len(input_records),
            "canonical_records": len(canonical_records),
            "exact_duplicates_removed": len(duplicate_removals),
            "documents": len({record.document_id for record in canonical_records}),
            "split_components": component_count,
            "pii_records_redacted_before_deduplication": pii_audit["records_redacted"],
            "pii_records_redacted": pii_audit["final_records_redacted"],
            "records_by_split": record_counts,
            "documents_by_split": document_counts,
        },
        "records_by_collection_and_split": {
            name: _collection_counts(records) for name, records in splits.items()
        },
        "pii_audit": pii_audit,
        "validation": validation,
    }
    return PreparedDataset(
        canonical_records=canonical_records,
        train_records=tuple(splits["train"]),
        validation_records=tuple(splits["validation"]),
        test_records=tuple(splits["test"]),
        duplicate_removals=duplicate_removals,
        pii_findings=pii_findings,
        manifest=manifest,
    )
