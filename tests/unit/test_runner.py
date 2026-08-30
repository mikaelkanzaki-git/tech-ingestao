from __future__ import annotations

import json
from pathlib import Path

from tech_ingestao.runner import main

from .test_scan_service import VALID_XML


def test_scan_command_writes_report_and_rejected_jsonl(tmp_path: Path) -> None:
    source = tmp_path / "MedQuAD" / "1_Example_QA"
    output = tmp_path / "output"
    source.mkdir(parents=True)
    (source / "valid.xml").write_text(VALID_XML, encoding="utf-8")

    exit_code = main(["scan", "--source", str(source.parent), "--output", str(output)])

    assert exit_code == 0
    report = json.loads((output / "report.json").read_text(encoding="utf-8"))
    assert report["summary"]["qa_pairs_total"] == 4
    assert len((output / "rejected.jsonl").read_text(encoding="utf-8").splitlines()) == 2


def test_scan_command_returns_error_for_invalid_source(tmp_path: Path) -> None:
    exit_code = main(["scan", "--source", str(tmp_path / "missing")])

    assert exit_code == 2


def test_prepare_command_writes_canonical_splits_and_manifest(tmp_path: Path) -> None:
    source = tmp_path / "MedQuAD" / "1_Example_QA"
    output = tmp_path / "dataset"
    source.mkdir(parents=True)
    (source / "valid.xml").write_text(VALID_XML, encoding="utf-8")

    exit_code = main(
        ["prepare", "--source", str(source.parent), "--output", str(output)]
    )

    assert exit_code == 0
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["summary"]["canonical_records"] == 1
    assert manifest["summary"]["exact_duplicates_removed"] == 1
    assert len((output / "canonical.jsonl").read_text(encoding="utf-8").splitlines()) == 1
    assert (output / "train.jsonl").exists()
    assert (output / "validation.jsonl").exists()
    assert (output / "test.jsonl").exists()
    assert len((output / "duplicates.jsonl").read_text(encoding="utf-8").splitlines()) == 1
    assert (output / "pii-audit.jsonl").exists()
    assert (output / "pii-audit.jsonl").read_text(encoding="utf-8") == ""


def test_prepare_command_returns_error_for_invalid_ratios(tmp_path: Path) -> None:
    exit_code = main(
        [
            "prepare",
            "--source",
            str(tmp_path),
            "--train-ratio",
            "0.7",
            "--validation-ratio",
            "0.2",
            "--test-ratio",
            "0.2",
        ]
    )

    assert exit_code == 2
