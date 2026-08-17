# Tasks

## Etapa atual

ETAPA 1 — Fundação

## Tarefa atual

1.5 — Telegram

## Status

PARCIAL — aguardando teste end-to-end real

## Objetivo

Concluir a integração básica e segura com Telegram antes de avançar para `/status`.

## Permitido alterar

- app/
- tests/
- scripts/
- pyproject.toml
- .gitignore
- .env.example
- documentação

## Não implementar nesta tarefa

- IA
- Market Data
- Carteira
- Scheduler
- Alertas de oportunidade
- Compra automática
- Etapa 2 — Persistência de domínio

## Estado atual da 1.5

- [x] Configuração do token
- [x] `TelegramClient`
- [x] `getMe`
- [x] `getUpdates`
- [x] `sendMessage`
- [x] Parser de comandos
- [x] `/start`
- [x] Whitelist de usuários
- [x] Whitelist vazia usa deny-all
- [x] IDs inválidos são rejeitados
- [x] Usuários não autorizados são ignorados
- [x] Controle de offset
- [x] Runner de uma execução
- [x] Cliente HTTP fechado após sucesso
- [x] Cliente HTTP fechado após falha
- [x] Falhas são propagadas
- [x] 45 testes automatizados passando
- [x] `git diff --check` sem erros
- [ ] `getMe` validado contra Telegram real
- [ ] Token inválido rejeitado pela API real
- [ ] Telegram User ID real identificado
- [ ] `TELEGRAM_ALLOWED_USER_IDS` configurado com ID real
- [ ] `/start` validado end-to-end

## Bloqueio atual

A rede atual bloqueia a conexão TLS com:

`api.telegram.org`

Resultado atual:

`Telegram connection: FAILED [ConnectError]`

Esse bloqueio é externo ao código e não deve ser contornado desabilitando SSL/TLS.

## Etapas

- [x] 1.1 Bootstrap Python
- [x] 1.2 Configurações
- [x] 1.3 Logging
- [x] 1.4 Supabase
- [ ] 1.5 Telegram
- [ ] 1.6 /status
- [ ] 1.7 Testes de integração
- [ ] 1.8 Testes de falha

## Gate da Etapa 1

Status: ❌ NÃO APROVADA

Motivo:
A tarefa 1.5 ainda depende da validação end-to-end com a API real do Telegram.

## Próximo passo

Quando houver acesso a uma rede que permita Telegram:

1. Executar `python -m scripts.check_telegram`
2. Confirmar autenticação do bot
3. Testar token inválido
4. Enviar `/start` ao bot
5. Obter o Telegram User ID real
6. Configurar `TELEGRAM_ALLOWED_USER_IDS`
7. Executar o fluxo real do bot
8. Validar resposta ao `/start`
9. Aprovar 1.5
10. Iniciar 1.6 — `/status`