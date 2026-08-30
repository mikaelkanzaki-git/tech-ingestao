"""Modelos de resultado e estatísticas da varredura."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class CollectionStats:
    """Contadores acumulados para uma subcoleção do MedQuAD."""

    xml_files_discovered: int = 0
    xml_files_parsed: int = 0
    malformed_files: int = 0
    qa_pairs_total: int = 0
    qa_pairs_accepted: int = 0
    qa_pairs_rejected: int = 0
    missing_question: int = 0
    missing_answer: int = 0
    duplicate_question_occurrences: int = 0
    duplicate_pair_occurrences: int = 0
    question_types: Counter[str] = field(default_factory=Counter)
    categories: Counter[str] = field(default_factory=Counter)

    def as_dict(self) -> dict[str, Any]:
        return {
            "xml_files_discovered": self.xml_files_discovered,
            "xml_files_parsed": self.xml_files_parsed,
            "malformed_files": self.malformed_files,
            "qa_pairs_total": self.qa_pairs_total,
            "qa_pairs_accepted": self.qa_pairs_accepted,
            "qa_pairs_rejected": self.qa_pairs_rejected,
            "missing_question": self.missing_question,
            "missing_answer": self.missing_answer,
            "duplicate_question_occurrences": self.duplicate_question_occurrences,
            "duplicate_pair_occurrences": self.duplicate_pair_occurrences,
            "question_types": dict(sorted(self.question_types.items())),
            "categories": dict(sorted(self.categories.items())),
        }


@dataclass(frozen=True, slots=True)
class ScanResult:
    """Resultado completo da varredura, incluindo itens rejeitados."""

    report: dict[str, Any]
    rejected_records: tuple[dict[str, Any], ...]
