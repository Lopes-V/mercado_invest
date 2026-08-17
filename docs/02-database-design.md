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

`markets` não são `exchanges`: markets representam a jurisdição, enquanto bolsas ou venues específicos pertencem à futura tabela `exchanges`. Não há dados de exchange nem seeds nesta migration. RLS e policies serão tratadas em tarefa posterior; sua ausência agora é intencional, e a service role permanece somente no backend, sem exposição de chave administrativa no frontend.

### exchanges
Representam bolsas, venues e locais específicos de negociação; cada exchange pertence obrigatoriamente a um `market`. Os campos são `id` UUID, `market_id`, `code`, `name`, `mic` opcional, `timezone`, `is_active` e timestamps com timezone.

`code` é único apenas dentro do market. `mic` é opcional e único quando informado. `timezone` é obrigatório e validado somente quanto ao formato compatível com identificadores IANA; a verificação de sua existência real cabe à ingestão ou configuração futura. Exchanges não armazenam moeda default nem trading hours nesta etapa.

`markets` representam jurisdições, `exchanges` representam venues e `assets` serão instrumentos negociados em etapa futura. Não há seeds ou dados de provider nesta migration. RLS e policies serão tratadas posteriormente; sua ausência agora é intencional, e a service role permanece somente no backend.

### currencies
Moedas que servem como referência monetária do domínio, sem restringir a arquitetura a um país ou mercado. Cada registro possui `id` UUID, `code` alfanumérico em maiúsculas e único, `name` não vazio, `symbol` opcional, `decimal_places`, `is_active` e timestamps com timezone (`created_at` e `updated_at`).

Não há seeds de moeda nesta etapa: a tabela representa somente o schema e permanece preparada para múltiplas moedas. RLS e suas policies serão implementadas em tarefa posterior; a ausência delas nesta migration é intencional. A service role continua restrita ao backend.

### assets
Ativos.

### asset_provider_symbols
Mapeamento entre ativo interno e ticker utilizado pelos providers.

### market_quotes
Cotações.

### market_candles
Histórico OHLCV.

### fx_rates
Câmbio.

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

### system_settings

## Segurança
- RLS quando aplicável.
- service role somente backend.
- nenhuma credencial no banco sem proteção adequada.
