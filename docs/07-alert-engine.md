# Alert Engine

## Objetivo
Evitar alertas irrelevantes e manter cada decisão auditável.

## Princípio
Um único indicador não deve gerar alerta financeiro. A IA não define o score e não recomenda compra ou venda; ela interpreta somente fatos previamente validados.

## Fluxo automatizado

market data
-> quality
-> análise determinística
-> deterministic pre-filter
-> Gemini (somente contexto para candidatos)
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
- `AUTOMATION_ENABLED == true`
- `PRODUCTION_READY == true`

Dados ausentes, stale, incomplete, outlier ou invalid não avançam para Gemini/alerta.

Shadow mode persiste previsões e outcomes futuros, mas não invoca `AlertService` para envio. Mesmo um backtest aprovado permanece bloqueado até o gate explícito de evidência futura liberar `PRODUCTION_READY`.

## Policy de oportunidade

A produção carrega exclusivamente a frozen policy persistida indicada por `OPPORTUNITY_POLICY_VERSION`; `OPPORTUNITY_RULES_JSON` é legado e rejeitado.

## Cooldown e dedupe

O mesmo evento não deve gerar spam. `AlertService` persiste PENDING/SENT/SUPPRESSED/FAILED, aplica cooldown e dedupe antes do envio.

O schema atual deduplica por oportunidade, não por destinatário. Por isso a automação exige exatamente um `TELEGRAM_ALLOWED_USER_IDS` enquanto não existir modelagem de destinatário em `alerts`.

## Mensagem

A mensagem permitida contém fatos auditáveis: ativo, timestamp, preço validado, nível, score, fatores e riscos. Ela não promete resultado e não executa ordem real.
