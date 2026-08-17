# Tasks

## Etapa atual

ETAPA 2 — Supabase

## Tarefa atual

2.5 — constraints/indexes

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

### Segurança pendente

As migrations de domínio ainda não devem ser aplicadas ao ambiente remoto enquanto a tarefa de RLS da Etapa 2 não estiver concluída. As tabelas ficam em `public` e RLS será obrigatória antes do deploy.

### Tarefas

- [x] 2.1 currencies
- [x] 2.2 markets
- [x] 2.3 exchanges
- [x] 2.4 assets
- [x] 2.5 constraints/indexes

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

Status: ✅ APROVADA

### Tarefa atual

2.3 — exchanges

### 2.3 — exchanges

#### Objetivo

Representar bolsas, venues e locais de negociação pertencentes a um market, mantendo suporte a múltiplos países, moedas, fusos e providers.

#### Critérios de conclusão

- [x] migration criada
- [x] tabela public.exchanges criada
- [x] UUID usado como PK
- [x] exchange vinculada obrigatoriamente a markets
- [x] code validado
- [x] code único dentro de cada market
- [x] name validado
- [x] MIC opcional e validado
- [x] MIC único quando informado
- [x] timezone obrigatório e validado por contrato
- [x] sem trading hours nesta tarefa
- [x] sem assets
- [x] sem seeds
- [x] sem B3/NYSE/NASDAQ hardcoded
- [x] FK sem CASCADE destrutivo
- [x] timestamps com timezone
- [x] is_active
- [x] testes da migration
- [x] ordem das migrations validada
- [x] suíte completa passando
- [x] git diff --check limpo
- [x] nenhuma secret adicionada
- [x] documentação atualizada

## Gate 2.3

Status: ✅ APROVADA

### Tarefa atual

2.4 — assets

### 2.4 — assets

#### Objetivo

Representar instrumentos financeiros de forma canônica, independente de provider e preparada para múltiplos mercados, exchanges e moedas.

#### Critérios de conclusão

- [x] migration criada
- [x] tabela public.assets criada
- [x] UUID como PK
- [x] market_id obrigatório
- [x] exchange_id opcional
- [x] currency_id obrigatório
- [x] symbol obrigatório e validado
- [x] name obrigatório e validado
- [x] asset_type obrigatório e extensível
- [x] ISIN opcional e validado
- [x] ISIN único quando informado
- [x] identidade canônica protegida contra duplicação
- [x] exchange, quando informada, pertence ao mesmo market do asset
- [x] FKs sem CASCADE destrutivo
- [x] is_active
- [x] timestamps timestamptz
- [x] sem provider symbols
- [x] sem cotações
- [x] sem candles
- [x] sem portfolio
- [x] sem seeds
- [x] sem B3/NYSE/NASDAQ/BRL/USD hardcoded
- [x] ordem das migrations validada
- [x] testes adicionados
- [x] suíte completa passando
- [x] git diff --check limpo
- [x] nenhuma secret adicionada
- [x] documentação atualizada

## Gate 2.4

Status: ✅ APROVADA

### Tarefa atual

2.5 — constraints/indexes

### 2.5 — constraints/indexes

#### Objetivo

Auditar constraints e índices do domínio financeiro já modelado, eliminando redundâncias e adicionando somente índices necessários para integridade referencial e padrões de acesso já justificáveis.

#### Critérios de conclusão

- [x] PRIMARY KEYs auditadas
- [x] UNIQUE constraints auditadas
- [x] foreign keys auditadas
- [x] cobertura de índices das FKs documentada
- [x] índices redundantes evitados
- [x] markets.default_currency_id avaliado
- [x] assets.currency_id avaliado
- [x] exchanges.market_id avaliado
- [x] assets.market_id avaliado
- [x] assets exchange/market FK avaliada
- [x] nenhum índice especulativo adicionado
- [x] nova migration criada se necessária
- [x] testes adicionados
- [x] migrations antigas preservadas
- [x] suíte completa passando
- [x] git diff --check limpo
- [x] nenhuma secret adicionada
- [x] documentação atualizada

## Gate 2.5

Status: ✅ APROVADA
