"""Formata e divide registros canônicos para recuperação semântica."""

from __future__ import annotations

import hashlib
import re

from tech_ingestao.models.canonical import CanonicalMedicalRecord
from tech_ingestao.models.knowledge import KnowledgeDocument, MetadataValue

# O MiniLM usado pelo projeto trunca entradas em 256 tokens. O alvo em caracteres não
# substitui uma contagem de tokens, mas mantém os textos próximos dessa janela sem acoplar
# esta regra de domínio ao tokenizer do adaptador ONNX.
TARGET_KNOWLEDGE_DOCUMENT_CHARS = 1_000
TARGET_ANSWER_CHUNK_CHARS = 1_000
CHUNK_OVERLAP_CHARS = 180

# Chroma Cloud aceita no máximo 16 KiB no campo document. A folga cobre variações de UTF-8
# e evita que uma mudança pequena na formatação encoste no limite do provedor.
MAX_KNOWLEDGE_DOCUMENT_BYTES = 12 * 1_024
CHUNKING_VERSION = "semantic-v1"

_BOUNDARY_PATTERN = re.compile(r"\n{2,}|\n|(?<=[.!?])\s+")
_MIN_SEMANTIC_CHUNK_RATIO = 0.55


def _base_metadata(record: CanonicalMedicalRecord, split: str) -> dict[str, MetadataValue]:
    source = record.source
    values: dict[str, MetadataValue | None] = {
        "schema_version": record.schema_version,
        "document_id": record.document_id,
        "content_sha256": record.content_sha256,
        "language": record.language,
        "focus": record.focus,
        "category": record.category,
        "question_type": record.question_type,
        "dataset": source.dataset,
        "collection": source.collection,
        "relative_path": source.relative_path,
        "upstream_revision": source.upstream_revision,
        "publisher": source.publisher,
        "source_url": source.url,
        "license": source.license,
        "split": split,
    }
    return {key: value for key, value in values.items() if value is not None}


def _context_sections(record: CanonicalMedicalRecord) -> list[str]:
    sections: list[str] = []
    if record.focus:
        sections.append(f"Medical topic: {record.focus}")
    sections.append(f"Question: {record.question}")
    return sections


def build_knowledge_document(record: CanonicalMedicalRecord, *, split: str) -> KnowledgeDocument:
    """Monta o documento original; registros curtos preservam exatamente este contrato."""

    text = "\n".join((*_context_sections(record), f"Answer: {record.answer}"))
    return KnowledgeDocument(
        record_id=record.record_id,
        text=text,
        metadata=_base_metadata(record, split),
    )


def _maximum_end(text: str, start: int, *, max_chars: int, max_bytes: int) -> int:
    """Encontra o maior fim que respeita simultaneamente caracteres e bytes UTF-8."""

    upper = min(len(text), start + max_chars)
    if len(text[start:upper].encode("utf-8")) <= max_bytes:
        return upper

    lower = start + 1
    best = start
    while lower <= upper:
        middle = (lower + upper) // 2
        if len(text[start:middle].encode("utf-8")) <= max_bytes:
            best = middle
            lower = middle + 1
        else:
            upper = middle - 1
    return best


def _semantic_end(text: str, start: int, hard_end: int) -> int:
    if hard_end >= len(text):
        return len(text)

    candidate = text[start:hard_end]
    minimum = max(1, int(len(candidate) * _MIN_SEMANTIC_CHUNK_RATIO))
    semantic_breaks = [match.start() for match in _BOUNDARY_PATTERN.finditer(candidate)]
    useful_breaks = [position for position in semantic_breaks if position >= minimum]
    if useful_breaks:
        return start + useful_breaks[-1]

    whitespace = candidate.rfind(" ", minimum)
    if whitespace >= minimum:
        return start + whitespace
    return hard_end


def _overlap_start(text: str, start: int, end: int, overlap_chars: int) -> int:
    candidate = max(start + 1, end - overlap_chars)
    overlap_region = text[candidate:end]
    for match in _BOUNDARY_PATTERN.finditer(overlap_region):
        semantic_start = candidate + match.end()
        if semantic_start < end:
            return semantic_start

    while candidate < end and candidate > 0 and not text[candidate - 1].isspace():
        candidate += 1
    while candidate < end and text[candidate].isspace():
        candidate += 1
    return candidate if candidate < end else max(start + 1, end - overlap_chars)


