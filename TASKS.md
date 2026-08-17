# Tasks

## Etapa atual

ETAPA 2 — Supabase

## Tarefa atual

2.2 — markets

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

### Tarefas

- [x] 2.1 currencies
- [ ] 2.2 markets

## Gate 2.1

Status: ✅ APROVADA

### Tarefa atual

2.2 — markets

### 2.2 — markets

#### Objetivo

Representar mercados/jurisdições financeiras suportados pelo sistema sem acoplamento exclusivo ao Brasil.

#### Critérios de conclusão

- [x] migration criada
- [x] tabela public.markets criada
- [x] UUID usado como PK
- [x] code único e validado
- [x] name validado
- [x] country_code opcional e validado
- [x] default_currency_id referenciando currencies
- [x] mercado pode existir sem moeda padrão
- [x] timestamps com timezone
- [x] is_active
- [x] nenhuma informação de exchange adicionada
- [x] nenhum BR/B3/US hardcoded como regra
- [x] sem seeds
- [x] testes da migration
- [x] suíte completa passando
- [x] git diff --check limpo
- [x] nenhuma secret adicionada
- [x] documentação atualizada

## Gate 2.2

Status: ⚠ AGUARDANDO REVISÃO EXTERNA
