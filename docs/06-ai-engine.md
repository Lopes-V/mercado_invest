# AI Engine

## Responsabilidade
Interpretar informações previamente validadas.

## A IA pode
- identificar relações.
- explicar contexto.
- destacar riscos.
- comparar evidências.
- produzir resumo.

## A IA não pode
- inventar cotação.
- inventar indicador.
- alterar dados.
- executar compra.
- definir sozinha Opportunity Score.

## Entrada

ValidatedAIContext:
- asset
- market
- price
- metrics
- macro context
- portfolio context
- data quality

## Saída

AIAnalysisResponse:
- classification
- confidence
- positive_factors
- negative_factors
- risks
- summary

## Validação
Qualquer resposta fora do schema deverá ser rejeitada.

## Auditoria
Registrar:
- modelo
- provider
- análise
- duração
- tokens
- versão