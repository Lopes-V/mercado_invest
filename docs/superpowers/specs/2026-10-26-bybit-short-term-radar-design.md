# Radar Bybit para cripto de curto prazo

## Pedido e direção

O usuário pediu melhorar o backend de coleta/análise, explicou que pretende avaliar compras de cripto para operações rápidas de poucos dias e escolheu a Bybit. O produto deve transformar dados reais em um radar legível no Atlas. Escopo aprovado pelo usuário antes da implementação.

Decisões propostas pelo implementador: começar pelo mercado **spot em USDT**, com BTCUSDT, ETHUSDT e SOLUSDT como lista inicial configurável; observar candles de 15 minutos e de 1 hora. A escolha de spot não presume que o usuário queira contratos ou alavancagem. Compra e venda permanecem decisões do operador; esta entrega não inclui integração de ordens.

## O que existe e por que mudar

- Backend Python modular com adapters BRAPI/Twelve Data, normalização Decimal, QualityEngine, Supabase e jobs. O Atlas Next.js lê o banco no servidor.
- A coleta atual acompanha 15 ativos e existe histórico real de análises. A suíte atual executou 415 testes aprovados e 21 integrações opt-in ignoradas.
- O RSI chamado de Wilder usa média simples da última janela; volume ausente é convertido em zero; volatilidade usa uma janela diferente da referência publicada. Esses comportamentos precisam de uma versão corrigida, com testes numéricos.
- Policies de ações já congeladas dependem das fórmulas existentes. Alterá-las silenciosamente invalidaria a comparabilidade dos scores.
- GitHub Actions a cada 30 minutos não é uma infraestrutura de atualização rápida; Vercel não mantém um worker Python residente.

## Abordagens

1. **Recomendação, coerente com o backend solicitado:** adapter Bybit e análise versionada em `mercado_invest`; fatos persistidos no Supabase existente; Atlas apresenta os resultados. Reaproveita os modelos, auditoria e autenticação e mantém uma fonte para os cálculos.
2. Consultar e calcular tudo no frontend: reduz a integração inicial, mas duplica o motor Python e mistura responsabilidades. Não atende à melhoria do backend pedida pelo usuário.
3. Plataforma de execução automática/futuros: exige APIs privadas, gestão de posições, taxas efetivas e outro escopo de validação. Não integra esta primeira entrega de análise.

A implementação proposta segue a primeira abordagem; a aprovação deste documento confirma esse caminho e as escolhas iniciais acima.

## Primeira entrega

### 1. Coleta pública Bybit V5

Implementar um adapter `bybit` seguindo `MarketDataProvider`, usando o transporte HTTP existente com timeout, TLS verificado e parsing Decimal. `category=spot` deve ser explícito: a API de kline assume `linear` quando a categoria é omitida.

Endpoints oficiais:

- `/v5/market/instruments-info`: identidade, base/quote e estado Trading do par.
- `/v5/market/recent-trade`: preço e timestamp do último negócio; não tratar o horário de resposta HTTP como horário do negócio.
- `/v5/market/kline`: OHLCV por intervalo, com paginação até o intervalo solicitado.
- `/v5/market/tickers`: snapshot opcional de bid/ask, turnover e volume 24h, com horário próprio de observação. Esse snapshot não substitui o timestamp do último negócio.

Validar retCode, categoria, símbolo, formato, números finitos, coerência OHLC e limites temporais. Ordenar candles por tempo, remover apenas duplicatas idênticas de páginas sobrepostas e rejeitar duplicatas conflitantes. Só enviar candles encerrados à análise. Para spot, volume é quantidade do ativo base; turnover é quantidade da moeda de cotação. Não misturar os dois.

A seleção inicial é uma allowlist configurável; não anunciar cobertura de todo o mercado. USDT deve ser identificado como USDT, sem conversão implícita para dólar ou real.

### 2. Indicadores corrigidos e versionados

