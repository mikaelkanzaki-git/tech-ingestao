# Diretrizes do repositório

Este projeto segue uma arquitetura em camadas pragmática.

- `models/`: estruturas de dados e enums do domínio.
- `services/`: orquestração e regras da aplicação.
- `integrations/`: leitura de fontes externas e escrita em sistemas externos.
- `config/`: composição e configurações, somente quando houver dependências reais.
- `repositories/`: contratos e implementações de persistência, somente quando houver banco.
- `api/`: transporte HTTP, somente quando a API for criada.

O fluxo de dependências deve apontar para dentro: `runner/api -> services -> models`.
Detalhes de XML, filesystem, ChromaDB e outros SDKs devem permanecer em `integrations/`.
O `tech-ingestao` é o único serviço autorizado a criar ou atualizar a coleção vetorial. O
`tech-ai` consulta essa coleção usando exatamente o mesmo contrato de embeddings.

Não crie camadas ou abstrações sem responsabilidade concreta. Evite pastas genéricas como
`utils`, `helpers`, `ports` e `adapters`; prefira nomes que expressem a responsabilidade.

Antes de entregar mudanças, execute:

```powershell
uv run ruff check .
uv run mypy
uv run pytest
```

Não faça commit, push ou abra pull request sem autorização explícita do usuário.
