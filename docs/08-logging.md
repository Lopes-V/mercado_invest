# Logging

## Logs operacionais

Níveis:
- INFO
- WARNING
- ERROR
- CRITICAL

## Auditoria financeira

Registrar:
- ativo
- timestamp
- dados utilizados
- indicadores
- versão
- resposta IA
- opportunity score
- decisão
- alerta

## Correlation ID
Cada execução deve ser rastreável de ponta a ponta.

## Jobs

Jobs registram `job_started`, `job_succeeded`, `job_failed` e `job_skipped_duplicate` com `job_name`, `correlation_id`, `scheduled_for` e `run_id`. Mensagens persistidas são sanitizadas e limitadas; não recebem traceback, headers ou tokens.

## Segurança
Nunca registrar:
- Telegram token
- Supabase secret
- API keys
- credentials

## Secrets

Nunca registrar valores de:

- Telegram Bot Token
- Supabase keys
- API keys
- credenciais
- tokens de autenticação

Erros devem fornecer contexto sem revelar secrets.