def _split_semantically(
    text: str,
    *,
    max_chars: int,
    max_bytes: int,
    overlap_chars: int,
) -> tuple[str, ...]:
    normalized = text.strip()
    if not normalized:
        return ()
    if max_chars <= 0 or max_bytes <= 0:
        raise ValueError("Os limites de chunk devem ser maiores que zero.")
    effective_overlap = min(overlap_chars, max_chars // 5)

    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        hard_end = _maximum_end(
            normalized,
            start,
            max_chars=max_chars,
            max_bytes=max_bytes,
        )
        if hard_end <= start:
            raise ValueError("O limite em bytes não comporta um caractere UTF-8.")
        end = _semantic_end(normalized, start, hard_end)
        chunk = normalized[start:end].strip()
        if not chunk:
            end = hard_end
            chunk = normalized[start:end].strip()
        chunks.append(chunk)
        if end >= len(normalized):
            break
        start = _overlap_start(normalized, start, end, effective_overlap)
    return tuple(chunks)


def _chunk_texts(record: CanonicalMedicalRecord, original_text: str) -> tuple[str, ...]:
    if (
        len(original_text) <= TARGET_KNOWLEDGE_DOCUMENT_CHARS
        and len(original_text.encode("utf-8")) <= MAX_KNOWLEDGE_DOCUMENT_BYTES
    ):
        return (original_text,)

    context = "\n".join(_context_sections(record))
    answer_prefix = f"{context}\nAnswer: "
    available_chars = TARGET_KNOWLEDGE_DOCUMENT_CHARS - len(answer_prefix)
    available_bytes = MAX_KNOWLEDGE_DOCUMENT_BYTES - len(answer_prefix.encode("utf-8"))

    # Cabeçalhos anormalmente grandes não devem gerar centenas de fragmentos minúsculos.
    # Nesse caso raro, o texto completo é dividido sem repetição do contexto.
    if available_chars <= CHUNK_OVERLAP_CHARS or available_bytes <= 4:
        return _split_semantically(
            original_text,
            max_chars=TARGET_KNOWLEDGE_DOCUMENT_CHARS,
            max_bytes=MAX_KNOWLEDGE_DOCUMENT_BYTES,
            overlap_chars=CHUNK_OVERLAP_CHARS,
        )

    answer_chunks = _split_semantically(
        record.answer,
        max_chars=min(TARGET_ANSWER_CHUNK_CHARS, available_chars),
        max_bytes=available_bytes,
        overlap_chars=CHUNK_OVERLAP_CHARS,
    )
    return tuple(f"{answer_prefix}{answer_chunk}" for answer_chunk in answer_chunks)


def _chunk_id(parent_record_id: str, chunk_index: int) -> str:
    if chunk_index == 0:
        return parent_record_id
    return f"{parent_record_id}::chunk::{chunk_index:04d}"


def build_knowledge_documents(
    record: CanonicalMedicalRecord,
    *,
    split: str,
) -> tuple[KnowledgeDocument, ...]:
    """Cria documentos pequenos, rastreáveis e idempotentes para o ChromaDB."""

    original = build_knowledge_document(record, split=split)
    chunk_texts = _chunk_texts(record, original.text)
    chunk_count = len(chunk_texts)
    documents: list[KnowledgeDocument] = []
    for chunk_index, text in enumerate(chunk_texts):
        chunk_bytes = text.encode("utf-8")
        if len(chunk_bytes) > MAX_KNOWLEDGE_DOCUMENT_BYTES:
            raise ValueError("O chunk excedeu o teto de segurança em bytes.")
        metadata = {
            **original.metadata,
            "parent_record_id": record.record_id,
            "chunk_index": chunk_index,
            "chunk_count": chunk_count,
            "chunk_sha256": hashlib.sha256(chunk_bytes).hexdigest(),
            "chunk_utf8_bytes": len(chunk_bytes),
            "chunking_version": CHUNKING_VERSION,
        }
        documents.append(
            KnowledgeDocument(
                record_id=_chunk_id(record.record_id, chunk_index),
                text=text,
                metadata=metadata,
            )
        )
    return tuple(documents)
