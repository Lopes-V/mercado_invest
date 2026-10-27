# Radar Kraken spot

A fonte ativa passa a ser Kraken, validada por teste público no mesmo tipo de executor GitHub usado pelo coletor. O adaptador Bybit continua disponível por seleção explícita; nunca há fallback silencioso ou mistura entre exchanges.

## Execução

```bash
# Por padrão: apenas validar instrumentos e mostrar catálogo, sem gravar.
python -m app.crypto_radar --provider kraken --bootstrap
# Bootstrap idempotente e coleta/análise dos três pares aprovados.
python -m app.crypto_radar --provider kraken --bootstrap --apply --persist --output /tmp/kraken-radar.json
# Fonte anterior, quando explicitamente desejada e acessível.
python -m app.crypto_radar --provider bybit --bootstrap
```

`CRYPTO_PROVIDER` ou `--provider` seleciona a fonte; o padrão da CLI/workflow é `kraken`. `CRYPTO_SYMBOLS`/`--symbols` mantém o formato canônico BTCUSDT,ETHUSDT,SOLUSDT. O adaptador traduz BTCUSDT para XBTUSDT nas consultas, após validar os metadados online/USDT da Kraken. A consulta pública não requer chave privada. Supabase usa os secrets existentes, somente no backend.

Catálogo KRAKEN e mappings `kraken` possuem IDs de assets próprios, sem reaproveitar assets BYBIT nem sobrescrever registros existentes/desativados. As tabelas e fórmulas `analysis-v2` permanecem iguais; não há migration, ordens ou notificações. `CryptoCatalog` e `CryptoStore` preservam default `bybit` para callers existentes, e a CLI passa explicitamente a fonte escolhida.

## Dados e limitações

- Preço e timestamp da cotação vêm do mesmo negócio efetivo, não do relógio da coleta. Só dados com até 120 segundos e qualidade válida permitem análise. A UI também rejeita timestamps futuros e expira a exibição com a página aberta.
- O radar fixa a janela nos 200 candles fechados mais recentes, inclusive quando a requisição cruza a abertura de um candle; assim o seed dos indicadores e a identidade da análise permanecem estáveis na repetição. Candles fechados de 15m/1h: OHLC/volume Decimal, identidade única, alinhamento, continuidade e atualização verificadas. Duplicatas conflitantes são erro. A Kraken fornece somente os últimos 720 candles; ranges antigos/truncados são recusados explicitamente.
- Análises usam as mesmas fórmulas descritas em docs/17-crypto-radar.md e não recalculam indicadores no navegador. Histórico e resultados existentes são imutáveis; repetição compara fatos na escala numeric(38,18).
- SOLUSDT apresentou negócio antigo no teste preliminar. Se isso ocorrer, o radar mostra indisponibilidade, sem flexibilizar o limite ou inferir preço de outra corretora. Os três pares continuam monitorados independentemente; um par indisponível produz relatório incompleto/exit1, sem apagar dados válidos dos demais.
- Liquidez atual/spread/turnover não são persistidos nem apresentados como disponíveis nesta versão Kraken; indicadores de volume dos candles são suportados. Custos continuam `CUSTOS_NAO_CONFIGURADOS`.
- A interface `/cripto` consulta somente KRAKEN/kraken. Preços são desse mercado, não preços executáveis garantidos na Bybit.

O workflow `.github/workflows/crypto-radar.yml` mantém cron de cinco minutos e execução manual. Sua fonte agendada só muda depois do merge na branch padrão; deploy Vercel não inicia coleta. Cron pode atrasar e a cotação pode vencer antes da próxima execução — o painel a oculta corretamente após 120 segundos. Não declarar cobertura contínua ou negociação em tempo real.

## Validação real inicial

A primeira execução da feature branch (40497250998) validou e criou os três assets KRAKEN; gravou cotação BTCUSDT e análises v2 de 15m e 1h. O job ficou `CRYPTO_REPORT_INCOMPLETE`, preservando a indisponibilidade dos outros pares. Ainda são necessárias verificações de repetição/idempotência, revisão final e Atlas publicado. Não houve merge automático.

## Entrega verificada

Backend: 582 testes passaram e 21 integrações opt-in ficaram desativadas. Atlas: 13 unitários e 14 testes de navegador passaram, além de lint/build/typecheck. Revisão independente identificou dois problemas temporais, corrigidos com regressões: timestamp futuro e janela de 201/200 candles durante virada de intervalo.

A execução 40498138810 confirmou BTCUSDT e ETHUSDT READY, SOLUSDT STALE_OR_INVALID_QUOTE. Foram verificadas quatro análises únicas (duas janelas para cada um dos dois assets), com RSI, médias e direção reais, preservadas na repetição. O relatório geral permanece incompleto quando SOL está antigo; não se declara sucesso dos três pares.

Atlas publicado em https://atlas-web-azure-two.vercel.app/cripto, deployment dpl_3avoC69PoufWFYE5ZoN8JaVPwKEm READY. Login HTTPS, fonte Kraken, preços/indicadores BTC/ETH e ausência de cotação/análise SOL foram confirmados em produção. Stocks e autenticação continuam funcionando.

PRs para revisão: backend #5 e Atlas #2. Não houve merge automático. A coleta manual na feature branch está validada para BTC/ETH; a fonte do cron da main só passa para Kraken depois do merge do backend. Não confundir essa dependência com publicação do frontend, que já foi feita.
