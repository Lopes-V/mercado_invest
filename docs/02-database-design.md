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
Mercados suportados.

### exchanges
Bolsas.

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
