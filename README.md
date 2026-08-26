# Investment Bot

## Objetivo
Sistema pessoal de análise de investimentos com coleta automática de mercado,
carteira, IA, alertas e bot no Telegram.

## Status atual
Etapas 0–15 aplicáveis implementadas e validadas; Gemini, Twelve Data EUA e Telegram possuem validação live. A etapa global permanece limitada pelo acesso do plano Twelve Data para equity não-US/não-BR.

## Principais tecnologias
- Python 3.12
- Supabase / PostgreSQL
- Telegram Bot API
- Google Gemini
- BRAPI
- Twelve Data
- GitHub Actions
- Docker

## Pipeline

Market Data -> Quality -> Analysis -> Deterministic Pre-filter -> summary/alert flow -> Telegram

A IA não define score financeiro, não inventa dados ausentes e não executa compra/venda. Dados não `VALID` bloqueiam o pipeline antes da IA.

## Automação

O repositório suporta:

- `python -m app.worker` para execução persistente;
- `python -m app.run_once` para execução agendada curta;
- `.github/workflows/automation.yml` para automação gratuita via GitHub Actions a cada 30 minutos.

Coleta, shadow e produção são caminhos separados. `SHADOW_MODE_ENABLED=true`
monta análise determinística e settlement de evidência futura sem Gemini,
Telegram, alertas ou trading. O pipeline de produção só é montado quando
`AUTOMATED_PIPELINE_ENABLED=true`, `AUTOMATION_ENABLED=true` e
`PRODUCTION_READY=true`. Regras financeiras não são reconstruídas no shadow:
ele usa uma policy previamente congelada em `SHADOW_POLICY_VERSION`.

## Lifecycle de policy

Uma calibração usa treino, validação e holdout cronológicos globais. A regra aprovada é avaliada com custo round-trip, concentração por ativo, distribuição mensal e bootstrap determinístico antes de ser congelada por versão. `CALIBRATION_RELEASE_READY` significa apenas que o holdout histórico passou; `PRODUCTION_READY` é uma decisão estatística separada, baseada em evidência futura líquida de custos. `AUTOMATION_ENABLED` continua sendo a decisão operacional do operador. Shadow mode nunca envia Telegram nem executa trades.

## Mercados
- Brasil: BRAPI
- Estados Unidos: Twelve Data
- Global: adapter implementado; cobertura live depende do plano/acesso do provider

## Estrutura
Veja `docs/01-architecture.md`.

## Segurança
Nunca versionar `.env`, tokens ou secret keys. Em GitHub Actions, credenciais ficam em Repository Secrets e policies não secretas em Repository Variables.
