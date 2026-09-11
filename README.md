# Tech Ingestão

Serviço responsável por ler, validar, transformar e indexar fontes médicas usadas no Tech
Challenge da FIAP. Ele preserva os XMLs do MedQuAD, prepara o contrato canônico e grava
embeddings locais no ChromaDB. Antes da deduplicação e dos splits, identificadores pessoais
diretos são auditados e redigidos de forma determinística.

## Arquitetura

O projeto segue o mesmo padrão de camadas pragmáticas usado nos demais serviços:

```text
tech-ingestao/
├── docs/architecture/
├── src/tech_ingestao/
│   ├── integrations/
│   │   ├── chroma/
│   │   ├── embeddings/
│   │   ├── filesystem/
│   │   └── medquad/
│   ├── config/
│   ├── models/
│   ├── repositories/
│   ├── services/
│   ├── errors.py
│   └── runner.py
└── tests/unit/
```

A justificativa de cada camada está em
[`docs/architecture/pragmatic-layered-architecture.md`](docs/architecture/pragmatic-layered-architecture.md).

Para quem vem de Java/Spring: `models` corresponde a DTOs e tipos do domínio, `services` aos
casos de uso, `repositories` aos contratos de persistência, `integrations` aos clients externos,
`config/dependencies.py` a uma classe `@Configuration` e `runner.py` à entrada da aplicação.

## Requisitos

