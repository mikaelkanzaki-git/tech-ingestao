"""Configurações externas lidas de variáveis de ambiente."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal

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


ChromaMode = Literal["local", "cloud"]


def _chroma_mode(value: str) -> ChromaMode:
    normalized = value.strip().lower()
    if normalized == "local":
        return "local"
    if normalized == "cloud":
        return "cloud"
    raise ConfigurationError("CHROMA_MODE deve ser local ou cloud.")


@dataclass(frozen=True, slots=True)
class ChromaSettings:
    """Conexão local ou gerenciada e coleção usadas pelo ChromaDB."""

    mode: ChromaMode = "local"
    host: str = "localhost"
    port: int = 8000
    collection: str = "medquad_knowledge_minilm_v1"
    ssl: bool = False
    api_key: str | None = field(default=None, repr=False)
    tenant: str | None = None
    database: str | None = None

    @classmethod
    def from_environment(cls, environment: Mapping[str, str] | None = None) -> ChromaSettings:
        values = os.environ if environment is None else environment
        mode = _chroma_mode(values.get("CHROMA_MODE", "local"))
        cloud_mode = mode == "cloud"
        host = values.get(
            "CHROMA_HOST",
            "api.trychroma.com" if cloud_mode else "localhost",
        ).strip()
        collection = values.get(
            "CHROMA_COLLECTION", "medquad_knowledge_minilm_v1"
        ).strip()
        if not host:
            raise ConfigurationError("CHROMA_HOST não pode ser vazio.")
        if not collection:
            raise ConfigurationError("CHROMA_COLLECTION não pode ser vazia.")

        api_key = values.get("CHROMA_API_KEY", "").strip() or None
        tenant = values.get("CHROMA_TENANT", "").strip() or None
        database = values.get("CHROMA_DATABASE", "").strip() or None
        if cloud_mode:
            missing = [
                variable
                for variable, configured in (
                    ("CHROMA_API_KEY", api_key),
                    ("CHROMA_TENANT", tenant),
                    ("CHROMA_DATABASE", database),
                )
                if configured is None
            ]
            if missing:
                raise ConfigurationError(
                    "No modo cloud, configure: " + ", ".join(missing) + "."
                )

        return cls(
            mode=mode,
            host=host,
            port=_positive_integer(
                values.get("CHROMA_PORT", "443" if cloud_mode else "8000"),
                "CHROMA_PORT",
            ),
            collection=collection,
            ssl=_boolean(
                values.get("CHROMA_SSL", "true" if cloud_mode else "false"),
                "CHROMA_SSL",
            ),
            api_key=api_key,
            tenant=tenant,
            database=database,
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