Criar `analysis-v2` explicitamente selecionável, preservando `analysis-v1` no pipeline de ações, calibração e policies existentes. Não mudar scores, thresholds nem a versão congelada atualmente usada em produção.

A nova análise deve incluir RSI de Wilder, EMA20/EMA50, retorno e momentum percentual por janela, volatilidade de retornos da janela informada, volume médio/relativo e ATR14. Cada métrica carrega período e versão. Fórmulas e escalas devem ser documentadas: retorno/volatilidade como razões; RSI entre 0 e 100; ATR na moeda de cotação. Períodos configuráveis têm limites e warm-up suficiente, sem preenchimento sintético.

Ausência de volume não vira zero. Histórico curto, lacunas, divisão por zero, preços inadequados ao cálculo ou dados inválidos produzem motivos explícitos de indisponibilidade. As janelas de 15m e 1h devem ser avaliadas separadamente, sem interpolar candles.

### 3. Radar e relatório

Produzir relatório estruturado por par com preço e referência do último negócio, instante de avaliação, intervalos, indicadores, direção observada em cada janela, volume e fatores de risco. Informar divergência entre janelas e dados insuficientes. Não criar probabilidades de lucro ou scores calibrados usando regras de ações.

O relatório descritivo usa relações transparentes entre indicadores, por exemplo preço/EMA e EMA20/EMA50, sem atribuir taxa de sucesso. Rankings permitidos inicialmente: variação, volume relativo e volatilidade, com unidades e período iguais. Ranking não é uma ordem de compra.

Se bid/ask estiverem disponíveis, calcular spread em bps com fórmula publicada e timestamp próprio. Sem taxas reais configuradas, informar `CUSTOS_NAO_CONFIGURADOS`: não estimar retorno líquido ou ponto de equilíbrio com taxas inventadas. Spread atual e taxas não são misturados silenciosamente com snapshots históricos.

Reutilizar `market_quotes`, `market_candles`, `analyses` e `analysis_metrics` para os fatos suportados pelo schema. O JSON de relatório completo, incluindo snapshot de liquidez e seu horário, pode ser retornado pelo comando do backend e salvo em caminho local ignorado para auditoria. Não inventar colunas nem esconder esse snapshot em outro tipo de registro.

### 4. Exibição no Atlas

Adicionar a seção Cripto usando leitura autenticada no servidor. Exibir os pares monitorados, preço/moeda/horário, tendência e indicadores por janela e avisos de indisponibilidade. Ler os indicadores versionados persistidos pelo backend. Não recalcular as fórmulas Python no navegador.

Na ausência de análise persistida válida/recente, o Atlas mostra um estado genérico honesto: “Aguardando análise válida/recente”, sem inventar a causa. Motivos específicos por ativo ficam no relatório estruturado do backend; falhas globais de execução ficam em job_runs/logs existentes. Não inferir falha, ausência de volume ou gap apenas da ausência de uma métrica. Dados de liquidez que não tenham persistência equivalente devem aparecer como indisponíveis no painel nesta primeira entrega; o relatório do backend pode expor o snapshot atual com seu timestamp. Persistência histórica de livro/spread é uma extensão que exige desenho de schema separado. O painel não declara custos líquidos disponíveis quando eles não estão configurados.

Preservar DESIGN.md, login, ocultação de valores, fluxo de ações e demais telas. Candles de cripto podem ser exibidos nos intervalos suportados pelo adapter, com fornecedor e versão identificados.

## Persistência, catálogo e execução

