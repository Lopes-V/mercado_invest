# Security

## Secrets
Apenas variáveis de ambiente.

## Telegram
Lista de usuários autorizados.

## Supabase
Chaves administrativas apenas no backend.

## RLS
Habilitar nas tabelas expostas.

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