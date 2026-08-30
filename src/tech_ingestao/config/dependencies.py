"""Composição explícita das integrações usadas pela linha de comando."""

from __future__ import annotations

from tech_ingestao.config.settings import ChromaSettings, OpenAIEmbeddingSettings
from tech_ingestao.integrations.chroma.knowledge_repository import ChromaKnowledgeRepository
from tech_ingestao.integrations.embeddings.openai import OpenAIEmbeddingService
from tech_ingestao.services.knowledge_index_service import KnowledgeIndexService


def build_knowledge_index_service() -> KnowledgeIndexService:
    """Monta o fluxo OpenAI -> serviço -> ChromaDB a partir do ambiente."""

    embedding_service = OpenAIEmbeddingService(OpenAIEmbeddingSettings.from_environment())
    repository = ChromaKnowledgeRepository(ChromaSettings.from_environment())
    return KnowledgeIndexService(embedding_service, repository)


def build_chroma_repository() -> ChromaKnowledgeRepository:
    """Monta somente o repositório para diagnósticos que não usam a OpenAI."""

    return ChromaKnowledgeRepository(ChromaSettings.from_environment())
