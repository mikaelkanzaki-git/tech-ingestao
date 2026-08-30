"""Estruturas normalizadas lidas dos documentos do MedQuAD."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MedQuADQuestionAnswer:
    """Pergunta e resposta extraídas de um elemento `QAPair`."""

    position: int
    pair_id: str | None
    question_id: str | None
    question_type: str | None
    question: str
    answer: str


@dataclass(frozen=True, slots=True)
class MedQuADDocument:
    """Conteúdo relevante de um documento XML do MedQuAD."""

    document_id: str | None
    publisher: str | None
    source_url: str | None
    focus: str | None
    category: str | None
    synonyms: tuple[str, ...]
    umls_cuis: tuple[str, ...]
    umls_semantic_types: tuple[str, ...]
    umls_semantic_groups: tuple[str, ...]
    pairs: tuple[MedQuADQuestionAnswer, ...]


@dataclass(frozen=True, slots=True)
class GitSourceMetadata:
    """Origem e revisão Git usadas na varredura."""

    repository: str | None
    revision: str | None
