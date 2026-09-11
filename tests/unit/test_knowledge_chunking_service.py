from __future__ import annotations

from itertools import pairwise

from tech_ingestao.models.canonical import CanonicalMedicalRecord, CanonicalSource
from tech_ingestao.services.knowledge_chunking_service import (
    CHUNKING_VERSION,
    MAX_KNOWLEDGE_DOCUMENT_BYTES,
    TARGET_KNOWLEDGE_DOCUMENT_CHARS,
    build_knowledge_document,
    build_knowledge_documents,
)


def _record(
    *,
    answer: str,
    question: str = "What are the symptoms?",
    focus: str | None = "Example condition",
) -> CanonicalMedicalRecord:
    return CanonicalMedicalRecord(
        record_id="record-1",
        document_id="document-1",
        content_sha256="content-hash",
        language="en",
        focus=focus,
        category="Diseases",
        question_type="symptoms",
        question=question,
        answer=answer,
        synonyms=(),
        umls_cuis=(),
        umls_semantic_types=(),
        umls_semantic_groups=(),
        source=CanonicalSource(
            dataset="MedQuAD",
            collection="collection",
            relative_path="collection/1.xml",
            upstream_repository="https://example.test/MedQuAD.git",
            upstream_revision="abc123",
            upstream_document_id="1",
            upstream_pair_id="1",
            upstream_question_id="1-1",
            publisher="NIH",
            url="https://example.test/source",
            license="CC-BY-4.0",
        ),
    )


def test_short_record_preserves_existing_id_and_text() -> None:
    record = _record(answer="A short answer.")
    original = build_knowledge_document(record, split="train")

    documents = build_knowledge_documents(record, split="train")

    assert len(documents) == 1
    assert documents[0].record_id == original.record_id
    assert documents[0].text == original.text
    assert documents[0].metadata["parent_record_id"] == record.record_id
    assert documents[0].metadata["chunk_index"] == 0
    assert documents[0].metadata["chunk_count"] == 1
    assert documents[0].metadata["chunking_version"] == CHUNKING_VERSION
    assert len(str(documents[0].metadata["chunk_sha256"])) == 64
    assert documents[0].metadata["chunk_utf8_bytes"] == len(original.text.encode("utf-8"))


def test_long_record_has_repeated_context_stable_ids_and_provenance() -> None:
    answer = " ".join(
        f"Sentence {index} describes medically relevant information."
        for index in range(120)
    )
    record = _record(answer=answer)

    first = build_knowledge_documents(record, split="validation")
    second = build_knowledge_documents(record, split="validation")

    assert first == second
    assert len(first) > 1
    assert first[0].record_id == record.record_id
    assert first[1].record_id == f"{record.record_id}::chunk::0001"
    assert len({document.record_id for document in first}) == len(first)
    assert all(
        document.text.startswith(
            "Medical topic: Example condition\nQuestion: What are the symptoms?\nAnswer: "
        )
        for document in first
    )
    assert all(len(document.text) <= TARGET_KNOWLEDGE_DOCUMENT_CHARS for document in first)
    assert all(
        len(document.text.encode("utf-8")) <= MAX_KNOWLEDGE_DOCUMENT_BYTES
        for document in first
    )
    assert [document.metadata["chunk_index"] for document in first] == list(range(len(first)))
    assert all(document.metadata["chunk_count"] == len(first) for document in first)
    assert all(document.metadata["parent_record_id"] == record.record_id for document in first)
    assert all(
        document.metadata["source_url"] == "https://example.test/source" for document in first
    )
    assert all(
        document.metadata["chunk_utf8_bytes"] == len(document.text.encode("utf-8"))
        for document in first
    )


def test_semantic_chunking_prefers_complete_sentences_and_keeps_overlap() -> None:
    sentences = [
        f"Clinical sentence {index:03d} has distinct relevant information."
        for index in range(100)
    ]
    record = _record(answer=" ".join(sentences))

    documents = build_knowledge_documents(record, split="train")
    answers = [document.text.split("\nAnswer: ", maxsplit=1)[1] for document in documents]

    assert len(answers) > 1
    assert all(answer.endswith(".") for answer in answers[:-1])
    assert all(answer.startswith("Clinical sentence ") for answer in answers[1:])
    for previous, current in pairwise(answers):
        first_overlapping_sentence = f"{current.split('.', maxsplit=1)[0]}."
        assert first_overlapping_sentence in previous


def test_multibyte_and_unbroken_content_respects_utf8_hard_limit() -> None:
    record = _record(
        answer="🩺" * 5_000,
        question="Q" * (TARGET_KNOWLEDGE_DOCUMENT_CHARS + 1),
        focus=None,
    )

    documents = build_knowledge_documents(record, split="train")

    assert len(documents) > 1
    assert all(document.text for document in documents)
    assert all(
        len(document.text.encode("utf-8")) <= MAX_KNOWLEDGE_DOCUMENT_BYTES
        for document in documents
    )


def test_large_repeatable_context_reduces_overlap_to_guarantee_progress() -> None:
    record = _record(answer="A" * 5_000, question="Q" * 700)

    documents = build_knowledge_documents(record, split="train")

    assert 1 < len(documents) < 40
    assert all(len(document.text) <= TARGET_KNOWLEDGE_DOCUMENT_CHARS for document in documents)
