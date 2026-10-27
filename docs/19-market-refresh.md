# Intervalos de atualização

- Atlas conectado: consulta automática ao servidor a cada30 segundos, com a aba visível e online. Router.refresh preserva filtros, privacidade e autenticação; a chave Supabase continua somente no servidor. A consulta não torna antigo preço válido.
- Cripto: rodada a cada60 segundos dentro de uma janela de270 segundos por job GitHub (até5 rodadas). Solicitações são sequenciais; slots perdidos por chamadas lentas são descartados, sem rajadas de catch-up. Falha parcial não impede a próxima rodada e não vira sucesso silencioso.
- Ações: job independente a cada5 minutos, com intervalo de slots300s, usando os providers BRAPI/Twelve Data já configurados. Executa somente coleta de cotações. Desativa explícita e localmente gates de pipeline, shadow, Gemini, Telegram, histórico e alertas, preservando os jobs e gates originais de automation.yml.

O workflow crypto-radar.yml mantém cron */5, que é o mínimo suportado pelo GitHub. Disparos podem atrasar: a janela interna de60s não é um servidor permanente nem garante atualização contínua entre jobs. Operação contínua subcinco minutos requer um executor persistente, fora do GitHub cron. A integração dos PRs ativa as novas janelas na main; o deploy Atlas só ativa o polling da tela.

```bash
python -m app.market_refresh --mode crypto --interval 60 --duration 270 --output /tmp/crypto-radar.json
python -m app.market_refresh --mode stocks --duration 0 --output /tmp/stock-quotes.json
```

As duas chamadas gravam dados reais e auditoria; não executá-las só para iniciar o ambiente. O crypto provider permanece Kraken. Não são emitidas ordens, recomendações, mensagens ou transações virtuais. O cooldown de alertas não é o intervalo de coleta e não foi alterado.

Taxas/cotas dependem dos planos das APIs. Fora do pregão, sem negócios recentes, sem credenciais ou ao atingir limite da fonte, coletar mais vezes não cria novos preços. O relatório preserva indisponibilidade e horários reais. A validade cripto continua120 segundos.
