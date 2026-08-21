# Analysis Engine

## Responsabilidade
Realizar cálculos determinísticos antes da IA.

## Métricas planejadas
- variação
- médias móveis
- volatilidade
- volume
- momentum
- RSI
- drawdown

Indicadores fundamentalistas serão definidos posteriormente.

## Regra
Os cálculos não devem depender da IA.

## Resultado

AnalysisMetrics:
- metric
- value
- reference period
- timestamp
- algorithm version

## Versionamento
Alterações nas fórmulas precisam aumentar a versão do algoritmo.

## Implementação atual

`analysis-v1` calcula RETURN, SMA, MOMENTUM, AVERAGE_VOLUME, volatilidade populacional de retornos simples (sem anualização), RSI de Wilder e MAX_DRAWDOWN. A entrada é ordenada por timestamp, rejeita duplicidade e exige `Candle.quality == VALID`; candles não são interpolados.
