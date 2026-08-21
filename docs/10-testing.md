# Testing

## Tipos

### Unit
Funções isoladas.

### Integration
Supabase, providers, Telegram.

### E2E
Fluxos completos.

## Casos obrigatórios

Happy Path.

Provider indisponível.

Banco indisponível.

Dados antigos.

Dados incompletos.

Outlier.

IA inválida.

Telegram indisponível.

## Regra
Uma tarefa não pode ser aprovada apenas por teste manual.

## Persistência Supabase

Os testes unitários dos repositories usam uma fronteira Supabase controlada e não acessam rede. A integração real é opt-in para evitar escrita remota acidental na suíte diária:

```bash
RUN_SUPABASE_INTEGRATION=1 \
python -m pytest tests/integration/test_domain_persistence.py -vv
```

Ela requer migrations aplicadas e credenciais de backend já presentes no ambiente; os dados temporários são únicos e o cleanup usa somente os UUIDs criados pelo próprio teste. Um teste skipped sem a variável não valida a persistência remota. A execução remota da Etapa 2 passou, validando constraints, RLS de backend e cleanup sem dados temporários restantes.

## Market Data

Transporte e adapters usam `httpx.MockTransport` em testes unitários. As integrações externas de Market Data são opt-in e não convertem falhas reais em sucesso quando habilitadas:

```bash
RUN_BRAPI_INTEGRATION=1 \\
RUN_SUPABASE_INTEGRATION=1 \\
RUN_MARKET_DATA_DB_INTEGRATION=1 \\
RUN_MARKET_DATA_E2E=1 \\
python -m pytest tests/integration -vv
```

As flags controlam, respectivamente, o smoke BRAPI, a persistência de domínio, a persistência Market Data e o Full E2E. A última execução externa habilitada teve 4 testes passados e 0 skipped; a suíte normal teve 218 passed e 4 skipped.

## Jobs

O core de jobs é testado sem relógio, rede ou Supabase real. As integrações futuras são opt-in:

```bash
RUN_JOBS_DB_INTEGRATION=1 python -m pytest tests/integration/test_job_runs_persistence.py -vv
RUN_STAGE4_E2E=1 python -m pytest tests/integration/test_stage4_scheduler_e2e.py -vv
```

As duas integrações exigem a migration `job_runs` aplicada remotamente. A validação externa habilitada passou com 6 testes e 0 skipped; a suíte normal validada teve 254 passed e 6 skipped.

## Etapas 5–16

As integrações futuras são opt-in e não são aprovação implícita quando skipped: `RUN_PORTFOLIO_DB_INTEGRATION`, `RUN_ANALYSIS_DB_INTEGRATION`, `RUN_OPENAI_INTEGRATION`, `RUN_OPPORTUNITY_DB_INTEGRATION`, `RUN_TELEGRAM_ALERT_INTEGRATION`, `RUN_BACKTEST_DB_INTEGRATION`, `RUN_PAPER_TRADING_DB_INTEGRATION`, `RUN_TREASURY_INTEGRATION`, `RUN_TWELVE_DATA_INTEGRATION`, `RUN_GLOBAL_MARKET_INTEGRATION` e `RUN_FULL_PIPELINE_E2E`. Elas só devem ser habilitadas após a migration correspondente e credenciais seguras estarem disponíveis.
