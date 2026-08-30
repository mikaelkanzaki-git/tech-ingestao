# Política de detecção e redação de PII

O comando `prepare` aplica a política `1.0` antes de calcular hashes, remover duplicidades ou
atribuir documentos aos splits. Portanto, `canonical.jsonl`, os três splits e uma indexação
posterior no ChromaDB recebem somente a versão sanitizada dos campos avaliados.

## Escopo

Os campos de conteúdo `focus`, `question`, `answer` e `synonyms` são avaliados. Metadados de
procedência, como publicador e URL do MedQuAD, permanecem intactos para sustentar atribuição e
explicabilidade. O MedQuAD é um conjunto público de perguntas e respostas, e não um prontuário;
ainda assim, contatos diretos presentes nas respostas são tratados de forma conservadora.

| Tipo | Exemplo de marcador |
| --- | --- |
| E-mail | `[REDACTED_EMAIL]` |
| Telefone e fax | `[REDACTED_PHONE]` |
| Social Security Number (EUA) | `[REDACTED_US_SSN]` |
| CPF formatado | `[REDACTED_CPF]` |
| Número de prontuário rotulado | `[REDACTED_MEDICAL_RECORD_NUMBER]` |
| Nome do paciente rotulado | `[REDACTED_PATIENT_NAME]` |
| Data de nascimento rotulada | `[REDACTED_DATE_OF_BIRTH]` |

Os detectores são expressões determinísticas e versionadas. Nomes próprios em texto livre não
são classificados automaticamente: isso evita marcar epônimos médicos, instituições e autores
como pessoas atendidas. Campos de paciente precisam estar explicitamente rotulados para que
nome, prontuário e data de nascimento sejam substituídos.

## Evidências produzidas

O `manifest.json` registra versão da política, campos avaliados, quantidade de registros por
estado antes e depois da deduplicação, categorias encontradas e pendências. A preparação falha
se algum registro permanecer como `not_evaluated` ou `detected` sem redação.

O `pii-audit.jsonl` contém somente `record_id`, `document_id`, caminho de origem, ID do par,
categorias detectadas e a ação `redacted`. Ele deliberadamente não inclui o trecho original.

## Limites e revisão

Esta política reduz exposição de identificadores diretos e torna a etapa reproduzível, mas não
é, isoladamente, uma certificação de conformidade com LGPD ou HIPAA. Antes de usar fontes
internas, prontuários ou notas clínicas, a equipe deve acrescentar um detector contextual/NER,
amostragem manual e aprovação de um responsável por privacidade. Toda mudança nas regras exige
uma nova versão da política e a regeneração do dataset e dos embeddings.