- Não há migration nesta primeira entrega. Se um requisito exigir nova tabela ou coluna, parar nesse ponto e apresentar a alteração concreta antes de aplicá-la.
- Preparar comando de bootstrap idempotente para os três pares, moeda USDT e exchange Bybit, preservando IDs e registros existentes. Por padrão o comando mostra o plano; `--apply` cria apenas o que falta. Não criar moedas fiduciárias equivalentes nem alterar mappings de ações.
- Preparar um comando de execução única e um job próprio de coleta/análise cripto, com allowlist e intervalos separados da automação de ações. Persistir apenas fatos de mercado e indicadores, usando repositories existentes.
- Propor intervalo operacional de 5 minutos para atualização dos indicadores; candles fechados de 15m/1h determinam a janela analisada. Não prometer execução de baixa latência ou preços em tempo real a partir de cron.
- Executor proposto: workflow GitHub Actions exclusivo para cripto, agendado a cada 5 minutos e também acionável manualmente. Reutilizar os secrets Supabase já utilizados pelo backend; Bybit pública não usa chave privada. Preservar integralmente o workflow/schedule das ações. O cron pode atrasar e não fornece atualização instantânea.
- Disponibilizar execução única local e o novo workflow. Publicação do workflow na branch padrão e ao menos uma execução real bem-sucedida são pré-requisitos para afirmar que a coleta recorrente está ativa. Se o acesso ao GitHub ou a revisão/merge impedir isso, entregar as mudanças concretas para revisão e declarar explicitamente que a recorrência está pendente; não confundir deploy do Atlas com deploy do coletor. Não fazer merge automático nem alterar gates/variáveis de produção das ações. Worker persistente é alternativa de hospedagem futura, não pré-requisito desta primeira entrega.
- Política de freshness para cripto deve ser explícita e independente do limite de vários dias usado na referência de ações. Verificar novamente no momento da análise. Não reaproveitar `VALID` antigo como garantia permanente.

## Validação e critérios de conclusão

- Testes numéricos de Wilder e demais indicadores com valores esperados, warm-up, ausência de volume e janelas corretas.
- Testes do adapter cobrindo identidade, retCode, arrays invertidos, paginação, candle aberto, timestamps, Decimal, erro transitório e payload malformado.
- Testes de serviço garantindo isolamento da policy antiga, proteção de dados e indisponibilidade explícita.
- Suíte existente do backend continua verde; testes de navegador incluem a seção Cripto, autenticação e estados vazios/de falha.
- Smoke real na Bybit usando apenas endpoints públicos; validação de persistência limitada aos pares aprovados e sem ordens ou notificações.
- Build/lint/tipos e deploy do Atlas depois das mudanças aprovadas, com validação do painel publicado. O status do executor de coleta deve ser relatado separadamente do deploy do frontend.

## Bloqueios observados

Inicialmente o proxy recusava o CONNECT. Após liberar o domínio, a Bybit respondeu HTTP 403 com bloqueio do país de origem pela distribuição CloudFront. A coleta real permanece bloqueada por restrição regional do provedor, não por falta de chave. Nenhum catálogo ou fato de mercado foi criado para substituir essa resposta. A documentação foi consultada pelo repositório oficial público `bybit-exchange/docs` em raw.githubusercontent.com. A coleta pública não exige chave privada da conta Bybit; executar apenas em infraestrutura permitida pelo provedor.

## Decisões deixadas ao implementador

Nomes internos de módulos/comandos, organização dos testes, tamanhos de lotes, limites conservadores de requests e detalhes visuais que sigam DESIGN.md. Nenhuma decisão pode relaxar validação de TLS, inventar dados financeiros, reutilizar scores incompatíveis ou publicar segredos.

## Referências oficiais

- https://bybit-exchange.github.io/docs/v5/market/kline
- https://bybit-exchange.github.io/docs/v5/market/tickers
- https://github.com/bybit-exchange/docs

## Revisão independente do desenho

Foram levantadas duas ambiguidades e resolvidas nesta proposta: (1) o Atlas usa estado genérico de indisponibilidade quando não há um resultado persistido confiável, enquanto o relatório do backend registra causas específicas; não será criada uma coluna de status implicitamente; (2) o executor escolhido é um workflow próprio no GitHub Actions a cada 5 minutos, com publicação e execução verificadas antes de declarar recorrência ativa. Essas são decisões propostas pelo implementador e fazem parte da aprovação do escopo.
