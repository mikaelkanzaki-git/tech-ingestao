# Schema canônico de dados médicos

O schema `CanonicalMedicalRecord` representa um par de pergunta e resposta aceito sem acoplar
o domínio ao XML do MedQuAD, ao formato de fine-tuning da OpenAI ou ao payload do ChromaDB.
A versão atual é `1.1`.

O contrato executável está em
[`schemas/canonical-medical-record.schema.json`](../../schemas/canonical-medical-record.schema.json).

## Decisões de modelagem

- Cada registro corresponde a um par de pergunta e resposta válido.
- `record_id` é um UUIDv5 determinístico para identificar o par.
- `document_id` é compartilhado por todos os pares do mesmo XML e será a chave de agrupamento
  das divisões de treino, validação e teste. Isso impede vazamento entre pares do mesmo documento.
- `content_sha256` permite detectar conteúdo exatamente duplicado sem usar o ID de origem.
- A procedência preserva coleção, arquivo, IDs originais, publicador, URL, repositório, revisão e
  licença. Esses campos sustentam atribuição CC BY 4.0 e fontes nas respostas do assistente.
- `pii_status` é definido como `not_detected` depois da verificação ou `redacted` quando pelo
  menos um identificador direto foi substituído. `pii_types` registra somente as categorias,
  nunca os valores encontrados.
- Valores ausentes são `null`; o texto sentinela `"unknown"` fica restrito aos relatórios
  agregados e não contamina o dado canônico.

## Campos principais

| Campo | Finalidade |
| --- | --- |
| `schema_version` | Permite evoluir o contrato sem misturar formatos incompatíveis. |
| `record_id` | Identidade estável do par para JSONL, ChromaDB e auditoria. |
| `document_id` | Unidade indivisível usada para evitar vazamento entre splits. |
| `content_sha256` | Identificação de duplicidade exata de pergunta e resposta. |
| `question`, `answer` | Conteúdo supervisionado para fine-tuning e recuperação. |
| `focus`, `category`, `question_type` | Contexto temático e clínico. |
| `synonyms`, `umls_*` | Anotações médicas úteis para busca e avaliação. |
| `source` | Procedência completa e fonte explicável. |
| `curation` | Estado de aceitação, PII, tipos detectados, transformações e alertas. |

## Exemplo reduzido

```json
{
  "schema_version": "1.1",
  "record_id": "55f268c4-8570-50a4-b41a-8ce1c66dbfb9",
  "document_id": "24d9259a-c85a-5197-ac18-3f574bb28972",
  "content_sha256": "d9b0c5d2898d5caecffb8dc848d52f9b22df05ab8be5f470f958d74c330e51f2",
  "language": "en",
  "focus": "Holmes-Adie",
  "category": null,
  "question_type": "information",
  "question": "what is holmes-adie syndrome ?",
  "answer": "Holmes-Adie syndrome is a neurological disorder...",
  "synonyms": [],
  "umls_cuis": [],
  "umls_semantic_types": [],
  "umls_semantic_groups": [],
  "source": {
    "dataset": "MedQuAD",
    "collection": "6_NINDS_QA",
    "relative_path": "6_NINDS_QA/0000007.xml",
    "upstream_repository": "https://github.com/abachaa/MedQuAD.git",
    "upstream_revision": "577bd37b96c02d1833b2c9eed2de9f96964e96cb",
    "upstream_document_id": "0000007",
    "upstream_pair_id": "1",
    "upstream_question_id": "0000007-1",
    "publisher": "NINDS",
    "url": "http://www.ninds.nih.gov/disorders/holmes_adie/holmes_adie.htm",
    "license": "CC-BY-4.0"
  },
  "curation": {
    "status": "accepted",
    "pii_status": "not_detected",
    "pii_types": [],
    "transformations": ["whitespace_normalized"],
    "quality_flags": []
  }
}
```

## Variações do MedQuAD cobertas

O leitor reconhece os elementos predominantes (`Document`, `QAPair`, `Question`, `Answer`) e
o formato legado encontrado em quatro arquivos do NINDS (`doc`, `pair`, `question`, `answer`).
Também trata `DiseaseFile`, atributos alternativos de identidade e anotações UMLS simples ou
agrupadas.
