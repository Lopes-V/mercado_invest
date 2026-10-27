# Radar público Bybit spot

O radar observa BTCUSDT, ETHUSDT e SOLUSDT por padrão, em candles **fechados** de 15m e 1h. A lista pode ser configurada com `CRYPTO_SYMBOLS` ou `--symbols`, até 20 pares USDT. USDT não é convertido implicitamente para USD ou BRL.

## Instalação e execução

Use Python 3.12 e `pip install -r requirements.lock.txt`. Configure `SUPABASE_URL` e `SUPABASE_SECRET_KEY` com os mesmos nomes do backend. A CLI carrega o `.env` próprio do backend e o ambiente do processo; não copia credenciais do frontend. A API de mercado da Bybit é pública e não precisa de chave de negociação.

```bash
# Valida os instrumentos e mostra o catálogo que seria criado, sem escrever.
python -m app.crypto_radar --bootstrap
# Após revisar o plano, cria somente os registros ausentes.
python -m app.crypto_radar --bootstrap --apply
# Relatório descritivo sem gravação de fatos financeiros.
python -m app.crypto_radar
# Coleta, análise e auditoria persistidas; relatório fora do checkout.
python -m app.crypto_radar --bootstrap --apply --persist --output /tmp/crypto-radar.json
```

Catálogo: moeda USDT, market CRYPTO, exchange BYBIT/UTC, asset_type CRYPTO. Registros existentes e desativados são preservados; conflitos de identidade interrompem o bootstrap. Não há migration, ordem, alteração de policy de ações ou envio de Telegram.

## Fórmulas e versão

`analysis-v2` é uma classe independente; `analysis-v1`, suas políticas congeladas e os jobs existentes continuam iguais. São necessários ao menos 51 candles contínuos e válidos. O período padrão é 14, com suporte a 2..200.

- RETURN: razão de retorno nos últimos `period` intervalos (period+1 fechamentos); MOMENTUM_PCT: 100 vezes essa razão.
- EMA20/EMA50: média simples inicial e atualização com alpha=2/(n+1).
- RSI: seed de ganhos/perdas e suavização de Wilder ao longo do histórico.
- VOLATILITY: desvio padrão populacional dos últimos `period` retornos simples, não anualizado.
- ATR: true range com suavização de Wilder, na moeda de cotação.
- MAX_DRAWDOWN: perda máxima do pico na mesma janela de period+1 fechamentos.
- AVERAGE_VOLUME: média dos `period` candles anteriores, sem o atual. RELATIVE_VOLUME: volume atual dividido por essa média; sem denominador positivo o quociente é indisponível. Volume ausente não vira zero.
- TREND_DIRECTION: 1 se close>EMA20>EMA50, -1 se close<EMA20<EMA50, 0 nos demais casos. É direção observada, não probabilidade ou ordem de compra.

As operações usam Decimal. Os indicadores são quantizados explicitamente para a escala `numeric(38,18)` ao persistir, com arredondamento HALF_UP compatível com PostgreSQL; uma repetição do mesmo candle não falha por arredondamento. Valores brutos de mercado que não couberem exatamente nessa escala são recusados em vez de silenciosamente modificados.

## Qualidade e relatório

Cotação usa o horário real do último negócio, com idade máxima de 120 segundos e tolerância futura de 2 minutos. Histórico deve ser contínuo, encerrado e recente em relação ao seu intervalo; não se interpolam lacunas. Janelas são independentes e registram indisponibilidade por motivo. Falhas de uma janela ou de um par não se tornam sucesso global; o comando termina com status diferente de zero para relatório incompleto.

Snapshot de liquidez tem horário próprio, bid/ask, volume e turnover. Spread em bps = (ask-bid)/midpoint*10.000. A indisponibilidade dessa informação opcional é sinalizada sem apagar uma análise técnica válida. Taxas não são inventadas: o relatório informa `CUSTOS_NAO_CONFIGURADOS`.

São reutilizadas as tabelas market_quotes, market_candles, analyses, analysis_metrics e job_runs. Fatos existentes nunca são sobrescritos. O relatório completo não é escondido em outras tabelas: pode ser salvo em arquivo fora do checkout. O Atlas lê indicadores e preços persistidos no servidor; onde não há fonte persistida para spread/custos, mostra indisponibilidade.

## Recorrência e hospedagem

`.github/workflows/crypto-radar.yml` oferece execução manual e cron de cinco minutos. Reutiliza os secrets Supabase do repositório e tem concorrência controlada. O workflow de ações não é alterado. GitHub cron pode atrasar; isso não é uma infraestrutura de negociação de baixa latência. `CRYPTO_RUNNER` pode selecionar um runner autorizado/configurado pelo operador; o padrão é ubuntu-latest.

Recorrência só está ativa depois que o workflow estiver na branch padrão e uma execução real for confirmada. O deploy do Atlas na Vercel não inicia esse coletor. Não fazer merge automático.

## Bloqueio constatado neste ambiente

A Bybit retornou HTTP 403 com a mensagem de que a distribuição CloudFront bloqueia o país de origem desta máquina. Isso foi confirmado após o domínio ter sido liberado: é uma restrição do provedor, não falta de chave Bybit. O adapter/CLI preserva o erro. Não foram criados preços demonstrativos nem registros de mercado para substituir a resposta.

O coletor deve ser executado em infraestrutura permitida pela Bybit e conforme as condições da conta/região do operador. Um runner GitHub padrão pode encontrar a mesma restrição; a primeira execução real deve confirmar acesso antes de declarar o radar operacional.
