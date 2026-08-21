# Investment Bot

## Objetivo
Sistema pessoal de análise de investimentos com coleta automática de mercado,
carteira, IA, alertas e bot no Telegram.

## Status atual
Etapas 0–16 implementadas; validações live dependentes de credenciais externas permanecem explicitamente pendentes.

## Principais tecnologias
- Python
- Supabase / PostgreSQL
- Telegram Bot
- IA/LLM
- Docker futuramente

## Funcionalidades planejadas
- Monitoramento automático
- Carteira
- Análise de ativos
- Opportunity Score
- Alertas
- Logs
- Backtesting
- Paper Trading

## Mercados
V1: Brasil
Futuro: Estados Unidos e outros mercados

## Estrutura
Veja `docs/01-architecture.md`.

## Como executar
Consulte a documentação de cada etapa e os testes correspondentes.

## Segurança
Nunca versionar `.env` ou tokens.
# Estado de implementação

As etapas 0–15 aplicáveis foram validadas externamente. A IA usa Google Gemini como adapter opcional de backend; sua live depende de `GEMINI_API_KEY` e `GEMINI_MODEL`. As etapas 9 e 16 aguardam somente lives externas; a live global da etapa 16 depende da disponibilidade de equity não-US/não-BR no plano Twelve Data. As bases das etapas 5–16 usam Decimal, timestamps explícitos e RLS deny-by-default; suas migrations foram aplicadas e validadas remotamente, incluindo a migration de índices de consulta.
