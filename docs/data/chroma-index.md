# Índice semântico no ChromaDB

O ChromaDB armazena vetores gerados localmente pelo modelo ONNX `all-MiniLM-L6-v2`. A coleção
não possui função de embedding própria: o `tech-ingestao` gera os vetores na escrita e o
`tech-ai` usa a mesma integração na consulta.

## Contrato de indexação

- Coleção padrão: `medquad_knowledge_minilm_v1`.
- ID do primeiro trecho: `record_id` canônico, preservado também para registros curtos.
- IDs adicionais: `<record_id>::chunk::<índice com quatro dígitos>`, começando em `0001`.
- Distância: cosseno.
- Modelo: `all-MiniLM-L6-v2`, executado localmente por ONNX Runtime.
- Dimensão: 384, fixada por configuração para detectar incompatibilidades cedo.
- Normalização: vetores normalizados pelo runtime do modelo.
- Texto indexado: `focus` quando presente, `question` e `answer`.
- Metadados: somente valores escalares. Objetos aninhados da procedência são achatados.

## Contrato de chunking

O modelo `all-MiniLM-L6-v2` trunca a entrada em 256 tokens. Por isso o serviço não usa o limite
de 16 KiB do Chroma Cloud como tamanho desejado: ele divide os textos perto da janela útil do
modelo e mantém um teto técnico separado.

| Regra | Valor |
| --- | --- |
| Versão do algoritmo | `semantic-v1` |
| Alvo máximo do documento | 1.000 caracteres, incluindo o cabeçalho |
| Sobreposição | até 180 caracteres, reduzida em chunks pequenos para garantir avanço |
| Teto rígido | 12.288 bytes em UTF-8 |
| Ordem de quebra | parágrafo, linha, fim de frase, espaço e corte por codepoint |

Tópico e pergunta são repetidos em cada trecho da resposta sempre que o cabeçalho cabe no alvo.
Um cabeçalho excepcionalmente grande ativa o fallback que divide o texto completo sem repeti-lo.
Registros que já cabem nos limites preservam exatamente seu ID e texto anteriores.

Todos os documentos recebem os metadados `parent_record_id`, `chunk_index`, `chunk_count`,
`chunk_sha256`, `chunk_utf8_bytes` e `chunking_version`, além da procedência já existente. O
primeiro chunk usa o ID canônico para que o `upsert` substitua uma eventual versão única gravada
antes deste contrato.

Os IDs são idempotentes enquanto o conteúdo e `semantic-v1` permanecerem iguais. Como o dataset
é imutável nesta etapa, o pipeline não faz uma reconciliação destrutiva de chunks excedentes. Ao
alterar limites ou algoritmo, crie uma coleção com novo nome/versionamento e reindexe-a; isso
evita que chunks de contratos diferentes coexistam.

`--limit` limita registros canônicos (pais), não a quantidade final de documentos. O resumo da
indexação separa `indexed_records`, `indexed_documents` e `chunked_records` para deixar esse
efeito explícito.

O split padrão é `train`. Isso permite validar recuperação sem colocar previamente as respostas
de validação e teste na base. Quando a avaliação estiver encerrada, os outros splits podem ser
indexados conscientemente com comandos separados.

## Variáveis

Copie `.env.example` para `.env` e execute os comandos que acessam o banco com
`uv run --env-file .env ...`. O projeto não lê nem versiona automaticamente esse arquivo.

| Variável | Padrão | Obrigatória |
| --- | --- | --- |
| `LOCAL_EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | não |
| `LOCAL_EMBEDDING_DIMENSIONS` | `384` | não |
| `CHROMA_MODE` | `local` | não |
| `CHROMA_HOST` | `localhost` no modo local; `api.trychroma.com` no cloud | não |
| `CHROMA_PORT` | `8000` no modo local; `443` no cloud | não |
| `CHROMA_SSL` | `false` no modo local; `true` no cloud | não |
| `CHROMA_COLLECTION` | `medquad_knowledge_minilm_v1` | não |
| `CHROMA_API_KEY` | sem padrão | somente no modo `cloud` |
| `CHROMA_TENANT` | sem padrão | somente no modo `cloud` |
| `CHROMA_DATABASE` | sem padrão | somente no modo `cloud` |

No modo `local`, a integração usa `chromadb.HttpClient`. No modo `cloud`, usa
`chromadb.CloudClient` com autenticação por API key. A chave deve permanecer apenas no `.env`
local ou no gerenciador de segredos do ambiente de execução.

Na primeira indexação, o modelo ONNX é baixado automaticamente para o cache local do runtime.
Depois disso, a geração dos vetores não precisa de chave nem de chamada a uma API de embeddings;
a conexão com o Chroma Cloud continua exigindo sua própria credencial.

Alterar modelo ou dimensão exige uma nova coleção. Vetores gerados por modelos diferentes não
devem ser misturados, mesmo quando possuírem a mesma dimensão.
