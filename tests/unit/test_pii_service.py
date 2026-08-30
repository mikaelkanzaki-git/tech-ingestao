from __future__ import annotations

import pytest

from tech_ingestao.models.canonical import PiiType
from tech_ingestao.services.pii_service import redact_pii


@pytest.mark.parametrize(
    ("text", "sensitive_value", "placeholder", "pii_type"),
    [
        (
            "Email: jane.doe@example.org.",
            "jane.doe@example.org",
            "[REDACTED_EMAIL]",
            "email_address",
        ),
        ("Call 301-496-5248", "301-496-5248", "[REDACTED_PHONE]", "phone_number"),
        ("SSN: 123-45-6789", "123-45-6789", "[REDACTED_US_SSN]", "us_ssn"),
        ("CPF: 123.456.789-09", "123.456.789-09", "[REDACTED_CPF]", "brazilian_cpf"),
        (
            "MRN: AB-12345",
            "AB-12345",
            "[REDACTED_MEDICAL_RECORD_NUMBER]",
            "medical_record_number",
        ),
        (
            "Patient Name: Jane Mary Doe;",
            "Jane Mary Doe",
            "[REDACTED_PATIENT_NAME]",
            "patient_name",
        ),
        (
            "DOB: 04/23/1980",
            "04/23/1980",
            "[REDACTED_DATE_OF_BIRTH]",
            "date_of_birth",
        ),
        ("TTY: 18005551234", "18005551234", "[REDACTED_PHONE]", "phone_number"),
        ("Contact us at 3015928573", "3015928573", "[REDACTED_PHONE]", "phone_number"),
        ("Call 1-800-4-CANCER", "1-800-4-CANCER", "[REDACTED_PHONE]", "phone_number"),
    ],
)
def test_redact_pii_removes_direct_identifier(
    text: str,
    sensitive_value: str,
    placeholder: str,
    pii_type: PiiType,
) -> None:
    result = redact_pii(text)

    assert sensitive_value not in result.text
    assert placeholder in result.text
    assert pii_type in result.detected_types


def test_redact_pii_does_not_guess_medical_names_or_unlabeled_dates() -> None:
    text = "Parkinson disease was described in 1817. What is your date of birth?"

    result = redact_pii(text)

    assert result.text == text
    assert result.detected_types == ()


def test_redact_pii_reports_each_type_once() -> None:
    result = redact_pii("Email a@example.org or b@example.org")

    assert result.text.count("[REDACTED_EMAIL]") == 2
    assert result.detected_types == ("email_address",)
