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

Market Data -> Quality -> Analysis -> Gemini -> Opportunity -> Alert -> Telegram

A IA não define score financeiro, não inventa dados ausentes e não executa compra/venda. Dados não `VALID` bloqueiam o pipeline antes da IA.

## Automação

O repositório suporta:

- `python -m app.worker` para execução persistente;
- `python -m app.run_once` para execução agendada curta;
- `.github/workflows/automation.yml` para automação gratuita via GitHub Actions a cada 30 minutos.

A automação só coleta/análisa quando `AUTOMATED_PIPELINE_ENABLED=true`. Envio de Telegram exige adicionalmente `AUTOMATION_ENABLED=true` e `PRODUCTION_READY=true`; calibração histórica por si só nunca libera produção. Regras financeiras não são hardcoded: `OPPORTUNITY_RULES_JSON` e `OPPORTUNITY_POLICY_VERSION` são obrigatórios quando o pipeline automático está ativo.

## Lifecycle de policy

Uma calibração usa treino, validação e holdout cronológicos globais. A regra aprovada é avaliada com custo round-trip, concentração por ativo, distribuição mensal e bootstrap determinístico antes de ser congelada por versão. `CALIBRATION_RELEASE_READY` significa apenas que o holdout histórico passou; `PRODUCTION_READY` exige evidência futura registrada em shadow mode. Shadow mode nunca envia Telegram nem executa trades.

## Mercados
- Brasil: BRAPI
- Estados Unidos: Twelve Data
- Global: adapter implementado; cobertura live depende do plano/acesso do provider

## Estrutura
Veja `docs/01-architecture.md`.

## Segurança
Nunca versionar `.env`, tokens ou secret keys. Em GitHub Actions, credenciais ficam em Repository Secrets e policies não secretas em Repository Variables.
