# Índice semântico no ChromaDB

O ChromaDB armazena vetores gerados explicitamente pela OpenAI. A coleção não possui função
de embedding própria: isso evita configuração duplicada no servidor e deixa a troca de
provedor restrita à integração de embeddings.

## Contrato de indexação

- Coleção padrão: `medquad_knowledge_v1`.
- ID do registro: `record_id` canônico; repetir o comando atualiza o mesmo item via `upsert`.
- Distância: cosseno.
- Modelo padrão: `text-embedding-3-small`.
- Dimensão padrão: 1536, fixada por configuração para detectar incompatibilidades cedo.
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
| `OPENAI_API_KEY` | sem padrão | sim para `index` e `search` |
| `OPENAI_EMBEDDING_MODEL` | `text-embedding-3-small` | não |
| `OPENAI_EMBEDDING_DIMENSIONS` | `1536` | não |
| `CHROMA_HOST` | `localhost` | não |
| `CHROMA_PORT` | `8000` | não |
| `CHROMA_SSL` | `false` | não |
| `CHROMA_COLLECTION` | `medquad_knowledge_v1` | não |

Alterar modelo ou dimensão exige uma nova coleção. Vetores de dimensões diferentes não podem
ser consultados na mesma coleção.
