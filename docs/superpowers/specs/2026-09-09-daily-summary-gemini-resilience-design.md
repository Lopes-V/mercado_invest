# Resiliência do Gemini e fechamento diário consolidado

## Objetivo

Evitar que indisponibilidade transitória do Gemini interrompa a pipeline de
oportunidades e substituir o summary operacional enviado a cada execução por
um fechamento diário consolidado, às 22:00 em `America/Sao_Paulo`.

O sistema continua sendo de análise e alerta. O Gemini não fornece preços,
não calcula indicadores, não altera score ou nível e não produz ordens de
compra ou venda.

## Limites e invariantes

- Não criar ou alterar migrations, tabelas, policy congelada, `candidate-v1`,
  thresholds ou gates de produção.
- Não modificar GitHub Secrets ou Repository Variables remotas.
- Persistir e utilizar somente dados de mercado `VALID`, com timestamps.
- Não estimar preço, indicador, resumo Gemini ou risco ausente.
- Manter shadow sem Gemini, Telegram, `AlertService` ou paper trading.
- Manter alertas individuais sujeitos a qualidade, elegibilidade, dedupe e
  cooldown existentes.

## Pipeline de oportunidade e Gemini

A cada 30 minutos, cada pipeline de provider mantém a sequência atual:

```text
dados VALID -> análise determinística -> policy congelada -> persistência
                                                   |
                         INTERESTING/HIGH_INTEREST +-- Gemini qualitativo
```

O adapter Gemini tentará no máximo três chamadas totais para indisponibilidade
transitória: HTTP `429`, HTTP `5xx`, timeout ou erro de rede. Os intervalos de
espera crescem entre tentativas e são injetáveis em testes. Erros HTTP não
transitórios e respostas que não passam no schema continuam rejeitados.

A pipeline captura apenas erros de domínio da IA, registra uma ocorrência
sanitizada (`AI unavailable` para indisponibilidade; resposta rejeitada para
falha de validação) e persiste a mesma decisão determinística sem `ai_run_id`.
Assim, a falha é observável, mas não torna a rodada financeira dependente de
um serviço externo qualitativo. Erros de dados, qualidade, persistência e
policy continuam fatais para a análise dependente.

O prompt exige que `summary`, fatores e riscos voltados ao usuário estejam em
`pt-BR`. As classificações estruturadas internas continuam os enums já
contratados.

## Fechamento diário

O summary por provider e por execução deixa de enviar Telegram. Um
`DailyInvestmentSummaryJob` separado é agendado para o slot de 22:00 no fuso
`America/Sao_Paulo`, após as pipelines de todos os providers. A agenda diária
só disponibiliza o job em uma janela explícita desse slot: ela não gera um
fechamento atrasado ao iniciar o worker em outro horário.

O job lê os registros já auditáveis no intervalo local `[00:00, 24:00)`:

- oportunidades e análises correspondentes;
- métricas persistidas e última cotação `VALID` disponível no encerramento;
- execução Gemini vinculada à oportunidade, quando existente.

Os novos métodos de repositório são somente de leitura, tipados e validam as
respostas PostgREST. Não há estado em memória entre execuções nem migration.

Para cada ativo, a avaliação final do dia determina seu estado:

- **nova**: terminou `INTERESTING`/`HIGH_INTEREST` e não estava relevante na
  avaliação anterior ao início do dia;
- **mantida**: terminou relevante e já estava relevante antes do dia;
- **deixou de ser interessante**: foi relevante durante o dia, mas terminou
  em `NONE` ou `WATCH`.

As melhores oportunidades incluem apenas ativos que terminam relevantes,
ordenados por score determinístico decrescente e símbolo como desempate. Os
riscos são agregados apenas de respostas Gemini validadas associadas às
oportunidades apresentadas. Caso não haja ativo relevante no fechamento, a
mensagem declara isso claramente.

O job envia uma mensagem por `TELEGRAM_ALERT_CHAT_IDS` diretamente pelo
transport Telegram. Ele não chama `AlertService`, não cria registros em
`alerts` e não emite um segundo alerta individual. Alertas individuais seguem
o fluxo normal; o fechamento apenas os consolida.

## Apresentação

Uma camada de apresentação recebe fatos já persistidos e valores `Decimal`.
Ela não reavalia policy ou indicadores. Os formatos previstos são:

- retorno e volatilidade: percentual com sinal quando aplicável e duas casas;
- RSI e score: duas casas no máximo;
- drawdown: percentual negativo para comunicar perda a partir do pico;
- volume: unidades abreviadas como `mi` e `bi`, sem transformar números em
  links de telefone no Telegram;
- preço e SMA: valor monetário na moeda da cotação, como `R$ 15,43`.

Métricas indisponíveis são omitidas; nunca são substituídas por zero ou texto
que pareça dado financeiro.

## Configuração, observabilidade e testes

`TELEGRAM_SUMMARY_ENABLED` continua sendo o controle do fechamento, e a
configuração ganha a hora diária BRT, com default `22`; a workflow preserva o
default sem alterar estado remoto. Logs guardam somente contagens, slot,
provider e categoria sanitizada de falha, nunca tokens, headers ou chat IDs.

Cobertura mínima:

- retries para erro transitório, esgotamento e resposta válida após retry;
- continuidade da oportunidade sem contexto Gemini após falha de IA;
- prompt em pt-BR e rejeição de resposta estruturada inválida;
- formatação Decimal de preço, percentuais, volume, RSI e drawdown;
- fechamento único diário, multi-provider, ranking e ausência de relevante;
- estados nova, mantida e deixou de ser interessante;
- isolamento de alertas individuais/cooldown e de shadow;
- validação de configuração, workflow e documentação.
