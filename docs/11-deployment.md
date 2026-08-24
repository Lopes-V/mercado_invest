# Deployment

## Estado
Deploy-ready com duas formas de execução:

1. `python -m app.worker` para host persistente/Docker;
2. `python -m app.run_once` para execução curta agendada, usada pelo GitHub Actions.

## Worker persistente

`app.worker` agora é um entrypoint real: carrega Settings, monta o composition root, executa `SchedulerService.run_forever` e fecha os clientes que foram montados em shutdown cooperativo por SIGINT/SIGTERM.

O Dockerfile continua usando usuário não-root e `CMD ["python", "-m", "app.worker"]`.

## GitHub Actions gratuito

`.github/workflows/automation.yml` executa a cada 30 minutos e chama `python -m app.run_once`. O cron roda quando shadow está habilitado ou quando os dois gates de produção estão aprovados. Shadow exige `SHADOW_MODE_ENABLED=true` e `SHADOW_POLICY_VERSION`; não requer Gemini nem Telegram. Alertas exigem simultaneamente `AUTOMATION_ENABLED=true` e `PRODUCTION_READY=true`.

O caminho de produção também recusa `OPPORTUNITY_RULES_JSON` que não corresponda
à versão persistida e aprovada em `frozen_opportunity_policies`; variáveis de
runtime não podem substituir thresholds congelados silenciosamente.

Credenciais devem ficar em GitHub Actions Secrets:

- `SUPABASE_URL`
- `SUPABASE_SECRET_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_ALLOWED_USER_IDS`
- `BRAPI_TOKEN` (opcional)
- `TWELVE_DATA_API_KEY`
- `GEMINI_API_KEY`

Configuração não secreta deve ficar em Repository Variables:

- `GEMINI_MODEL`
- `AUTOMATED_PIPELINE_PROVIDERS`
- `OPPORTUNITY_POLICY_VERSION`
- `OPPORTUNITY_RULES_JSON`
- `OPPORTUNITY_MINIMUM_CATEGORIES`
- `OPPORTUNITY_MAX_AI_WEIGHT`
- `ALERT_COOLDOWN_SECONDS`
- `AUTOMATION_ENABLED`
- `PRODUCTION_READY`
- `SHADOW_MODE_ENABLED`
- `SHADOW_POLICY_VERSION`
- `SHADOW_INTERVAL_SECONDS`
- `SHADOW_CANDLE_INTERVAL`
- `SHADOW_LOOKBACK_DAYS`
- `SHADOW_ANALYSIS_PERIOD`
- `SHADOW_FORWARD_HORIZON_DAYS` (dias de calendário)
- `SHADOW_ROUND_TRIP_COST_BPS`

## Ordem por rodada

Os jobs são registrados em ordem determinística:

1. quotes BRAPI/Twelve Data;
2. history BRAPI/Twelve Data quando devido;
3. shadow determinístico por provider e settlement quando habilitados;
4. pipeline completo Gemini/Opportunity/Alert somente com ambos os gates de produção.

`JobRunner` continua responsável por `run_key` idempotente e latest-slot-only. Assim um GitHub Actions atrasado não tenta reproduzir todos os slots perdidos.

Quando um provider devolve a mesma última cotação, `market_quotes` também é
idempotente por `(asset_id, provider, observed_at)`. O job registra
`market_quote_duplicate_ignored` e termina como sucesso; a restrição
`market_quotes_identity_unique` continua sendo a autoridade concorrente para a
decisão de duplicata.

## Limites

GitHub Actions não é infraestrutura de baixa latência e execuções `schedule` podem atrasar. O projeto não realiza trading automático; o uso é análise e alerta.

A policy de oportunidade precisa ser explicitamente configurada e deve ser calibrada por backtesting. A automação não inventa thresholds financeiros de produção.
