# Arquitetura em camadas pragmática

O `tech-ingestao` organiza o pipeline por responsabilidade concreta. A estrutura cresce
conforme novos comportamentos são implementados, sem antecipar camadas vazias.

```text
src/tech_ingestao/
├── config/
│   ├── dependencies.py
│   └── settings.py
├── errors.py
├── runner.py
├── models/
│   ├── canonical.py
│   ├── dataset.py
│   ├── medquad.py
│   ├── knowledge.py
│   └── scan.py
├── repositories/
│   └── knowledge_repository.py
├── services/
│   ├── canonicalization_service.py
│   ├── dataset_preparation_service.py
│   ├── embedding_service.py
│   ├── knowledge_index_service.py
│   └── scan_service.py
└── integrations/
    ├── chroma/
    │   └── knowledge_repository.py
    ├── embeddings/
    │   └── openai.py
    ├── filesystem/
    │   └── report_writer.py
    └── medquad/
        ├── git_metadata.py
        └── reader.py
```

## Responsabilidades atuais

- `runner.py`: interpreta argumentos e compõe a execução local.
- `services/scan_service.py`: aplica as regras de aceitação, contabiliza qualidade e monta o
  relatório.
- `integrations/medquad/reader.py`: conhece a estrutura XML específica do MedQuAD.
- `integrations/medquad/git_metadata.py`: identifica repositório e revisão da fonte.
- `integrations/filesystem/report_writer.py`: persiste JSON e JSONL.
- `models/`: representa documentos do MedQuAD e resultados da varredura.
- `models/canonical.py`: define o contrato estável consumido pelas próximas etapas.
- `services/canonicalization_service.py`: traduz o formato MedQuAD para o schema canônico.
- `services/dataset_preparation_service.py`: deduplica, divide e audita o dataset canônico.
- `services/knowledge_index_service.py`: formata o texto recuperável, coordena lotes e busca.
- `repositories/knowledge_repository.py`: contrato de persistência vetorial consumido pelo
  serviço, sem expor o SDK.
- `integrations/chroma/knowledge_repository.py`: implementa `upsert`, consulta e contagem pelo
  cliente HTTP do ChromaDB.
- `integrations/embeddings/openai.py`: solicita embeddings explícitos à OpenAI; o banco não
  conhece a credencial nem o provedor.
- `config/`: valida variáveis de ambiente e compõe as integrações na borda da aplicação.

## Evolução prevista

`api/` só será necessário se este serviço expuser transporte HTTP. A integração do ChromaDB
permanece substituível porque serviços e modelos dependem apenas do contrato em `repositories/`.
