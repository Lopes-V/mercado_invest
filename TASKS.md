# Tasks

## Etapa atual

ETAPA 4 — Automation / Jobs (CONCLUÍDA)

## Tarefa atual

Próxima etapa planejada: ETAPA 5 — Portfolio

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

## Etapa 3 — Market Data

### Objetivo

Construir uma camada de dados de mercado independente de provider, capaz de consumir múltiplos mercados e fontes sem contaminar o domínio com payloads específicos de APIs externas.

### Tarefas

- [x] 3.1 contratos e modelos normalizados
- [x] 3.2 quality/validation engine
- [x] 3.3 infraestrutura HTTP de providers
- [x] 3.4 primeiro provider brasileiro
- [x] 3.5 persistência de Market Data
- [x] 3.6 ingestion service
- [x] 3.7 integração E2E

### 3.1 — contratos e modelos normalizados

#### Critérios de conclusão

- [x] tipos financeiros usam Decimal
- [x] timestamps timezone-aware
- [x] timestamps normalizados para UTC
- [x] Quote modelado
- [x] Candle modelado
- [x] MarketStatus modelado
- [x] ProviderAsset modelado
- [x] requests explícitos
- [x] DataQuality definido
- [x] MarketDataProvider definido
- [x] provider não depende de Supabase
- [x] nenhum provider concreto implementado
- [x] nenhum float financeiro
- [x] nenhuma persistência implementada
- [x] nenhuma chamada HTTP implementada
- [x] testes unitários
- [x] documentação atualizada
- [x] suíte completa passando
- [x] git diff --check limpo

### Revisão externa 3.1

Revisão externa confirmou:

- `quality=None` representa qualidade ainda não avaliada;
- nenhum estado artificial foi adicionado a `DataQuality`;
- provider adapter não define qualidade automaticamente;
- UUID interno e identificador externo permanecem separados;
- `MarketStatusRequest` possui routing externo suficiente.

## Gate 3.1

Status: ✅ APROVADA

### 3.2 — quality/validation engine

#### Critérios de conclusão

- [x] QualityPolicy
- [x] policy validada
- [x] QualityIssue
- [x] QualityAssessment
- [x] QualityEngine
- [x] evaluated_at explícito
- [x] sem relógio oculto
- [x] staleness quote
- [x] staleness candle
- [x] staleness MarketStatus
- [x] timestamp futuro inválido
- [x] received_at futuro inválido
- [x] candle completeness configurável
- [x] UNKNOWN status configurável
- [x] outlier com referência explícita
- [x] Decimal em cálculos
- [x] precedência determinística
- [x] múltiplos issues preservados
- [x] quality anterior não confiada
- [x] input original imutável
- [x] sem decisão financeira
- [x] testes unitários
- [x] documentação
- [x] suíte completa passando
- [x] git diff --check limpo

## Gate 3.2

Status: ✅ APROVADA

Revisão externa confirmou:

- `evaluated_at` explícito;
- ausência de relógio oculto;
- recomputação independente da quality anterior;
- input original imutável;
- issues múltiplos preservados;
- precedência determinística;
- `STALE` baseado no timestamp financeiro;
- `OUTLIER` depende de referência explícita;
- `Decimal` usado em cálculos;
- nenhuma decisão financeira implementada.

### 3.3 — infraestrutura HTTP de providers

- [x] timeout explícito
- [x] redirects desabilitados
- [x] retry determinístico para GET
- [x] JSON com Decimal
- [x] lifecycle explícito
- [x] testes unitários

## Gate 3.3

Status: ✅ APROVADA

### 3.4 — primeiro provider brasileiro

- [x] BRAPI V2 quote/history/tickers
- [x] token opcional por Authorization header
- [x] ticker rename rejeitado
- [x] parsing Decimal e timestamps UTC
- [x] market status como capability error
- [x] testes unitários e live opt-in

## Gate 3.4

Status: ✅ APROVADA

### 3.5 — persistência Market Data

- [x] migration local com tabelas, constraints, RLS e grants
- [x] records e repositories locais
- [x] testes locais
- [x] migration/validação remota
- [x] RLS, grants e ausência de policies confirmados remotamente
- [x] security/performance advisors revisados remotamente

