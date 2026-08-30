from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from tech_ingestao.integrations.medquad.reader import MedQuADReader
from tech_ingestao.models.canonical import CurationMetadata
from tech_ingestao.services.canonicalization_service import canonicalize_medquad_document

from .test_scan_service import LEGACY_XML, VALID_XML


def test_reader_preserves_medical_annotations_and_provenance(tmp_path: Path) -> None:
    xml_path = tmp_path / "document.xml"
    xml_path.write_text(VALID_XML, encoding="utf-8")

    document = MedQuADReader().read(xml_path)

    assert document.document_id == "doc-1"
    assert document.publisher == "Example"
    assert document.source_url == "https://example.test/doc-1"
    assert document.focus == "Example disease"
    assert document.category == "Disease"
    assert document.synonyms == ("Example condition",)
    assert document.umls_cuis == ("C0000001",)
    assert document.umls_semantic_types == ("T047",)
    assert document.umls_semantic_groups == ("Disorders",)
    assert document.pairs[0].position == 1


def test_reader_maps_legacy_lowercase_format(tmp_path: Path) -> None:
    xml_path = tmp_path / "legacy.xml"
    xml_path.write_text(LEGACY_XML, encoding="utf-8")

    document = MedQuADReader().read(xml_path)

    assert document.document_id == "legacy-1"
    assert document.publisher == "NINDS"
    assert document.focus == "Legacy condition"
    assert document.umls_cuis == ("C0000002",)
    assert document.umls_semantic_types == ("T191",)
    assert document.umls_semantic_groups == ("Disorders",)
    assert document.pairs[0].question == "What is the condition?"
    assert document.pairs[0].answer == "A legacy-format answer."


def test_canonicalization_keeps_only_valid_pairs_and_is_deterministic(tmp_path: Path) -> None:
    xml_path = tmp_path / "valid.xml"
    xml_path.write_text(VALID_XML, encoding="utf-8")
    document = MedQuADReader().read(xml_path)
    arguments = {
        "collection": "1_Example_QA",
        "relative_path": "1_Example_QA/valid.xml",
        "upstream_repository": "https://github.com/example/MedQuAD.git",
        "upstream_revision": "a" * 40,
    }

    records = canonicalize_medquad_document(document, **arguments)
    repeated_records = canonicalize_medquad_document(document, **arguments)

    assert len(records) == 2
    assert records == repeated_records
    assert records[0].document_id == records[1].document_id
    assert records[0].record_id != records[1].record_id
    assert len(records[0].content_sha256) == 64
    assert records[0].source.relative_path == "1_Example_QA/valid.xml"
    assert records[0].source.upstream_document_id == "doc-1"
    assert records[0].source.license == "CC-BY-4.0"
    assert records[0].curation.pii_status == "not_detected"
    assert records[0].curation.pii_types == ()


def test_canonical_dict_matches_json_schema_top_level(tmp_path: Path) -> None:
    xml_path = tmp_path / "legacy.xml"
    xml_path.write_text(LEGACY_XML, encoding="utf-8")
    document = MedQuADReader().read(xml_path)
    record = canonicalize_medquad_document(
        document,
        collection="6_NINDS_QA",
        relative_path="6_NINDS_QA/legacy.xml",
        upstream_repository=None,
        upstream_revision=None,
    )[0]
    schema_path = Path(__file__).parents[2] / "schemas" / "canonical-medical-record.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    assert set(record.as_dict()) == set(schema["required"])
    assert record.as_dict()["source"]["publisher"] == "NINDS"
    assert record.as_dict()["curation"]["status"] == "accepted"
    assert record.as_dict()["curation"]["pii_types"] == []


def test_canonicalization_redacts_pii_before_generating_content_hash(tmp_path: Path) -> None:
    xml_path = tmp_path / "valid.xml"
    xml_path.write_text(VALID_XML, encoding="utf-8")
    document = MedQuADReader().read(xml_path)
    document = replace(
        document,
        pairs=(
            replace(
                document.pairs[0],
                answer="Patient Name: Jane Doe; email jane.doe@example.test or 301-496-5248.",
            ),
        ),
    )

    record = canonicalize_medquad_document(
        document,
        collection="1_Example_QA",
        relative_path="1_Example_QA/valid.xml",
        upstream_repository=None,
        upstream_revision=None,
    )[0]

    assert "Jane Doe" not in record.answer
    assert "jane.doe@example.test" not in record.answer
    assert "301-496-5248" not in record.answer
    assert "[REDACTED_PATIENT_NAME]" in record.answer
    assert "[REDACTED_EMAIL]" in record.answer
    assert "[REDACTED_PHONE]" in record.answer
    assert record.curation.pii_status == "redacted"
    assert record.curation.pii_types == (
        "email_address",
        "phone_number",
        "patient_name",
    )
    assert record.curation.transformations == ("whitespace_normalized", "pii_redacted")


def test_curation_metadata_requires_consistent_pii_status() -> None:
    with pytest.raises(ValueError, match="redacted requer"):
        CurationMetadata(pii_status="redacted")
    with pytest.raises(ValueError, match="not_detected não aceita"):
        CurationMetadata(pii_status="not_detected", pii_types=("email_address",))


def test_canonical_record_rejects_empty_question_and_answer(tmp_path: Path) -> None:
    xml_path = tmp_path / "legacy.xml"
    xml_path.write_text(LEGACY_XML, encoding="utf-8")
    document = MedQuADReader().read(xml_path)
    record = canonicalize_medquad_document(
        document,
        collection="6_NINDS_QA",
        relative_path="6_NINDS_QA/legacy.xml",
        upstream_repository=None,
        upstream_revision=None,
    )[0]

    with pytest.raises(ValueError, match="pergunta não vazia"):
        replace(record, question=" ")
    with pytest.raises(ValueError, match="resposta não vazia"):
        replace(record, answer=" ")
