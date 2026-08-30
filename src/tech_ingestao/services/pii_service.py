"""Detecção e redação determinística de identificadores pessoais diretos."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from tech_ingestao.models.canonical import CanonicalMedicalRecord, PiiType
from tech_ingestao.models.dataset import PiiAuditFinding

PII_POLICY_VERSION = "1.0"
PII_SCANNED_FIELDS = ("focus", "question", "answer", "synonyms")


@dataclass(frozen=True, slots=True)
class PiiRedaction:
    """Texto sanitizado e tipos de identificador encontrados, sem guardar o valor original."""

    text: str
    detected_types: tuple[PiiType, ...]


@dataclass(frozen=True, slots=True)
class _PiiRule:
    pii_type: PiiType
    placeholder: str
    pattern: re.Pattern[str]


_PII_TYPE_ORDER: tuple[PiiType, ...] = (
    "email_address",
    "phone_number",
    "us_ssn",
    "brazilian_cpf",
    "medical_record_number",
    "patient_name",
    "date_of_birth",
)

_RULES: tuple[_PiiRule, ...] = (
    _PiiRule(
        pii_type="email_address",
        placeholder="[REDACTED_EMAIL]",
        pattern=re.compile(
            r"(?P<value>(?<![\w.+-])[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,63}(?![\w-]))",
            re.IGNORECASE,
        ),
    ),
    _PiiRule(
        pii_type="us_ssn",
        placeholder="[REDACTED_US_SSN]",
        pattern=re.compile(
            r"(?P<value>(?<!\d)(?!000|666|9\d{2})\d{3}-(?!00)\d{2}-(?!0000)\d{4}(?!\d))"
        ),
    ),
    _PiiRule(
        pii_type="brazilian_cpf",
        placeholder="[REDACTED_CPF]",
        pattern=re.compile(r"(?P<value>(?<!\d)\d{3}\.\d{3}\.\d{3}-\d{2}(?!\d))"),
    ),
    _PiiRule(
        pii_type="medical_record_number",
        placeholder="[REDACTED_MEDICAL_RECORD_NUMBER]",
        pattern=re.compile(
            r"(?P<prefix>\b(?:medical\s+record(?:\s+(?:number|no\.?|#))?|mrn|"
            r"patient\s+(?:id|identifier))\s*(?::|=|#|\bis\b)\s*)"
            r"(?P<value>[A-Z0-9][A-Z0-9-]{3,31})",
            re.IGNORECASE,
        ),
    ),
    _PiiRule(
        pii_type="patient_name",
        placeholder="[REDACTED_PATIENT_NAME]",
        pattern=re.compile(
            r"(?P<prefix>(?i:\b(?:patient\s+name|name\s+of\s+(?:the\s+)?patient)"
            r"\s*[:=-]\s*))"
            r"(?P<value>[A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ'-]+"
            r"(?:\s+[A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ'-]+){1,5})"
            r"(?=\s*(?:[;,|]|\b(?i:DOB|date\s+of\s+birth|MRN|medical\s+record)\b|$))"
        ),
    ),
    _PiiRule(
        pii_type="date_of_birth",
        placeholder="[REDACTED_DATE_OF_BIRTH]",
        pattern=re.compile(
            r"(?P<prefix>\b(?:date\s+of\s+birth|dob)\s*[:=-]\s*)"
            r"(?P<value>(?:\d{4}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|"
            r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
            r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|"
            r"Dec(?:ember)?)\.?\s+\d{1,2},?\s+\d{4}))",
            re.IGNORECASE,
        ),
    ),
    _PiiRule(
        pii_type="phone_number",
        placeholder="[REDACTED_PHONE]",
        pattern=re.compile(
            r"(?P<value>(?<![\w])(?:\+?1[\s.-]?)?(?:\(\d{3}\)|\d{3})"
            r"[\s.-]\d{3}[\s.-]\d{4}(?![\w]))"
        ),
    ),
    _PiiRule(
        pii_type="phone_number",
        placeholder="[REDACTED_PHONE]",
        pattern=re.compile(
            r"(?P<value>(?<![\w])1[\s.-]?(?:800|833|844|855|866|877|888)"
            r"(?:[\s.-]?[A-Z0-9]){7,11}(?![\w]))",
            re.IGNORECASE,
        ),
    ),
    _PiiRule(
        pii_type="phone_number",
        placeholder="[REDACTED_PHONE]",
        pattern=re.compile(r"(?P<value>(?<!\d)1(?:800|833|844|855|866|877|888)\d{7}(?!\d))"),
    ),
    _PiiRule(
        pii_type="phone_number",
        placeholder="[REDACTED_PHONE]",
        pattern=re.compile(r"(?P<value>(?<!\d)1?[2-9]\d{2}[2-9]\d{6}(?!\d))"),
    ),
    _PiiRule(
        pii_type="phone_number",
        placeholder="[REDACTED_PHONE]",
        pattern=re.compile(
            r"(?P<prefix>\b(?:phone|telephone|tel|mobile|cell|fax|tty)\s*:?[ \t]*)"
            r"(?P<value>\+?\d{7,15})(?!\d)",
            re.IGNORECASE,
        ),
    ),
    _PiiRule(
        pii_type="phone_number",
        placeholder="[REDACTED_PHONE]",
        pattern=re.compile(
            r"(?P<prefix>\bcall(?:ing)?\s+)(?P<value>\+?\d{10,15})(?!\d)",
            re.IGNORECASE,
        ),
    ),
)


def _replacement(
    rule: _PiiRule,
    detected: set[PiiType],
) -> Callable[[re.Match[str]], str]:
    def replace(match: re.Match[str]) -> str:
        detected.add(rule.pii_type)
        return f"{match.groupdict().get('prefix') or ''}{rule.placeholder}"

    return replace


def redact_pii(text: str) -> PiiRedaction:
    """Substitui identificadores reconhecidos sem persistir seus valores no resultado."""

    redacted = text
    detected: set[PiiType] = set()
    for rule in _RULES:
        redacted = rule.pattern.sub(_replacement(rule, detected), redacted)

    ordered_types = tuple(pii_type for pii_type in _PII_TYPE_ORDER if pii_type in detected)
    return PiiRedaction(text=redacted, detected_types=ordered_types)


def build_pii_audit(records: Iterable[CanonicalMedicalRecord]) -> dict[str, Any]:
    """Agrega evidências da política sem incluir o conteúdo sensível encontrado."""

    statuses: Counter[str] = Counter()
    records_by_type: Counter[str] = Counter()
    total = 0
    for record in records:
        total += 1
        statuses[record.curation.pii_status] += 1
        records_by_type.update(record.curation.pii_types)

    unresolved = statuses["not_evaluated"] + statuses["detected"]
    return {
        "policy_version": PII_POLICY_VERSION,
        "strategy": "deterministic_direct_identifier_redaction",
        "fields_scanned": list(PII_SCANNED_FIELDS),
        "records_scanned": total,
        "records_by_status": dict(sorted(statuses.items())),
        "records_by_detected_type": dict(sorted(records_by_type.items())),
        "records_redacted": statuses["redacted"],
        "unresolved_records": unresolved,
    }


def build_pii_findings(
    records: Iterable[CanonicalMedicalRecord],
) -> tuple[PiiAuditFinding, ...]:
    """Cria um índice de achados redigidos sem repetir os valores identificados."""

    return tuple(
        PiiAuditFinding(
            record_id=record.record_id,
            document_id=record.document_id,
            source_relative_path=record.source.relative_path,
            upstream_pair_id=record.source.upstream_pair_id,
            detected_types=record.curation.pii_types,
        )
        for record in records
        if record.curation.pii_status == "redacted"
    )
