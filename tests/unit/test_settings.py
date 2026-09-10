from __future__ import annotations

import pytest

from tech_ingestao.config.settings import ChromaSettings, LocalEmbeddingSettings
from tech_ingestao.errors import ConfigurationError


def test_chroma_settings_use_defaults_and_parse_values() -> None:
    defaults = ChromaSettings.from_environment({})
    configured = ChromaSettings.from_environment(
        {
            "CHROMA_HOST": "chroma.internal",
            "CHROMA_PORT": "9000",
            "CHROMA_COLLECTION": "medical_v2",
            "CHROMA_SSL": "yes",
        }
    )

    assert defaults == ChromaSettings()
    assert configured == ChromaSettings(
        host="chroma.internal",
        port=9000,
        collection="medical_v2",
        ssl=True,
    )


@pytest.mark.parametrize(
    ("environment", "message"),
    [
        ({"CHROMA_PORT": "zero"}, "número inteiro"),
        ({"CHROMA_PORT": "0"}, "maior que zero"),
        ({"CHROMA_SSL": "maybe"}, "true ou false"),
        ({"CHROMA_HOST": " "}, "HOST"),
        ({"CHROMA_COLLECTION": " "}, "COLLECTION"),
    ],
)
def test_chroma_settings_reject_invalid_values(
    environment: dict[str, str],
    message: str,
) -> None:
    with pytest.raises(ConfigurationError, match=message):
        ChromaSettings.from_environment(environment)


def test_local_embedding_settings_use_fixed_contract() -> None:
    assert LocalEmbeddingSettings.from_environment({}) == LocalEmbeddingSettings(
        model="all-MiniLM-L6-v2",
        dimensions=384,
    )


@pytest.mark.parametrize(
    "environment",
    [
        {"LOCAL_EMBEDDING_MODEL": "other-model"},
        {"LOCAL_EMBEDDING_DIMENSIONS": "768"},
        {"LOCAL_EMBEDDING_DIMENSIONS": "invalid"},
    ],
)
def test_local_embedding_settings_reject_incompatible_contract(
    environment: dict[str, str],
) -> None:
    with pytest.raises(ConfigurationError):
        LocalEmbeddingSettings.from_environment(environment)
