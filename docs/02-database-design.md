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
Moedas.

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