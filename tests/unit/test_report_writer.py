from __future__ import annotations

import json
from pathlib import Path

from tech_ingestao.integrations.filesystem.report_writer import write_json, write_jsonl


def test_writes_json_and_creates_parent_directory(tmp_path: Path) -> None:
    destination = tmp_path / "nested" / "report.json"

    write_json(destination, {"acentuação": "médica", "count": 2})

    assert json.loads(destination.read_text(encoding="utf-8")) == {
        "acentuação": "médica",
        "count": 2,
    }


def test_writes_one_json_document_per_line(tmp_path: Path) -> None:
    destination = tmp_path / "nested" / "rejected.jsonl"

    write_jsonl(destination, ({"id": 1}, {"id": 2}))

    assert [json.loads(line) for line in destination.read_text(encoding="utf-8").splitlines()] == [
        {"id": 1},
        {"id": 2},
    ]