- Python 3.12;
- [uv](https://docs.astral.sh/uv/);
- Docker Desktop apenas se você optar pelo ChromaDB local;
- repositórios `MedQuAD` e `tech-ingestao` clonados lado a lado.

```text
tech-3/
├── MedQuAD/
└── tech-ingestao/
```

## Configuração

A partir do diretório `tech-ingestao`:

```powershell
uv sync --dev
Copy-Item .env.example .env
```

O arquivo `.env` real é ignorado pelo Git. O projeto não o carrega implicitamente; nos comandos
que acessam o ChromaDB, use `uv run --env-file .env ...`. Não coloque a chave do Chroma Cloud
no README, em commits ou em mensagens de diagnóstico.

## Executar a varredura

```powershell
uv run tech-ingestao scan
```

Os caminhos também podem ser informados explicitamente:

```powershell
uv run tech-ingestao scan `
  --source "..\MedQuAD" `
  --output "artifacts\scan"
```

O comando cria:

- `artifacts/scan/report.json`: estatísticas globais e por coleção;
- `artifacts/scan/rejected.jsonl`: um registro por arquivo inválido ou par de
  pergunta/resposta rejeitado.

Um par é aceito nesta fase quando possui pergunta e resposta não vazias. Duplicidades exatas,
após normalização de espaços e capitalização, são apenas contabilizadas. A política de remoção
será definida na etapa de curadoria.

## Schema canônico

O contrato que desacopla o MedQuAD dos formatos futuros de fine-tuning e ChromaDB está descrito
em [`docs/data/canonical-schema.md`](docs/data/canonical-schema.md). O JSON Schema versionado
fica em [`schemas/canonical-medical-record.schema.json`](schemas/canonical-medical-record.schema.json).

## Preparar JSONL e splits

```powershell
uv run tech-ingestao prepare
```

O comando gera `canonical.jsonl`, `train.jsonl`, `validation.jsonl`, `test.jsonl`,
`duplicates.jsonl`, `pii-audit.jsonl` e `manifest.json` em `artifacts/dataset`. A divisão padrão
é 80/10/10 com seed 42, nunca separa pares do mesmo documento e mantém perguntas normalizadas
equivalentes no mesmo split. A política completa está em
[`docs/data/dataset-splits.md`](docs/data/dataset-splits.md).

## Privacidade e anonimização

A sanitização ocorre antes do hash de conteúdo, da deduplicação e dos splits. E-mails,
telefones, SSN, CPF e campos explicitamente rotulados como nome do paciente, data de nascimento
ou prontuário são substituídos por marcadores. O relatório de auditoria contém somente IDs de
registros e tipos detectados; os valores originais não são gravados nele.

A política, seus limites e o procedimento de revisão estão documentados em
[`docs/data/pii-policy.md`](docs/data/pii-policy.md). Ela fornece uma proteção reproduzível para
identificadores diretos, mas não deve ser apresentada isoladamente como certificação de
conformidade com LGPD ou HIPAA.

## Conectar ao ChromaDB

### Chroma Cloud

Para manter a base disponível sem iniciar o Docker local, configure no `.env` as credenciais
copiadas da tela **Connect** do seu banco no Chroma Cloud:

```dotenv
CHROMA_MODE=cloud
CHROMA_HOST=api.trychroma.com
CHROMA_PORT=443
CHROMA_SSL=true
CHROMA_API_KEY=chroma_key_...
CHROMA_TENANT=seu-tenant-id
CHROMA_DATABASE=seu-database
CHROMA_COLLECTION=medquad_knowledge_minilm_v1
```

`CHROMA_API_KEY`, `CHROMA_TENANT` e `CHROMA_DATABASE` são obrigatórias no modo `cloud`. Para a
região padrão, host, porta e SSL já assumem respectivamente `api.trychroma.com`, `443` e `true`,
mas mantê-los explícitos torna a configuração mais fácil de auditar.

Valide a autenticação e o acesso à coleção:

```powershell
uv run --env-file .env tech-ingestao chroma-health
```

O Chroma Cloud hospeda o banco vetorial. Este comando e a indexação ainda executam o código do
`tech-ingestao` na máquina atual; publicar esse processo como serviço ou job é uma etapa
separada.

### ChromaDB local (opcional)

O servidor usa uma imagem versionada e um volume persistente:

```powershell
docker compose up -d chroma
uv run --env-file .env tech-ingestao chroma-health
```

Para interromper o contêiner sem apagar os dados:

```powershell
docker compose stop chroma
```

## Embeddings locais

O serviço usa `all-MiniLM-L6-v2` por ONNX Runtime, com vetores normalizados de 384 dimensões.
Não é necessária chave da OpenAI nem chamada a outro serviço. O modelo é baixado automaticamente
na primeira indexação e reutilizado do cache local nas execuções seguintes.

A coleção padrão é `medquad_knowledge_minilm_v1`. O `tech-ai` usa exatamente o mesmo modelo,
dimensão e coleção para pesquisar os documentos.

## Indexar o MedQuAD

Comece com um lote pequeno para validar o download do modelo e a conectividade:

```powershell
uv run --env-file .env tech-ingestao index --split train --limit 25
```

Depois do smoke test, remova `--limit` para processar todo o split de treino:

```powershell
uv run --env-file .env tech-ingestao index --split train
```

Antes do embedding, respostas extensas são divididas em trechos semânticos próximos da janela
de 256 tokens do MiniLM. Cada trecho tem alvo de até 1.000 caracteres no total, repete tópico e
pergunta quando possível, conserva até 180 caracteres de sobreposição e nunca ultrapassa o teto de
segurança de 12 KiB em UTF-8. Isso também mantém cada documento abaixo da cota de 16 KiB do
Chroma Cloud.

O primeiro trecho preserva o `record_id` canônico; os demais recebem IDs determinísticos como
`<record_id>::chunk::0001`. Assim uma reexecução faz `upsert` nos mesmos itens. Metadados como
`parent_record_id`, `chunk_index`, `chunk_count`, `chunk_sha256` e `chunk_utf8_bytes` mantêm a
rastreabilidade. O `--limit` conta registros canônicos de origem, portanto 25 registros podem
produzir mais de 25 documentos na coleção.

Validação e teste não são indexados por padrão para preservar uma avaliação sem vazamento. O
contrato completo está em [`docs/data/chroma-index.md`](docs/data/chroma-index.md).

## Validar uma consulta semântica

```powershell
uv run --env-file .env tech-ingestao search "What are the symptoms of diabetes?" --limit 5
```

Cada resultado inclui distância, texto recuperado e metadados de procedência como publicador,
URL e revisão do MedQuAD.

## Validar o projeto

```powershell
uv run ruff check .
uv run mypy
uv run pytest
```

## Fonte dos dados

O MedQuAD contém perguntas e respostas médicas coletadas de sites do NIH e é
distribuído sob a licença CC BY 4.0. O dataset não é copiado para este
repositório: sua origem e revisão Git são registradas no relatório de varredura.

- Repositório: https://github.com/abachaa/MedQuAD
- Artigo: https://doi.org/10.1186/s12859-019-3119-4

## Próximas etapas

1. Revisar os achados do relatório de PII antes de liberar uma nova versão do dataset;
2. reindexar o split de treino no ChromaDB quando o conteúdo sanitizado for aprovado;
3. usar no `tech-fine-tuning` o adaptador conversacional e o treinamento com Unsloth.
