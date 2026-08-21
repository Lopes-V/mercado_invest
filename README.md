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

As etapas 0–14 aplicáveis foram validadas externamente. As etapas 7, 9, 15 e 16 estão implementadas e aguardam somente lives que exigem credenciais ou configuração externa. As bases das etapas 5–16 usam Decimal, timestamps explícitos e RLS deny-by-default; suas migrations foram aplicadas e validadas remotamente, incluindo a migration de índices de consulta.
