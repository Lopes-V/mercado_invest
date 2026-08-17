# Tasks

## Etapa atual

ETAPA 2 — Supabase

## Tarefa atual

2.1 — currencies
Status: ✅ APROVADA
## Status

EM ANDAMENTO

## Etapa 1 concluída

- [x] 1.1 Bootstrap Python
- [x] 1.2 Configurações
- [x] 1.3 Logging
- [x] 1.4 Supabase
- [x] 1.5 Telegram
- [x] 1.6 /status
- [x] 1.7 Testes de integração
- [x] 1.8 Testes de falha

## Gate da Etapa 1

Status: ✅ APROVADA

### Validações registradas

- [x] Python >= 3.12
- [x] aplicação executável
- [x] pytest funcionando
- [x] 57 testes passando
- [x] Supabase conectado
- [x] Telegram validado end-to-end
- [x] whitelist funcionando
- [x] /start funcionando
- [x] /status funcionando
- [x] polling controlado por offset
- [x] testes de integração
- [x] testes de falha
- [x] .env ignorado
- [x] nenhuma secret versionada

## Etapa 2 — Supabase

### Objetivo

Construir a persistência do domínio financeiro no PostgreSQL/Supabase de forma incremental, auditável e preparada para múltiplos mercados.

### Tarefa atual

2.1 — currencies

### Objetivo da 2.1

Criar a primeira entidade estrutural do domínio: moedas.

### Permitido alterar

- supabase/
- tests/
- docs/
- TASKS.md
- arquivos mínimos necessários à tarefa

### Não implementar

- markets
- exchanges
- assets
- asset_provider_symbols
- market_quotes
- market_candles
- fx_rates
- carteira
- análises
- IA
- scheduler
- alertas
- repositories Python para entidades futuras

### Critérios de conclusão da 2.1

- [ ] migration criada
- [ ] tabela currencies definida
- [ ] UUID usado como identificador
- [ ] código da moeda único
- [ ] código validado
- [ ] precisão decimal validada
- [ ] timestamps com timezone
- [ ] nenhum BRL/USD hardcoded como comportamento do sistema
- [ ] migration revisável
- [ ] testes aplicáveis passando
- [ ] suíte anterior continua passando
- [ ] git diff --check limpo
- [ ] nenhuma secret adicionada
- [ ] documentação atualizada

## Gate 2.1

Status: ❌ NÃO APROVADA
