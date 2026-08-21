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

## Quality Engine

`QualityEngine` é determinístico, independente de provider e recebe uma `QualityPolicy` explícita. Cada avaliação recebe `evaluated_at` timezone-aware; o engine não consulta relógio, banco, API ou qualquer referência externa. Ele sempre recalcula a qualidade, sem confiar no valor anterior do dado, e retorna uma nova instância normalizada com `QualityAssessment` e todos os `QualityIssue` encontrados.

A policy configura as idades máximas de quotes, candles e status, a tolerância para timestamps futuros, a completude opcional de candles e o limite opcional de desvio relativo. A precedência determinística é `INVALID > INCOMPLETE > OUTLIER > STALE > VALID`; issues secundários nunca são descartados.

`INVALID` cobre incoerências temporais objetivas: `timestamp` ou `received_at` além da tolerância futura, ou `timestamp` excessivamente posterior a `received_at`. `STALE` usa exclusivamente o timestamp financeiro: `age == max_age` ainda é válido, enquanto `age > max_age` é stale. `received_at` permanece informação de auditoria e não rejuvenesce o dado.

`OUTLIER` só é avaliado com `reference_price` explícito e `Decimal` positivo e finito. O engine não busca nem inventa referência; sem referência, o check não é executado. Outlier é uma classificação de qualidade, jamais recomendação, alerta ou decisão de compra/venda.

`max_relative_price_deviation` é uma razão decimal: `Decimal("0.10")` representa 10%; `Decimal("10")` não representa 10%.

`Candle.timestamp` deve ter semântica consistente definida pelos adapters futuros. Cada adapter deverá normalizar o timestamp recebido do provider para o contrato do core antes da avaliação de qualidade.

`VALID` significa somente que nenhuma regra habilitada encontrou problema. Não prova que o preço é verdadeiro, não garante resultado financeiro e não constitui recomendação.

## Transporte, provider e ingestão

`ProviderHttpClient` fornece somente transporte HTTP/JSON síncrono: timeout explícito, redirects desabilitados, retry determinístico de GET para falhas transitórias e parsing de números JSON decimais com `Decimal`. Tokens seguem exclusivamente no header `Authorization` e nunca em URL ou exceções.

O adapter BRAPI usa os endpoints V2 `/api/v2/stocks/quote`, `/api/v2/stocks/historical` e `/api/v2/tickers`. Renomes ou divergências de ticker interrompem a operação para reavaliação do mapping; não há alteração silenciosa de identidade. O histórico exige intervalo explícito e preserva o instante fornecido pela BRAPI como `Candle.timestamp` UTC. Market status não é inferido: a capability não é suportada pelo provider.

`MarketDataIngestionService` recebe provider, QualityEngine e repositories por injeção. Ele resolve o mapping, normaliza, avalia e só então persiste; inclusive dados stale, incomplete, outlier ou invalid são auditáveis. Dados sem quality avaliada não são persistidos.

O Full E2E opt-in valida o pipeline real BRAPI → modelos normalizados (`quality=None`) → Quality Engine → Supabase e o cleanup por IDs temporários exatos. Nenhum provider, engine ou ingestion inventa cotação, candle, referência de outlier ou market status.

## Regra

Dados `INVALID` nunca podem chegar à IA. Payloads de providers passam primeiro pelo adapter, modelos normalizados, qualidade e persistência; nunca entram diretamente na IA.
