# Calibração da Opportunity Policy

## Objetivo

Gerar uma `OPPORTUNITY_RULES_JSON` candidata a partir de histórico, sem escolher
thresholds financeiros manualmente e sem alterar a configuração de produção.

A calibração não usa Gemini, Telegram, paper trading nem ordens reais.

## Separação temporal

O histórico é separado cronologicamente em três partes:

1. **Treino**: gera os thresholds candidatos por quantis.
2. **Validação**: escolhe entre os candidatos.
3. **Teste holdout**: avalia uma única vez o candidato já escolhido.

O teste holdout não participa da escolha da regra. Se ele não tiver amostra
mínima, hit-rate >= 50% e retorno futuro médio positivo, o resultado é
`RELEASE_READY=false` e nenhuma `OPPORTUNITY_RULES_JSON` é liberada.

Isso reduz, mas não elimina, overfitting. Resultado histórico não garante retorno
futuro.

## Robustez e promoção

Os cortes são globais para todos os ativos elegíveis: um outcome não pode cruzar
o limite entre treino, validação ou holdout. Depois de selecionada, uma regra é
avaliada com custo round-trip em bps, concentração por ativo, distribuição mensal
e bootstrap determinístico. Esses diagnósticos não recalibram thresholds.

`CALIBRATION_RELEASE_READY` representa somente a evidência histórica. A policy
aprovada deve ser congelada em uma nova versão e observada em shadow mode, sem
Telegram ou trading. `PRODUCTION_READY` só pode ser verdadeiro após evidência
futura realizada, retorno líquido positivo e habilitação operacional explícita.

Para congelar um relatório já aprovado sem alterar GitHub Variables:

```bash
python -m app.freeze_opportunity_policy --report calibration.json --policy-version candidate-v1
```

## Métricas candidatas

Somente métricas comparáveis entre ativos entram na busca inicial:

- `RETURN` — categoria `TREND`
- `RSI` — categoria `MOMENTUM`
- `VOLATILITY` — categoria `RISK`
- `MAX_DRAWDOWN` — categoria `RISK`

`SMA`, `MOMENTUM` absoluto e `AVERAGE_VOLUME` não entram nesta primeira
calibração porque seus valores absolutos não são diretamente comparáveis entre
ativos com preços/volumes muito diferentes.

Cada candidato combina duas categorias de evidência diferentes e usa a mesma
semântica do `OpportunityEngine` de produção.

## Execução

A calibração inicial usa BRAPI e os mappings ativos já cadastrados no Supabase:

```bash
python -m app.calibrate_opportunity \
  --history-days 730 \
  --analysis-lookback-days 30 \
  --analysis-period 14 \
  --forward-horizon 5 \
  --max-assets 5 \
  --min-signals 8
```

Para limitar aos tickers desejados:

```bash
python -m app.calibrate_opportunity \
  --symbols PETR4,VALE3,ITUB4 \
  --history-days 730
```

O comando é read-only no Supabase. O histórico é obtido diretamente da BRAPI,
normalizado pelo adapter existente e usado apenas para replay.

## Resultado

Quando o holdout final passar:

```text
RELEASE_READY=true
OPPORTUNITY_RULES_JSON=[...]
```

Quando não houver evidência suficiente:

```text
RELEASE_READY=false
Evidência holdout insuficiente. Não substitua OPPORTUNITY_RULES_JSON.
```

Não altere `AUTOMATION_ENABLED=true` apenas porque uma calibração passou.
Primeiro revise tamanho de amostra, horizonte, ativos usados e comportamento da
policy em mais de uma janela histórica.