## Gate 3.5

Status: ✅ APROVADA

### 3.6 — ingestion service

- [x] orchestration por injeção de dependências
- [x] quality antes da persistência
- [x] resultados rastreáveis e testes unitários
- [x] integração real de banco e propagação de erros validada

## Gate 3.6

Status: ✅ APROVADA

### 3.7 — integração E2E

- [x] smoke BRAPI live opt-in
- [x] integração real de banco opt-in
- [x] E2E completo BRAPI, Quality Engine e Supabase opt-in
- [x] cleanup estrito por IDs temporários

## Gate 3.7

Status: ✅ APROVADA

## Gate da Etapa 3

Status: ✅ APROVADA

A revisão externa final confirmou:

- transporte HTTP validado;
- BRAPI unitário e live validados;
- Quality Engine antes da persistência;
- migration aplicada remotamente;
- RLS e menor privilégio validados;
- repositories e ingestion Market Data validados;
- DB integration e Full E2E reais validados;
- cleanup por IDs exatos validado;
- nenhuma secret exposta.

## Etapa 4 — Automation / Jobs

### Tarefas

- [x] 4.1 scheduling core
- [x] 4.2 job_runs persistence
- [x] 4.3 job runner / idempotency
- [x] 4.4 Market Data jobs
- [x] 4.5 scheduler service
- [x] 4.6 failure handling / observability
- [x] 4.7 integration E2E

### 4.1 — scheduling core

- [x] Job protocol síncrono
- [x] JobContext UTC e explícito
- [x] JobResult tipado
- [x] IntervalSchedule determinístico
- [x] sem relógio oculto no cálculo de slot
- [x] testes unitários

## Gate 4.1

Status: ✅ APROVADA

### 4.2 — job_runs persistence

- [x] migration local `job_runs`
- [x] constraints, idempotência e índice justificado
- [x] RLS deny-by-default e grants mínimos no SQL
- [x] JobRunRecord e JobRunRepository
- [x] testes de migration e repository
- [x] migration/validação remota

## Gate 4.2

Status: ✅ APROVADA

### 4.3 — job runner / idempotency

- [x] run key agendado determinístico
- [x] lifecycle RUNNING para terminal
- [x] duplicate scheduled run não reexecuta job
- [x] erro sanitizado e propagado
- [x] correlation ID preservado
- [x] testes unitários

## Gate 4.3

Status: ✅ APROVADA

### 4.4 — Market Data jobs

- [x] listagem ativa por provider ordenada
- [x] MarketQuoteCollectionJob fail-fast
- [x] MarketHistoryCollectionJob com janela explícita
- [x] sem símbolos, providers ou mercados hardcoded
- [x] testes unitários

## Gate 4.4

Status: ✅ APROVADA

### 4.5 — scheduler service

- [x] latest-slot-only policy
- [x] ordem determinística de registro
- [x] falha isolada por ScheduledJob
- [x] run_forever local com clock, sleep e parada injetáveis
- [x] testes unitários

## Gate 4.5

Status: ✅ APROVADA

### 4.6 — failure handling / observability

- [x] eventos de lifecycle no logger existente
- [x] correlation ID, job name, slot e run ID nos eventos
- [x] sanitização limitada de Bearer e atribuições de token/secret
- [x] sem traceback no banco
- [x] limitações de single-process documentadas

## Gate 4.6

Status: ✅ APROVADA

### 4.7 — integration E2E

- [x] teste real opt-in de job_runs criado
- [x] Full E2E Stage 4 opt-in criado
- [x] migration remota aplicada
- [x] integrações reais executadas

## Gate 4.7

Status: ✅ APROVADA

## Gate técnico da Etapa 4

Status: ✅ APROVADA

A revisão externa final confirmou:

- scheduling determinístico e latest-slot-only;
- run_key persistido e idempotência validada;
- correlation ID e lifecycle RUNNING para terminal;
- Market Data jobs e SchedulerService;
- integração real BRAPI e Supabase;
- repetição do mesmo slot sem reexecução;
- cleanup por IDs exatos;
- RLS e menor privilégio validados;
- nenhuma secret exposta.
