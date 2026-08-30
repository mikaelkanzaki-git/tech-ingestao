"""Orquestração e regras de qualidade da varredura do MedQuAD."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tech_ingestao.errors import ScanError
from tech_ingestao.integrations.medquad.git_metadata import read_git_metadata
from tech_ingestao.integrations.medquad.reader import (
    MalformedMedQuADDocumentError,
    MedQuADReader,
    normalize_text,
)
from tech_ingestao.models.scan import CollectionStats, ScanResult

REPORT_SCHEMA_VERSION = "1.0"


def _fingerprint(*values: str) -> str:
    canonical = "\u241f".join(normalize_text(value).casefold() for value in values)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _collection_name(source_root: Path, xml_path: Path) -> str:
    relative = xml_path.relative_to(source_root)
    return relative.parts[0] if len(relative.parts) > 1 else "root"


def _new_rejection(
    *,
    record_type: str,
    relative_path: str,
    collection: str,
    reasons: list[str],
    document_id: str | None = None,
    question_id: str | None = None,
    pair_id: str | None = None,
    question: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    return {
        "record_type": record_type,
        "relative_path": relative_path,
        "collection": collection,
        "document_id": document_id,
        "question_id": question_id,
        "pair_id": pair_id,
        "question": question,
        "reasons": reasons,
        "error": error,
    }


def scan_medquad(source_root: Path, *, reader: MedQuADReader | None = None) -> ScanResult:
    """Varre os XMLs do MedQuAD sem modificar o dataset de origem."""

    source_root = source_root.expanduser().resolve()
    if not source_root.exists():
        raise ScanError(f"Diretório do MedQuAD não encontrado: {source_root}")
    if not source_root.is_dir():
        raise ScanError(f"O caminho do MedQuAD não é um diretório: {source_root}")

    dataset_reader = reader or MedQuADReader()
    xml_files = dataset_reader.discover(source_root)
    if not xml_files:
        raise ScanError(f"Nenhum arquivo XML encontrado em: {source_root}")

    collections: dict[str, CollectionStats] = {}
    rejected_records: list[dict[str, Any]] = []
    seen_questions: set[str] = set()
    seen_pairs: set[str] = set()

    for xml_path in xml_files:
        relative_path = xml_path.relative_to(source_root).as_posix()
        collection = _collection_name(source_root, xml_path)
        stats = collections.setdefault(collection, CollectionStats())
        stats.xml_files_discovered += 1

        try:
            document = dataset_reader.read(xml_path)
        except MalformedMedQuADDocumentError as error:
            stats.malformed_files += 1
            rejected_records.append(
                _new_rejection(
                    record_type="file",
                    relative_path=relative_path,
                    collection=collection,
                    reasons=["malformed_xml"],
                    error=str(error),
                )
            )
            continue

        stats.xml_files_parsed += 1
        stats.categories[document.category or "unknown"] += 1

        for pair in document.pairs:
            stats.qa_pairs_total += 1
            reasons: list[str] = []
            if not pair.question:
                reasons.append("missing_question")
                stats.missing_question += 1
            if not pair.answer:
                reasons.append("missing_answer")
                stats.missing_answer += 1

            if reasons:
                stats.qa_pairs_rejected += 1
                rejected_records.append(
                    _new_rejection(
                        record_type="qa_pair",
                        relative_path=relative_path,
                        collection=collection,
                        document_id=document.document_id,
                        question_id=pair.question_id,
                        pair_id=pair.pair_id,
                        question=pair.question or None,
                        reasons=reasons,
                    )
                )
                continue

            stats.qa_pairs_accepted += 1
            stats.question_types[pair.question_type or "unknown"] += 1

            question_fingerprint = _fingerprint(pair.question)
            if question_fingerprint in seen_questions:
                stats.duplicate_question_occurrences += 1
            else:
                seen_questions.add(question_fingerprint)

            pair_fingerprint = _fingerprint(pair.question, pair.answer)
            if pair_fingerprint in seen_pairs:
                stats.duplicate_pair_occurrences += 1
            else:
                seen_pairs.add(pair_fingerprint)

    metadata = read_git_metadata(source_root)
    collection_documents = {
        name: item.as_dict() for name, item in sorted(collections.items())
    }

    def sum_stat(name: str) -> int:
        return sum(getattr(item, name) for item in collections.values())

    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "dataset": {
            "name": "MedQuAD",
            "source_root": str(source_root),
            "upstream_repository": metadata.repository,
            "upstream_revision": metadata.revision,
        },
        "summary": {
            "collections_discovered": len(collections),
            "xml_files_discovered": sum_stat("xml_files_discovered"),
            "xml_files_parsed": sum_stat("xml_files_parsed"),
            "malformed_files": sum_stat("malformed_files"),
            "qa_pairs_total": sum_stat("qa_pairs_total"),
            "qa_pairs_accepted": sum_stat("qa_pairs_accepted"),
            "qa_pairs_rejected": sum_stat("qa_pairs_rejected"),
            "missing_question": sum_stat("missing_question"),
            "missing_answer": sum_stat("missing_answer"),
            "duplicate_question_occurrences": sum_stat(
                "duplicate_question_occurrences"
            ),
            "duplicate_pair_occurrences": sum_stat("duplicate_pair_occurrences"),
            "rejection_records": len(rejected_records),
        },
        "collections": collection_documents,
    }
    return ScanResult(report=report, rejected_records=tuple(rejected_records))
