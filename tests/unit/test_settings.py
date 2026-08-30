from __future__ import annotations

import pytest

from tech_ingestao.config.settings import ChromaSettings, OpenAIEmbeddingSettings
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


def test_openai_settings_require_key_and_hide_it_from_repr() -> None:
    with pytest.raises(ConfigurationError, match="OPENAI_API_KEY"):
        OpenAIEmbeddingSettings.from_environment({})

    settings = OpenAIEmbeddingSettings.from_environment(
        {
            "OPENAI_API_KEY": "secret-key",
            "OPENAI_EMBEDDING_MODEL": "text-embedding-3-small",
            "OPENAI_EMBEDDING_DIMENSIONS": "256",
        }
    )

    assert settings.dimensions == 256
    assert "secret-key" not in repr(settings)


def test_openai_settings_reject_empty_model() -> None:
    with pytest.raises(ConfigurationError, match="MODEL"):
        OpenAIEmbeddingSettings.from_environment(
            {"OPENAI_API_KEY": "secret-key", "OPENAI_EMBEDDING_MODEL": " "}
        )
