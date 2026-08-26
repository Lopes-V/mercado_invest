# Pipeline deterministico de Opportunity, Gemini e Telegram

## Objetivo

Reduzir chamadas indiscriminadas ao Gemini, manter a decisao financeira inteiramente deterministica e separar summary operacional de alertas de oportunidade. O sistema continua de analise e alerta: nao existe ordem de compra, venda ou integracao com corretora.

## Restricoes imutaveis

- `candidate-v1`, seus thresholds, pesos, categorias e calibracao nao serao editados.
- Producao e simulacao leem regras somente de `frozen_opportunity_policies` por `OPPORTUNITY_POLICY_VERSION`; a record deve existir, ser `FROZEN` e ter `calibration_release_ready=true`.
- `OPPORTUNITY_RULES_JSON` nao influencia execucao. Se estiver definida localmente, a inicializacao falha com erro claro de configuracao obsoleta.
- `AUTOMATION_ENABLED` e `PRODUCTION_READY` permanecem falsos nos exemplos e nenhum GitHub Secret ou Variable remoto sera alterado.
- Shadow continua recebendo somente policy congelada, candles validos, analise e `ShadowService`; sem Gemini, Telegram, `AlertService` ou paper trading.
- Nenhuma migration sera criada. `opportunities.ai_run_id` ja aceita `NULL` e `alerts.dedupe_key` ja e texto unico, suficiente para identidade por chat.

## Arquitetura e lifecycle

```text
Market Data -> Quality -> Analysis -> Deterministic Pre-filter
                                           |
                       +-------------------+-------------------+
                       |                                       |
                 NONE / WATCH                  INTERESTING / HIGH_INTEREST
                       |                                       |
       persistir sem ai_run_id e incluir summary          Gemini qualitativo
                                                               |
                                           persistir a mesma avaliacao com ai_run_id
                                                               |
                                                          Alert -> Telegram
```

Para cada mapping ativo, quote/candles ausentes ou diferentes de `VALID`, asset inativo ou market inativo bloqueiam aquele ativo antes de analise/IA e entram na contagem de quality do summary. Nenhum dado ausente e estimado.

Depois de analise persistida e coerente com o ultimo candle, `OpportunityPreFilter` chama o proprio `OpportunityEngine`. Ele gera score, nivel, evidencias financeiras, regras atendidas e dados de apresentacao. Nao existe segunda formula de score.

`NONE` e `WATCH` sao persistidos sem `ai_run_id`, valor semanticamente valido no schema atual. WATCH e acompanhamento operacional, nao recomendacao nem alerta individual. `INTERESTING` e `HIGH_INTEREST` chamam Gemini somente quando o modo permite. Gemini produz `summary`, fatores positivos/negativos, riscos e confianca; o resultado final preserva exatamente score, nivel, categorias e criterios do pre-filter.

## Policy e IA

`load_frozen_opportunity_policy` continua validando/construindo rules da record persistida. O caminho de producao adiciona `validate_production_frozen_policy`: qualquer `evidence_category=AI_CONTEXT` falha com mensagem de que a policy e um modelo legado incompativel com o pipeline deterministico. Shadow nao recebe esta dependencia nova nem integracao de IA.

`OpportunityEngine.assess` deixa de aceitar `ai_positive`; todos os call sites internos serao atualizados. Isto remove a API enganosa e a possibilidade de uma resposta Gemini acrescentar categoria, ponto ou nivel. A busca dos call sites e os testes existentes mostram uso interno controlado, permitindo remocao em vez de manter logica morta.

`OPPORTUNITY_MINIMUM_CATEGORIES` e `OPPORTUNITY_MAX_AI_WEIGHT` deixam de ser inputs de runtime. A semantica existente de duas categorias permanece no `OpportunityPolicy`, sem mudar candidate-v1 ou suas rules. Uma policy futura que precise semantica diversa devera ter metadata imutavel em tarefa separada.

## Componentes

### `app/opportunity/pipeline.py`

```python
def assess(
    self,
    *,
    metrics: dict[str, Decimal],
    quote_quality: DataQuality,
    reference_at: datetime,
    evaluated_at: datetime,
    symbol: str,
) -> PreFilteredOpportunity: ...
```

`PreFilteredOpportunity` contem `OpportunityAssessment`, metricas disponiveis, rules atendidas e `presentation_rank`. O rank serve somente ao summary e ordena por score, numero de criterios atendidos, proximidade normalizada e simbolo. Proximidade usa `value / threshold` para GT/GTE positivos e `threshold / value` para LT/LTE com valor positivo; denominadores invalidos ou zero contribuem `Decimal("0")`. Ela nunca entra no engine, score persistido ou nivel.

`OpportunityService.record` persiste uma avaliacao ja calculada. Cada analise gera uma opportunity: `ai_run_id=None` para NONE/WATCH e AI run associado apenas quando Gemini foi realmente chamado.

### `app/telegram/messages.py`

Dataclasses de apresentacao e `TelegramMessageFormatter` implementam `render_summary(summary)` e `render_opportunity_alert(alert)`. O formatter so organiza texto em portugues. Recebe indicadores, criterios e contexto ja calculados; nao consulta policy, nao calcula score, nao decide elegibilidade e nao inventa metricas ausentes.

