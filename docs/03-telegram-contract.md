# Telegram Bot

## Segurança
Somente Telegram User IDs autorizados podem utilizar comandos privados.

## Comandos

### /start
Apresenta o bot.

### /help
Lista comandos.

### /status
Exibe saúde do sistema.

### /mercado
Resumo do mercado.

### /analisar <ativo>
Solicita análise.

Exemplo:
/analisar PETR4

### /carteira
Exibe carteira.

### /oportunidades
Lista oportunidades detectadas.

### /alertas
Consulta alertas.

### /logs
Logs recentes.

### /performance
Performance das análises anteriores.

## Erros

Ativo inexistente:
"Ativo não encontrado."

Dados desatualizados:
"Não existem dados suficientemente recentes para análise."

Serviço indisponível:
"Análise indisponível no momento."

## Fechamento diário

`DailyInvestmentSummaryJob` usa `TELEGRAM_SUMMARY_HOUR_BRT=22` e
`America/Sao_Paulo` para produzir uma única mensagem consolidada no dia. Ela
é enviada diretamente ao transporte para cada `TELEGRAM_ALERT_CHAT_IDS`, sem
passar pelo `AlertService`, sem criar `alerts` e sem repetir alertas
individuais.

O fechamento inclui a quantidade de ativos analisados, oportunidades relevantes
ordenadas por score, preço e indicadores `VALID`, resumo/riscos Gemini
persistidos e os estados nova, mantida ou deixou de ser interessante. Sem
oportunidade relevante, a mensagem informa isso explicitamente. Valores são
formatados para leitura humana e nenhum dado ausente é estimado.
# Alertas de oportunidade

O canal Telegram recebe somente uma decisão já qualificada. A mensagem não é ordem e não pode usar “compre”, “venda” ou promessa de retorno. Tokens nunca entram em mensagens, URLs ou logs.
