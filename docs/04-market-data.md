# Market Data

## Objetivo
Padronizar dados recebidos de diferentes providers.

## MarketDataProvider

Responsabilidades:
- get_quote
- get_history
- get_assets
- get_market_status

## Dados normalizados

Asset
Quote
Candle
MarketStatus

## Quote

Deve possuir:
- asset
- price
- currency
- timestamp
- provider
- received_at

## Qualidade

Estados:
- VALID
- STALE
- INCOMPLETE
- OUTLIER
- INVALID

## Regra
INVALID nunca pode chegar à IA.

## Outliers
Mudanças extremas precisam ser verificadas antes de gerar alertas.

## V1
Mercado brasileiro.

## Futuro
Providers estrangeiros deverão utilizar o mesmo contrato.