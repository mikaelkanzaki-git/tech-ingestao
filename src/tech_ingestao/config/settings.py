"""Configurações externas lidas de variáveis de ambiente."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field

from tech_ingestao.errors import ConfigurationError


def _positive_integer(value: str, variable: str) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise ConfigurationError(f"{variable} deve ser um número inteiro.") from error
    if parsed <= 0:
        raise ConfigurationError(f"{variable} deve ser maior que zero.")
    return parsed


def _boolean(value: str, variable: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ConfigurationError(f"{variable} deve ser true ou false.")


@dataclass(frozen=True, slots=True)
class ChromaSettings:
    """Endereço e coleção usados pelo cliente HTTP do ChromaDB."""

    host: str = "localhost"
    port: int = 8000
    collection: str = "medquad_knowledge_v1"
    ssl: bool = False

    @classmethod
    def from_environment(cls, environment: Mapping[str, str] | None = None) -> ChromaSettings:
        values = os.environ if environment is None else environment
        host = values.get("CHROMA_HOST", "localhost").strip()
        collection = values.get("CHROMA_COLLECTION", "medquad_knowledge_v1").strip()
        if not host:
            raise ConfigurationError("CHROMA_HOST não pode ser vazio.")
        if not collection:
            raise ConfigurationError("CHROMA_COLLECTION não pode ser vazia.")
        return cls(
            host=host,
            port=_positive_integer(values.get("CHROMA_PORT", "8000"), "CHROMA_PORT"),
            collection=collection,
            ssl=_boolean(values.get("CHROMA_SSL", "false"), "CHROMA_SSL"),
        )


@dataclass(frozen=True, slots=True)
class OpenAIEmbeddingSettings:
    """Credencial e contrato vetorial usados na API de embeddings."""

    api_key: str = field(repr=False)
    model: str = "text-embedding-3-small"
    dimensions: int = 1536

    @classmethod
    def from_environment(
        cls,
        environment: Mapping[str, str] | None = None,
    ) -> OpenAIEmbeddingSettings:
        values = os.environ if environment is None else environment
        api_key = values.get("OPENAI_API_KEY", "").strip()
        model = values.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small").strip()
        if not api_key:
            raise ConfigurationError(
                "OPENAI_API_KEY não foi definida. Configure-a apenas no ambiente local."
            )
        if not model:
            raise ConfigurationError("OPENAI_EMBEDDING_MODEL não pode ser vazio.")
        return cls(
            api_key=api_key,
            model=model,
            dimensions=_positive_integer(
                values.get("OPENAI_EMBEDDING_DIMENSIONS", "1536"),
                "OPENAI_EMBEDDING_DIMENSIONS",
            ),
        )
