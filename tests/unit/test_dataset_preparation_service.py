from __future__ import annotations

from pathlib import Path

import pytest

from tech_ingestao.errors import DatasetPreparationError
from tech_ingestao.services.dataset_preparation_service import (
    SplitConfig,
    prepare_medquad_dataset,
)

from .test_scan_service import LEGACY_XML, VALID_XML


def _create_source(tmp_path: Path) -> Path:
    source = tmp_path / "MedQuAD"
    first_collection = source / "1_Example_QA"
    second_collection = source / "6_NINDS_QA"
    first_collection.mkdir(parents=True)
    second_collection.mkdir(parents=True)
    (first_collection / "valid.xml").write_text(VALID_XML, encoding="utf-8")
    (second_collection / "legacy.xml").write_text(LEGACY_XML, encoding="utf-8")
    return source


def test_preparation_deduplicates_and_has_no_cross_split_leakage(tmp_path: Path) -> None:
    source = _create_source(tmp_path)

    prepared = prepare_medquad_dataset(source)

    assert prepared.manifest["summary"]["canonical_records_before_deduplication"] == 3
    assert prepared.manifest["summary"]["canonical_records"] == 2
    assert prepared.manifest["summary"]["exact_duplicates_removed"] == 1
    assert len(prepared.duplicate_removals) == 1
    assert prepared.manifest["pii_audit"]["records_scanned"] == 3
    assert prepared.manifest["pii_audit"]["unresolved_records"] == 0
    assert prepared.manifest["summary"]["pii_records_redacted"] == 0
    assert prepared.manifest["summary"]["pii_records_redacted_before_deduplication"] == 0
    assert prepared.manifest["validation"] == {
        "cross_split_document_overlap": 0,
        "cross_split_record_overlap": 0,
        "cross_split_content_overlap": 0,
    }

    document_split: dict[str, str] = {}
    split_records = {
        "train": prepared.train_records,
        "validation": prepared.validation_records,
        "test": prepared.test_records,
    }
    for split, records in split_records.items():
        for record in records:
            assert document_split.setdefault(record.document_id, split) == split


def test_preparation_is_deterministic_for_same_seed(tmp_path: Path) -> None:
    source = _create_source(tmp_path)
    config = SplitConfig(seed=123)

    first = prepare_medquad_dataset(source, config=config)
    second = prepare_medquad_dataset(source, config=config)

    assert [record.record_id for record in first.canonical_records] == [
        record.record_id for record in second.canonical_records
    ]
    assert [record.record_id for record in first.train_records] == [
        record.record_id for record in second.train_records
    ]
    assert [record.record_id for record in first.validation_records] == [
        record.record_id for record in second.validation_records
    ]
    assert [record.record_id for record in first.test_records] == [
        record.record_id for record in second.test_records
    ]


def test_preparation_reports_redacted_records_without_sensitive_values(tmp_path: Path) -> None:
    source = tmp_path / "MedQuAD" / "1_Example_QA"
    source.mkdir(parents=True)
    pii_xml = VALID_XML.replace("Fever and fatigue.", "Email jane.doe@example.org")
    (source / "pii.xml").write_text(pii_xml, encoding="utf-8")

    prepared = prepare_medquad_dataset(source.parent)

    assert prepared.manifest["pii_audit"]["records_scanned"] == 2
    assert prepared.manifest["pii_audit"]["records_redacted"] == 2
    assert prepared.manifest["pii_audit"]["final_records_redacted"] == 1
    assert prepared.manifest["pii_audit"]["records_by_detected_type"] == {
        "email_address": 2
    }
    assert len(prepared.pii_findings) == 2
    assert prepared.manifest["summary"]["pii_records_redacted"] == 1
    assert prepared.manifest["summary"]["pii_records_redacted_before_deduplication"] == 2
    serialized_findings = str([finding.as_dict() for finding in prepared.pii_findings])
    assert "jane.doe@example.org" not in serialized_findings
    assert prepared.canonical_records[0].answer == "Email [REDACTED_EMAIL]"


def test_split_config_requires_valid_ratios() -> None:
    with pytest.raises(DatasetPreparationError, match="entre 0 e 1"):
        SplitConfig(train_ratio=1.0, validation_ratio=0.0, test_ratio=0.0)
    with pytest.raises(DatasetPreparationError, match="somar 1"):
        SplitConfig(train_ratio=0.7, validation_ratio=0.2, test_ratio=0.2)


def test_preparation_rejects_missing_source(tmp_path: Path) -> None:
    with pytest.raises(DatasetPreparationError, match="não encontrado"):
        prepare_medquad_dataset(tmp_path / "missing")


def test_preparation_rejects_file_source(tmp_path: Path) -> None:
    source = tmp_path / "source.xml"
    source.write_text(VALID_XML, encoding="utf-8")

    with pytest.raises(DatasetPreparationError, match="não é um diretório"):
        prepare_medquad_dataset(source)


def test_preparation_rejects_source_without_xml(tmp_path: Path) -> None:
    with pytest.raises(DatasetPreparationError, match="Nenhum arquivo XML"):
        prepare_medquad_dataset(tmp_path)


def test_preparation_rejects_malformed_xml(tmp_path: Path) -> None:
    source = tmp_path / "MedQuAD"
    source.mkdir()
    (source / "broken.xml").write_text("<Document>", encoding="utf-8")

    with pytest.raises(DatasetPreparationError, match="XML inválido"):
        prepare_medquad_dataset(source)
