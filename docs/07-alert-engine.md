# Alert Engine

## Objetivo
Evitar alertas irrelevantes e manter cada decisão auditável.

## Princípio
Um único indicador não deve gerar alerta financeiro. A IA não define o score e não recomenda compra ou venda; ela interpreta somente fatos previamente validados.

## Fluxo automatizado

market data
-> quality
-> análise determinística
-> Gemini
-> opportunity engine
-> alert engine
-> Telegram

## Níveis
- NONE
- WATCH
- INTERESTING
- HIGH_INTEREST

## Condições obrigatórias
- quote com quality `VALID`
- candles com quality `VALID`
- análise persistida
- policy determinística explícita
- destinatário autorizado
- cooldown respeitado

Dados ausentes, stale, incomplete, outlier ou invalid não avançam para Gemini/alerta.

## Policy de oportunidade

A automação não contém thresholds financeiros hardcoded. As regras são recebidas por `OPPORTUNITY_RULES_JSON` e versionadas por `OPPORTUNITY_POLICY_VERSION`. Isso permite calibrar a policy por backtesting sem alterar o código do pipeline.

## Cooldown e dedupe

O mesmo evento não deve gerar spam. `AlertService` persiste PENDING/SENT/SUPPRESSED/FAILED, aplica cooldown e dedupe antes do envio.

O schema atual deduplica por oportunidade, não por destinatário. Por isso a automação exige exatamente um `TELEGRAM_ALLOWED_USER_IDS` enquanto não existir modelagem de destinatário em `alerts`.

## Mensagem

A mensagem permitida contém fatos auditáveis: ativo, timestamp, preço validado, nível, score, fatores e riscos. Ela não promete resultado e não executa ordem real.
