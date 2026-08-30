# Preparação dos JSONL e splits

O comando `prepare` transforma os pares aceitos no schema canônico, redige identificadores
diretos, remove duplicidades exatas e gera divisões reproduzíveis para treino, validação e teste.

```powershell
uv run tech-ingestao prepare
```

## Política padrão

- Treino: 80%.
- Validação: 10%.
- Teste: 10%.
- Seed: `42`.
- Privacidade: redação determinística antes de calcular `content_sha256`.
- Unidade indivisível: `document_id`.
- Deduplicação: `content_sha256`, mantendo o primeiro registro pela ordem estável da fonte.

Cada `document_id` recebe um valor determinístico calculado por SHA-256 a partir da seed. O
valor define seu split por limiares de proporção. Todos os pares daquele documento seguem para
o mesmo arquivo. Como a atribuição não depende da posição do documento na coleção, adicionar
novos documentos não movimenta os registros já existentes.

As proporções são alvos, não contagens exatas: documentos possuem quantidades diferentes de
perguntas e respostas. O manifesto registra os números efetivamente obtidos.

## Artefatos

| Arquivo | Conteúdo |
| --- | --- |
| `canonical.jsonl` | Todos os registros canônicos após deduplicação. |
| `train.jsonl` | Registros atribuídos ao treino. |
| `validation.jsonl` | Registros atribuídos à validação. |
| `test.jsonl` | Registros reservados para avaliação final. |
| `duplicates.jsonl` | Relação entre cada registro removido e o equivalente mantido. |
| `pii-audit.jsonl` | Registro, origem e categorias redigidas, sem armazenar os valores. |
| `manifest.json` | Configuração, origem, contagens por split e verificações de vazamento. |

Os JSONL preservam o schema canônico. Eles ainda não usam o formato `messages` de um provedor
de fine-tuning: essa conversão será responsabilidade do `tech-fine-tuning`, sem acoplar a
ingestão a um modelo ou provedor.

## Invariantes verificadas

O comando falha se detectar qualquer uma destas condições:

- um `document_id` em mais de um split;
- um `record_id` em mais de um split;
- o mesmo `content_sha256` em mais de um split.

O último item é garantido pela deduplicação global antes da divisão.

## Configuração alternativa

```powershell
uv run tech-ingestao prepare `
  --source "..\MedQuAD" `
  --output "artifacts\dataset" `
  --train-ratio 0.8 `
  --validation-ratio 0.1 `
  --test-ratio 0.1 `
  --seed 42
```

As três proporções devem ser maiores que zero, menores que um e somar exatamente um dentro da
tolerância numérica definida pelo serviço.
