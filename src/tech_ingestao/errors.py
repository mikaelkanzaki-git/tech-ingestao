"""Erros estáveis expostos pelo serviço de ingestão."""


class ScanError(ValueError):
    """Indica que a varredura não pode ser iniciada."""


class DatasetPreparationError(ValueError):
    """Indica que o dataset não pode ser preparado com segurança."""


class ConfigurationError(ValueError):
    """Indica configuração externa ausente ou inválida."""


class EmbeddingError(RuntimeError):
    """Indica falha ao gerar embeddings no provedor configurado."""


class KnowledgeStoreError(RuntimeError):
    """Indica falha de comunicação ou resposta inválida do banco vetorial."""


class KnowledgeIndexError(RuntimeError):
    """Indica que um lote não pôde ser indexado de forma consistente."""
