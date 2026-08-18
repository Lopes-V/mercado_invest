# Tasks

## Etapa atual

ETAPA 2 — Supabase

## Tarefa atual

2.8 — persistence tests

## Status

CONCLUÍDA

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

### Segurança de deploy

As migrations de domínio foram aplicadas e validadas remotamente por ferramenta conectada. As tabelas em `public` usam RLS deny-by-default; a service role é restrita ao backend e possui somente os privilégios necessários ao domínio.

### Tarefas

- [x] 2.1 currencies
- [x] 2.2 markets
- [x] 2.3 exchanges
- [x] 2.4 assets
- [x] 2.5 constraints/indexes
- [x] 2.6 RLS/security
- [x] 2.7 repositories
- [x] 2.8 persistence tests

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

### 2.6 — RLS/security

#### Objetivo

Proteger as tabelas de domínio em `public` com RLS deny-by-default, mantendo a service role restrita ao backend.

#### Critérios de conclusão

- [x] RLS habilitada em currencies
- [x] RLS habilitada em markets
- [x] RLS habilitada em exchanges
- [x] RLS habilitada em assets
- [x] anon sem acesso
- [x] authenticated sem acesso
- [x] PUBLIC sem privilégios de tabela
- [x] service_role preservada para backend
- [x] nenhuma policy permissiva
- [x] auth.role() não utilizado
- [x] SECURITY DEFINER não utilizado
- [x] migration criada
- [x] testes de contrato criados
- [x] migrations antigas preservadas
- [x] suíte completa passando
- [x] secrets preservadas
- [x] documentação atualizada

### Histórico de bloqueio durante validação remota

Status: ❌ BLOQUEADA DURANTE VALIDAÇÃO REMOTA

Motivo: a service role possuía os privilégios adicionais `REFERENCES`, `TRIGGER`, `TRUNCATE` e `MAINTAIN`, herdados do ambiente Supabase, além dos privilégios necessários ao backend.

### Correção local

- [x] migration corretiva de privilégios criada
- [x] teste de contrato da correção criado
- [x] privilégios da service role revalidados remotamente

## Gate 2.6

Status: ✅ APROVADA

### Registros operacionais remotos

- A ferramenta conectada registrou versões remotas diferentes dos timestamps dos arquivos locais. O histórico foi reconciliado exclusivamente pelos filenames locais, sem renomear versões remotas nem manipular `supabase_migrations.schema_migrations`.
- O advisor apontou `assets_exchange_market_fk` como `unindexed_foreign_keys`. Nenhum índice foi criado: `assets_identity_unique (market_id, exchange_id, symbol, currency_id)` será reavaliado com workload real antes de qualquer índice com prefixo em `exchange_id`.

### 2.7 — repositories

#### Objetivo

Criar uma camada de persistência Python mínima, tipada, testável e independente da criação do client Supabase.

#### Critérios de conclusão

- [x] modelos persistidos tipados
- [x] CurrencyRepository
- [x] MarketRepository
- [x] ExchangeRepository
- [x] AssetRepository
- [x] dependency injection do Client
- [x] create implementado
- [x] consultas por PK implementadas
- [x] consultas por chaves canônicas implementadas
- [x] respostas vazias tratadas
- [x] respostas malformadas rejeitadas
- [x] erros Supabase não engolidos
- [x] sem upsert silencioso
- [x] sem provider mappings
- [x] sem Market Data
- [x] testes unitários
- [x] suíte completa passando

## Gate 2.7

Status: ✅ APROVADA

### 2.8 — persistence tests

#### Objetivo

Validar a persistência real entre repositories, Supabase, PostgreSQL, constraints e o acesso de backend após RLS.

#### Critérios de conclusão

- [x] integration test criado
- [x] opt-in explícito para integração real
- [x] dados temporários únicos
- [x] cleanup por UUID
- [x] currency E2E
- [x] market E2E
- [x] exchange E2E
- [x] asset E2E
- [x] asset sem exchange testado
- [x] market/exchange inconsistente rejeitado
- [x] identidade duplicada rejeitada
- [x] backend service role funciona com RLS
- [x] RLS remota verificada
- [x] grants remotos verificados
- [x] suíte unitária completa passando
- [x] integração real passando
- [x] nenhuma secret exposta
- [x] nenhuma sobra de dados de teste

## Gate 2.8

Status: ✅ APROVADA

### Validação remota registrada

- [x] integration E2E: PASS
- [x] constraint exchange/market validada
- [x] duplicate identity validada
- [x] asset com exchange NULL validado
- [x] service role com RLS validada
- [x] cleanup validado
- [x] 0 dados temporários restantes

## Gate da Etapa 2

Status: ✅ APROVADA

### Critérios finais

- [x] schema versionado
- [x] migrations aplicadas remotamente
- [x] currencies
- [x] markets
- [x] exchanges
- [x] assets
- [x] constraints
- [x] índices
- [x] RLS
- [x] deny-by-default
- [x] menor privilégio service_role
- [x] repositories
- [x] testes unitários
- [x] testes de migration
- [x] teste real de persistência
- [x] integridade referencial validada
- [x] duplicate identity validada
- [x] cleanup validado
- [x] secrets protegidas
- [x] suíte completa passando
- [x] nenhuma migration antiga teve SQL alterado
- [x] histórico local/remoto reconciliado por filename
