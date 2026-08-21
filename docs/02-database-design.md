# Database Design

## Banco
PostgreSQL através do Supabase.

## Regras
- UUID para identificadores.
- timestamps em UTC.
- dados financeiros possuem momento de referência.
- valores monetários utilizam tipos precisos.
- manter histórico sempre que necessário.

## Mercado

### markets
Representam mercados ou jurisdições financeiras suportadas, preparados para múltiplos países, regiões e mercados não soberanos. Cada registro possui `id` UUID, `code` único em maiúsculas, `name`, `country_code` opcional, `default_currency_id` opcional, `is_active` e timestamps com timezone.

`country_code`, quando informado, segue ISO-3166-1 alpha-2 por contrato; não há tabela ou enum de países nesta etapa para preservar expansão futura. `default_currency_id` referencia `currencies` somente como conveniência e não determina a moeda de todos os ativos do mercado.

`markets` não são `exchanges`: markets representam a jurisdição, enquanto bolsas ou venues específicos pertencem à tabela `exchanges`. Não há dados de exchange nem seeds. A migration de segurança habilita RLS e não cria policies de usuário nesta fase; a service role permanece somente no backend, sem exposição de chave administrativa no frontend.

### exchanges
Representam bolsas, venues e locais específicos de negociação; cada exchange pertence obrigatoriamente a um `market`. Os campos são `id` UUID, `market_id`, `code`, `name`, `mic` opcional, `timezone`, `is_active` e timestamps com timezone.

`code` é único apenas dentro do market. `mic` é opcional e único quando informado. `timezone` é obrigatório e validado somente quanto ao formato compatível com identificadores IANA; a verificação de sua existência real cabe à ingestão ou configuração futura. Exchanges não armazenam moeda default nem trading hours nesta etapa.

`markets` representam jurisdições, `exchanges` representam venues e `assets` são instrumentos canônicos. Não há seeds ou dados de provider. A migration de segurança habilita RLS e não cria policies de usuário nesta fase; a service role permanece somente no backend.

### currencies
Moedas que servem como referência monetária do domínio, sem restringir a arquitetura a um país ou mercado. Cada registro possui `id` UUID, `code` alfanumérico em maiúsculas e único, `name` não vazio, `symbol` opcional, `decimal_places`, `is_active` e timestamps com timezone (`created_at` e `updated_at`).

Não há seeds de moeda nesta etapa: a tabela representa somente o schema e permanece preparada para múltiplas moedas. A migration de segurança habilita RLS e não cria policies de usuário nesta fase. A service role continua restrita ao backend.

### assets
Representam instrumentos financeiros canônicos, independentes de providers, posições ou cotações. Cada asset possui `id` UUID, `market_id` obrigatório, `exchange_id` opcional, `currency_id` obrigatório, `symbol`, `name`, `asset_type`, `isin` opcional, `is_active` e timestamps com timezone.

O market é obrigatório; quando há exchange, ela deve pertencer ao mesmo market do asset. A moeda é referenciada por `currency_id`, sem duplicar seus atributos. `symbol` é canônico e provider-independent, enquanto `asset_type` usa validação de formato extensível, sem enum fechado. `isin` é opcional e único quando informado. A identidade formada por market, exchange (inclusive `NULL`), symbol e currency impede duplicatas lógicas.

Assets não são `market_quotes`, posições de carteira ou provider symbols; preços, candles, carteira e mapeamentos de providers permanecem fora desta tabela. Não há seeds. A migration de segurança habilita RLS e não cria policies de usuário nesta fase; a service role permanece somente no backend.

### asset_provider_symbols
Mapeamento canônico entre ativo interno e ticker utilizado por provider, com unicidade por `(asset_id, provider)` e `(provider, provider_symbol)`.

### market_quotes
Cotações auditáveis do provider: preço `numeric(38,18)`, moeda reportada externamente, timestamps observado/recebido e quality avaliada. A moeda observada permanece texto validado, sem FK para o catálogo canônico.

### market_candles
Histórico OHLCV com valores `numeric(38,18)`, intervalo normalizado, checks OHLC e quality avaliada. As três tabelas Market Data foram implementadas pela migration remota `20260821194749_create_market_data_tables`. Elas usam RLS deny-by-default, não possuem policies, anon/authenticated/PUBLIC não têm grants e service_role possui somente `SELECT`, `INSERT`, `UPDATE` e `DELETE`.

### fx_rates
Câmbio.

## Índices e constraints

PRIMARY KEYs e UNIQUE constraints já criam os índices necessários para suas colunas. FKs não criam índice automaticamente no lado referenciador: `exchanges.market_id` já é coberto por `exchanges_market_code_unique`, e `assets.market_id` e a combinação market/exchange são cobertos pelo prefixo de `assets_identity_unique`.

Foram adicionados índices próprios para `markets.default_currency_id` e `assets.currency_id`, que não tinham cobertura iniciada por essas colunas. Índices especulativos foram evitados; novos índices serão avaliados quando repositories e queries reais existirem.

O advisor remoto sinalizou `assets_exchange_market_fk` como `unindexed_foreign_keys`. Não foi criado índice adicional apenas para silenciar o advisor: a cobertura de `assets_identity_unique (market_id, exchange_id, symbol, currency_id)` e a necessidade de um índice com prefixo em `exchange_id` serão reavaliadas com workload real. Os índices `markets_default_currency_id_idx` e `assets_currency_id_idx` aparecem como unused em banco recém-criado, o que não é bloqueante.

## Carteira

### portfolios

### portfolio_transactions

### portfolio_snapshots

## Análises

### analyses

### analysis_metrics

### ai_runs

### opportunities

## Sistema

### alerts

### system_logs

### job_runs
Histórico auditável de cada execução de job. `run_key` é único e protege a idempotência operacional; para jobs agendados ele deriva deterministicamente de `job_name` e do slot UTC. `correlation_id` também é único e conecta logs, contexto e persistência. A migration remota `20260821202531_create_job_runs.sql` define status, triggers, coerência temporal, RLS deny-by-default, nenhuma policy e CRUD mínimo para service_role; sua aplicação e validação remotas foram concluídas.

### system_settings

## Segurança

As tabelas de domínio em `public` usam a estratégia RLS deny-by-default definida na migration de segurança. `anon`, `authenticated` e `PUBLIC` não recebem privilégios de tabela nem policies nesta fase; a service role, restrita ao backend, possui somente `SELECT`, `INSERT`, `UPDATE` e `DELETE` necessários ao domínio. Policies de usuário somente serão adicionadas quando houver um caso de uso real de frontend/auth.

As migrations de segurança foram aplicadas e validadas remotamente. Nenhuma chave administrativa pode ser exposta no frontend.

Após a aplicação remota, foi identificado que a service role possuía privilégios adicionais herdados do ambiente. A migration corretiva revoga todos os privilégios dessa role nas tabelas de domínio e devolve somente `SELECT`, `INSERT`, `UPDATE` e `DELETE`; a confirmação remota foi concluída.

As versões de migration registradas remotamente diferiam dos timestamps locais. A reconciliação foi realizada exclusivamente pelos filenames locais; o histórico remoto não foi renomeado nem manipulado diretamente em `supabase_migrations.schema_migrations`.

## Repositories

`CurrencyRepository`, `MarketRepository`, `ExchangeRepository` e `AssetRepository` recebem um `supabase.Client` já criado pelo backend. Eles retornam modelos tipados, validam UUIDs, timestamps e campos nullable das respostas do PostgREST e propagam erros externos; constraints, FKs e RLS continuam sendo garantias do banco.
