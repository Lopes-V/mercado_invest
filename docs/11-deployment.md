# Deployment

## Estado
Deploy-ready com duas formas de execução:

1. `python -m app.worker` para host persistente/Docker;
2. `python -m app.run_once` para execução curta agendada, usada pelo GitHub Actions.

## Worker persistente

`app.worker` agora é um entrypoint real: carrega Settings, monta o composition root, executa `SchedulerService.run_forever` e fecha clientes HTTP/Gemini/Telegram em shutdown cooperativo por SIGINT/SIGTERM.

O Dockerfile continua usando usuário não-root e `CMD ["python", "-m", "app.worker"]`.

## GitHub Actions gratuito

`.github/workflows/automation.yml` executa a cada 30 minutos e chama `python -m app.run_once`. O job só roda automaticamente quando a repository variable `AUTOMATION_ENABLED=true` estiver configurada.

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

## Ordem por rodada

Os jobs são registrados em ordem determinística:

1. quotes BRAPI/Twelve Data;
2. history BRAPI/Twelve Data quando devido;
3. pipeline de análise por provider.

`JobRunner` continua responsável por `run_key` idempotente e latest-slot-only. Assim um GitHub Actions atrasado não tenta reproduzir todos os slots perdidos.

## Limites

GitHub Actions não é infraestrutura de baixa latência e execuções `schedule` podem atrasar. O projeto não realiza trading automático; o uso é análise e alerta.

A policy de oportunidade precisa ser explicitamente configurada e deve ser calibrada por backtesting. A automação não inventa thresholds financeiros de produção.
