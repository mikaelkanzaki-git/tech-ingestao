# Índice semântico no ChromaDB

O ChromaDB armazena vetores gerados localmente pelo modelo ONNX `all-MiniLM-L6-v2`. A coleção
não possui função de embedding própria: o `tech-ingestao` gera os vetores na escrita e o
`tech-ai` usa a mesma integração na consulta.

## Contrato de indexação

- Coleção padrão: `medquad_knowledge_minilm_v1`.
- ID do registro: `record_id` canônico; repetir o comando atualiza o mesmo item via `upsert`.
- Distância: cosseno.
- Modelo: `all-MiniLM-L6-v2`, executado localmente por ONNX Runtime.
- Dimensão: 384, fixada por configuração para detectar incompatibilidades cedo.
- Normalização: vetores normalizados pelo runtime do modelo.
- Texto indexado: `focus` quando presente, `question` e `answer`.
- Metadados: somente valores escalares. Objetos aninhados da procedência são achatados.

O split padrão é `train`. Isso permite validar recuperação sem colocar previamente as respostas
de validação e teste na base. Quando a avaliação estiver encerrada, os outros splits podem ser
indexados conscientemente com comandos separados.

## Variáveis

Copie `.env.example` apenas como referência e configure os valores na sessão do terminal. O
projeto não lê nem versiona automaticamente um arquivo `.env`.

| Variável | Padrão | Obrigatória |
| --- | --- | --- |
| `LOCAL_EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | não |
| `LOCAL_EMBEDDING_DIMENSIONS` | `384` | não |
| `CHROMA_HOST` | `localhost` | não |
| `CHROMA_PORT` | `8000` | não |
| `CHROMA_SSL` | `false` | não |
| `CHROMA_COLLECTION` | `medquad_knowledge_minilm_v1` | não |

Na primeira indexação, o modelo ONNX é baixado automaticamente para o cache local do ChromaDB.
Depois disso, a geração dos vetores não precisa de chave nem de chamada a uma API externa.

Alterar modelo ou dimensão exige uma nova coleção. Vetores gerados por modelos diferentes não
devem ser misturados, mesmo quando possuírem a mesma dimensão.
