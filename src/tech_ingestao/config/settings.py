"""Configurações externas lidas de variáveis de ambiente."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

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
    collection: str = "medquad_knowledge_minilm_v1"
    ssl: bool = False

    @classmethod
    def from_environment(cls, environment: Mapping[str, str] | None = None) -> ChromaSettings:
        values = os.environ if environment is None else environment
        host = values.get("CHROMA_HOST", "localhost").strip()
        collection = values.get(
            "CHROMA_COLLECTION", "medquad_knowledge_minilm_v1"
        ).strip()
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
class LocalEmbeddingSettings:
    """Contrato do modelo ONNX executado localmente."""

    model: str = "all-MiniLM-L6-v2"
    dimensions: int = 384

    @classmethod
    def from_environment(
        cls,
        environment: Mapping[str, str] | None = None,
    ) -> LocalEmbeddingSettings:
        values = os.environ if environment is None else environment
        model = values.get("LOCAL_EMBEDDING_MODEL", "all-MiniLM-L6-v2").strip()
        dimensions = _positive_integer(
            values.get("LOCAL_EMBEDDING_DIMENSIONS", "384"),
            "LOCAL_EMBEDDING_DIMENSIONS",
        )
        if model != "all-MiniLM-L6-v2":
            raise ConfigurationError(
                "LOCAL_EMBEDDING_MODEL deve ser 'all-MiniLM-L6-v2' nesta versão."
            )
        if dimensions != 384:
            raise ConfigurationError(
                "LOCAL_EMBEDDING_DIMENSIONS deve ser 384 para all-MiniLM-L6-v2."
            )
        return cls(model=model, dimensions=dimensions)