`PipelineSummary` inclui ativos considerados, analisados com sucesso, bloqueados por quality, contagem NONE/WATCH/INTERESTING/HIGH_INTEREST e top N resultados. O summary mostra policy/rules reais e uma mensagem de ausencia de oportunidade quando aplicavel. Ele e operacional e nao cria linha em `alerts`.

## Settings e modos explicitos

| Variavel | Semantica | Default |
| --- | --- | --- |
| `TELEGRAM_ALERT_CHAT_IDS` | CSV ordenado de chat IDs nao-zero para summary/alertas. | vazio |
| `TELEGRAM_SUMMARY_ENABLED` | Habilita summary operacional. | `true` |
| `TELEGRAM_SUMMARY_TOP_N` | Limite inteiro entre 1 e 10. | `5` |
| `PIPELINE_SIMULATION_ENABLED` | Habilita explicitamente simulacao. | `false` |
| `TELEGRAM_DRY_RUN` | Confirma transporte Telegram sem HTTP na simulacao. | `false` |
| `DRY_RUN_ALLOW_AI` | Permite Gemini externo somente na simulacao. | `false` |

`TELEGRAM_ALLOWED_USER_IDS` continua um `frozenset` de IDs positivos exclusivo de polling/comandos do bot. `TELEGRAM_ALERT_CHAT_IDS` aceita IDs negativos de grupos/canais, mantem a ordem escrita e rejeita zero/duplicatas.

```text
disabled: AUTOMATED_PIPELINE_ENABLED=false
production: AUTOMATED_PIPELINE_ENABLED=true,
            PIPELINE_SIMULATION_ENABLED=false,
            AUTOMATION_ENABLED=true, PRODUCTION_READY=true
dry-run: AUTOMATED_PIPELINE_ENABLED=true,
         PIPELINE_SIMULATION_ENABLED=true, TELEGRAM_DRY_RUN=true
```

Producao exige token Telegram, recipients, Gemini e frozen policy valida. Dry-run exige recipients/policy validos, sempre usa sender sem HTTP e cria Gemini apenas com `DRY_RUN_ALLOW_AI=true` e credenciais presentes. Logo dry-run e um modo nomeado e observavel, nunca equivalencia ou liberacao dos gates. Sem IA, registra `gemini_calls_skipped_simulation` e nao alega contexto Gemini.

## Recipients, AlertService e dry-run

`AlertService.send` recebe conteudo pronto e `dry_run`. Em producao mantem quality, nivel, cooldown, dedupe e gates. Em simulacao aplica os mesmos checks de quality/nivel/cooldown, renderiza e marca `SUPPRESSED` com motivo `dry_run` antes de qualquer efeito externo.

```text
<asset_id>:<opportunity_id>:<recipient_chat_id>:<evaluated_at UTC>
```

sera a dedupe key. Cada recipient recebe chamada independente. Como a constraint existente so exige unicidade do texto completo, chats distintos produzem chaves distintas e o mesmo chat/execucao continua idempotente; testes cobrirao ambos.

`TelegramClient(dry_run=True)` captura/renderiza mensagens e retorna resultado sintetico sem executar HTTP. Logs emitem somente contagens, tipo e modo; nao logam token, headers, segredo, chave Gemini ou chat ID desnecessario.

## Configuracao, workflow e docs

`.env.example` documentara coleta, history, shadow, policy por versao, Gemini, Telegram, summary, cooldown, simulacao e intervalos. Deixara explicitos `AUTOMATION_ENABLED=false` e `PRODUCTION_READY=false`. O workflow deixa de encaminhar `OPPORTUNITY_RULES_JSON`, rules runtime ou peso de IA; recebe apenas controles nao sensiveis de recipients, summary e simulacao. Nenhum estado remoto sera modificado.

README e docs explicarao pre-filter, WATCH versus alerta, summary, recipients, dry-run, policy congelada, gates e isolamento shadow.

## Observabilidade e aceitacao

No fim de cada job, um evento seguro agrega considerados, analisados, bloqueados, niveis, Gemini evitados/efetivos, summaries renderizados/enviados, alertas renderizados/enviados/suprimidos e motivos de supressao agregados.

Os testes novos cobrem NONE/WATCH sem IA, candidatos com IA, invariancia financeira a Gemini, bloqueio quality, isolamento shadow, ranking/limite do summary, ausencia de metricas inventadas, dry-run sem HTTP, AI dry-run opt-in, recipients multiplos, dedupe por recipient, separacao de allowed IDs e falhas claras de policy inexistente/inadequada/AI_CONTEXT. A suite completa, checks estaticos, `git diff --check` e inspecao de segredos sao obrigatorios antes da entrega.

## Decisao de schema

Nao ha migration. `ai_run_id` nullable ja modela NONE/WATCH, `dedupe_key unique` ja aceita a identidade composta nova e summary e intencionalmente fora de `alerts`. Se surgir limitacao diferente, a implementacao para antes de criar SQL e pede autorizacao especifica.
