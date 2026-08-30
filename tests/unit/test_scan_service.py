from __future__ import annotations

from pathlib import Path

import pytest

from tech_ingestao.errors import ScanError
from tech_ingestao.integrations.medquad.reader import normalize_text
from tech_ingestao.services.scan_service import scan_medquad

VALID_XML = """<?xml version="1.0" encoding="UTF-8"?>
<Document id="doc-1" source="Example" url="https://example.test/doc-1">
  <Focus>Example disease</Focus>
  <FocusAnnotations>
    <UMLS>
      <CUIs><CUI>C0000001</CUI></CUIs>
      <SemanticTypes><SemanticType>T047</SemanticType></SemanticTypes>
      <SemanticGroup>Disorders</SemanticGroup>
    </UMLS>
    <Synonyms><Synonym>Example condition</Synonym></Synonyms>
    <Category>Disease</Category>
  </FocusAnnotations>
  <QAPairs>
    <QAPair pid="1">
      <Question qid="q-1" qtype="symptoms">What are the symptoms?</Question>
      <Answer>Fever and fatigue.</Answer>
    </QAPair>
    <QAPair pid="2">
      <Question qid="q-2" qtype="symptoms"> What  are the symptoms? </Question>
      <Answer> Fever and fatigue. </Answer>
    </QAPair>
    <QAPair pid="3">
      <Question qid="q-3" qtype="treatment">How is it treated?</Question>
      <Answer>   </Answer>
    </QAPair>
    <QAPair pid="4">
      <Answer>Answer without a question.</Answer>
    </QAPair>
  </QAPairs>
</Document>
"""

LEGACY_XML = """<?xml version="1.0" encoding="UTF-8"?>
<doc docid="legacy-1" corpus="NINDS" url="https://example.test/legacy-1">
  <doctitle-focus>Legacy condition</doctitle-focus>
  <umls>
    <cui>C0000002</cui>
    <semanticType>T191</semanticType>
    <semanticGroup>Disorders</semanticGroup>
  </umls>
  <qaPairs>
    <pair pid="1">
      <question qid="legacy-1-1" qtype="information">What is the condition?</question>
      <answer>A legacy-format answer.</answer>
    </pair>
  </qaPairs>
</doc>
"""


def test_normalize_text_collapses_whitespace() -> None:
    assert normalize_text("  one\n two\tthree  ") == "one two three"


def test_scan_counts_valid_rejected_duplicate_and_malformed_items(tmp_path: Path) -> None:
    source = tmp_path / "MedQuAD"
    collection = source / "1_Example_QA"
    collection.mkdir(parents=True)
    (collection / "valid.xml").write_text(VALID_XML, encoding="utf-8")
    (collection / "broken.xml").write_text("<Document>", encoding="utf-8")

    result = scan_medquad(source)
    summary = result.report["summary"]

    assert summary["xml_files_discovered"] == 2
    assert summary["xml_files_parsed"] == 1
    assert summary["malformed_files"] == 1
    assert summary["qa_pairs_total"] == 4
    assert summary["qa_pairs_accepted"] == 2
    assert summary["qa_pairs_rejected"] == 2
    assert summary["missing_question"] == 1
    assert summary["missing_answer"] == 1
    assert summary["duplicate_question_occurrences"] == 1
    assert summary["duplicate_pair_occurrences"] == 1
    assert summary["rejection_records"] == 3
    assert result.report["collections"]["1_Example_QA"]["categories"] == {"Disease": 1}

    reasons = [record["reasons"] for record in result.rejected_records]
    assert ["malformed_xml"] in reasons
    assert ["missing_answer"] in reasons
    assert ["missing_question"] in reasons


def test_scan_uses_root_collection_for_xml_at_source_root(tmp_path: Path) -> None:
    (tmp_path / "valid.xml").write_text(VALID_XML, encoding="utf-8")

    result = scan_medquad(tmp_path)

    assert list(result.report["collections"]) == ["root"]


def test_scan_includes_legacy_lowercase_ninds_format(tmp_path: Path) -> None:
    source = tmp_path / "MedQuAD" / "6_NINDS_QA"
    source.mkdir(parents=True)
    (source / "legacy.xml").write_text(LEGACY_XML, encoding="utf-8")

    result = scan_medquad(source.parent)

    assert result.report["summary"]["qa_pairs_total"] == 1
    assert result.report["summary"]["qa_pairs_accepted"] == 1


def test_scan_rejects_missing_source(tmp_path: Path) -> None:
    with pytest.raises(ScanError, match="Diretório do MedQuAD não encontrado"):
        scan_medquad(tmp_path / "missing")


def test_scan_rejects_file_source(tmp_path: Path) -> None:
    source = tmp_path / "source.xml"
    source.write_text(VALID_XML, encoding="utf-8")

    with pytest.raises(ScanError, match="não é um diretório"):
        scan_medquad(source)


def test_scan_rejects_directory_without_xml(tmp_path: Path) -> None:
    with pytest.raises(ScanError, match="Nenhum arquivo XML"):
        scan_medquad(tmp_path)
