# Market Data

## Objetivo
Padronizar dados recebidos de diferentes providers.

## Pipeline futuro

Provider API
    ↓
Provider Adapter
    ↓
Normalized Market Data
    ↓
Quality Engine
    ↓
Persistence
    ↓
Analysis

O core não chama APIs nem persiste dados. Providers específicos começam somente na tarefa 3.4.

## Identidade e requests

UUID interno não é identificador externo de provider. `asset_id` é a identidade canônica interna; `provider_symbol` identifica o ativo para uma fonte e nunca substitui o asset do domínio. Por isso, `QuoteRequest` e `HistoryRequest` exigem ambos explicitamente.

Para status, `MarketStatusRequest` exige ao menos um identificador interno (`market_id` ou `exchange_id`) para correlação com o domínio e ao menos um código externo (`provider_market_code` ou `provider_exchange_code`) para routing no adapter. O pareamento não precisa ser estrito: um `market_id` pode ser combinado com `provider_exchange_code`, por exemplo. O adapter recebe o código diretamente no request e não consulta repositories para descobrir o alvo da requisição.

## Dados normalizados

`Quote`, `Candle` e `MarketStatus` carregam timestamp de referência, `received_at`, provider e qualidade. Preços e OHLC usam `Decimal`; timestamps timezone-aware são normalizados para UTC.

`CandleInterval` define `1m`, `5m`, `15m`, `30m`, `1h`, `1d`, `1wk` e `1mo`. `MarketSessionStatus` representa somente o estado informado, sem modelar horários de negociação.

## Qualidade

`DataQuality` possui exatamente os estados `VALID`, `STALE`, `INCOMPLETE`, `OUTLIER` e `INVALID`. Antes do Quality Engine, `Quote`, `Candle` e `MarketStatus` podem ser construídos explicitamente com `quality=None`. Isso significa somente que a qualidade ainda não foi avaliada; não significa `VALID`, `INVALID` ou `INCOMPLETE`, nem cria um novo estado de `DataQuality`.

A tarefa 3.2 transformará `None` em um `DataQuality`. Antes de persistência, análise, IA ou alertas, os dados deverão possuir qualidade avaliada. A tarefa 3.1 não classifica dados nem assume `VALID`.

## Regra

Dados `INVALID` nunca podem chegar à IA. Payloads de providers passam primeiro pelo adapter, modelos normalizados, qualidade e persistência; nunca entram diretamente na IA.
