# Tech Ingestão

Serviço responsável por ler, validar, transformar e indexar fontes médicas usadas no Tech
Challenge da FIAP. Ele preserva os XMLs do MedQuAD, prepara o contrato canônico e grava
embeddings da OpenAI no ChromaDB. Antes da deduplicação e dos splits, identificadores pessoais
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

## Requisitos

- Python 3.12;
- [uv](https://docs.astral.sh/uv/);
- Docker Desktop para executar o ChromaDB localmente;
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
```

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
é 80/10/10 com seed 42 e nunca separa pares do mesmo documento. A política completa está em
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

## Executar o ChromaDB

O servidor usa uma imagem versionada e um volume persistente:

```powershell
docker compose up -d chroma
uv run tech-ingestao chroma-health
```

Para interromper o contêiner sem apagar os dados:

```powershell
docker compose stop chroma
```

## Configurar embeddings da OpenAI

A chave deve existir apenas no ambiente local. No PowerShell atual:

```powershell
$env:OPENAI_API_KEY = "sua-chave"
```

As demais configurações têm padrões documentados em `.env.example`. O serviço usa
`text-embedding-3-small` com 1536 dimensões e envia os vetores prontos ao ChromaDB; o servidor
vetorial não recebe a chave da OpenAI.

## Indexar o MedQuAD

Comece com um lote pequeno para validar credencial, custo e conectividade:

```powershell
uv run tech-ingestao index --split train --limit 25
```

Depois do smoke test, remova `--limit` para processar todo o split de treino:

```powershell
uv run tech-ingestao index --split train
```

O `record_id` canônico é usado no `upsert`, então uma reexecução atualiza os mesmos registros.
Validação e teste não são indexados por padrão para preservar uma avaliação sem vazamento. O
contrato completo está em [`docs/data/chroma-index.md`](docs/data/chroma-index.md).

## Validar uma consulta semântica

```powershell
uv run tech-ingestao search "What are the symptoms of diabetes?" --limit 5
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
3. criar no `tech-ai` o adaptador conversacional e o treinamento com Unsloth.
