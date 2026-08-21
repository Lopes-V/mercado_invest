# Security

## Secrets
Apenas variáveis de ambiente.

## Telegram
Lista de usuários autorizados.

## Supabase
As tabelas de domínio (`currencies`, `markets`, `exchanges` e `assets`) estão em `public` e a migration de segurança define RLS deny-by-default. As roles `anon`, `authenticated` e `PUBLIC` não possuem privilégios de tabela nem policies nesta fase.

A migration corretiva revoga todos os privilégios preexistentes da service role nas tabelas de domínio e devolve somente `SELECT`, `INSERT`, `UPDATE` e `DELETE` necessários ao backend. A validação remota confirmou esse menor privilégio, RLS habilitada e ausência intencional de policies. A chave administrativa nunca pode ser enviada ao frontend, incluída em logs ou usada por clientes públicos.

## RLS
RLS é obrigatória nas tabelas expostas. Policies de usuário só devem ser criadas quando existir um caso de uso real de frontend/auth; não há policies permissivas temporárias. A aplicação remota das migrations e a validação dos privilégios foram concluídas para a Etapa 2.

## Logs
Sanitizar informações sensíveis.

## Dependências
Manter versões controladas.

## Entradas
Validar:
- comandos Telegram
- ticker
- payloads externos
- respostas da IA

## Falha segura
Quando não for possível garantir integridade dos dados:
nenhuma recomendação deve ser emitida.

## Market Data
`BRAPI_TOKEN` é opcional e exclusivo do backend. Tokens de provider são enviados somente em `Authorization: Bearer`; nunca em query string, logs ou exceções. As tabelas `asset_provider_symbols`, `market_quotes` e `market_candles` seguem RLS deny-by-default, não possuem policies e concedem à service_role somente `SELECT`, `INSERT`, `UPDATE` e `DELETE`.
