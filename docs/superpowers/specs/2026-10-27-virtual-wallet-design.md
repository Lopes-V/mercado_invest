# Carteira virtual e radar de realocação — desenho aprovado

## Pedido e decisões confirmadas

Texto enviado pelo usuário: carteira virtual com registros manuais, depósitos, retiradas, compras, vendas e trocas; histórico auditável; patrimônio/preço médio/ganhos; simulador; radar, alertas, concentração, histórico de sinais e backtesting. O usuário escolheu **USDT como moeda base da primeira versão**, usando as cotações Kraken existentes. Valores/percentuais do protótipo são ilustrativos e não serão cadastrados como fatos.

Não há conexão de corretora, custódia, comprovantes, transferências ou ordens reais. As operações são declaradas pelo usuário. USDT é identificado como USDT, sem equivalência implícita com USD/BRL. O investimento real de uma pessoa não é comprovado por um registro virtual.

## Estado atual encontrado

O backend já tem PortfolioCalculator Decimal para BUY/SELL, preço médio, lucro realizado, valorização, módulo de FX explícito e bases de paper trading/backtesting. As tabelas portfolios/portfolio_transactions só aceitam BUY/SELL, não têm dono por usuário, nem saldo em caixa ou troca atômica. RLS está ativada mas apenas service_role tem acesso. Atlas usa senha compartilhada e leitura administrativa no servidor. Kraken fornece BTCUSDT,ETHUSDT,SOLUSDT e análises v2; nem todo par tem negócio recente em todas as coletas.

## Abordagem proposta

Contas individuais com **Supabase Auth**, novo livro virtual separado do portfolio legado e RPC transacional no PostgreSQL. A senha compartilhada continua apenas nas telas legadas do operador; não autentica o dono de uma carteira virtual. Carteiras novas ficam numa área própria `/virtual`, com cadastro/login individuais em `/conta`, sem expor informações privadas por meio do painel legado.

Alternativas consideradas: adicionar saldo/dono às tabelas legadas exigiria atribuir carteiras antigas a usuários e mudar contratos já usados; simulação só em localStorage não oferece isolamento entre dispositivos, auditoria ou atomicidade. A separação proposta atende ao site público preservando os registros existentes. O uso de Supabase Auth/RPC é uma decisão proposta pelo implementador, não uma preferência já declarada pelo usuário.

## Fluxo do produto

1. Criar conta e entrar; criar carteira vazia com nome e base USDT.
2. Adicionar depósito virtual declarado antes de registrar compras. Nenhum depósito é lucro.
3. Comprar: informar ativo, quantidade, preço unitário USDT efetivamente pago, data/hora e taxa USDT. Não exigir cotação atual para registrar uma operação histórica declarada.
4. Vender parcialmente ou totalmente: informar quantidade/preço/data/taxa. Creditar valor líquido em caixa e reduzir posição/custo médio; rejeitar quantidade maior que a posição disponível.
5. Trocar: registrar a venda e a compra na mesma operação, com ambos os preços e taxas. Eventual diferença fica em caixa; nunca debitar um ativo sem creditar o outro.
6. Retirar saldo e registrar taxas avulsas; rejeitar saldo insuficiente.
7. Histórico completo e detalhes por operação, identificados como registros virtuais declarados. Corrigir por estorno/substituição auditável, sem apagar nem editar os lançamentos originais.

Cadastros usam inicialmente os três assets KRAKEN/USDT validados. A estrutura aceita a inclusão posterior de outros ativos após validação do catálogo; não cria catálogos ou preços fictícios.

## Proposta concreta de persistência nova

Não alterar nem migrar automaticamente portfolios legadas ou seus donos. As seguintes entidades são novas:

- `virtual_wallets`: id UUID; owner_id UUID vinculado a auth.users; nome; base_currency_code fixo USDT na versão inicial; is_active; created_at. A carteira também é a linha bloqueada para serialização de movimentações.
- `virtual_operations`: id UUID; wallet_id; sequência de registro; kind DEPOSIT/WITHDRAWAL/BUY/SELL/SWAP/FEE/REVERSAL; occurred_at; created_at; idempotency_key; hash da solicitação; referência opcional à operação estornada; origem USER_DECLARED. Unique(wallet_id,idempotency_key), garantindo repetição sem duplicar e conflito se a mesma chave trouxer outro conteúdo.
- `virtual_entries`: id; operation_id; classe CASH/ASSET; asset_id opcional; currency_code; quantidade assinada numeric(38,18); preço unitário USDT quando aplicável; categoria de entrada TRADE/FEE/CONTRIBUTION; created_at. CASH não usa asset_id; ASSET requer asset CRYPTO/KRAKEN/USDT válido. Valores são validados, sem float ou arredondamento silencioso de quantidade/preço declarado.

Depósito gera entrada de caixa positiva; retirada negativa. Compra gera ativo positivo e caixa negativo para preço e taxa; venda gera ativo negativo e caixa positivo líquido; SWAP contém as duas pernas e taxas numa única operação. Custos e lucros seguem preço médio com taxas, aproveitando os testes/matemática do core existente, sem considerar depósitos como retorno.

## Segurança e atomicidade

- RLS: dono autenticado só lê carteiras próprias e operações/entradas vinculadas a elas. Sem acesso anônimo a dados privados. Não expor service_role nem usá-la para escrever carteiras de usuários em nome deles.
- Escrita apenas por funções transacionais autorizadas, usando JWT do usuário e `auth.uid()`; nenhum owner_id arbitrário vindo do navegador define autorização. Revogar INSERT/UPDATE/DELETE diretos nas tabelas financeiras.
- Funções SECURITY DEFINER com search_path fixo, validação explícita do dono, tipos/limites e asset, sem SQL dinâmico. `SELECT ... FOR UPDATE` na carteira evita duas vendas/retiradas concorrentes usarem o mesmo saldo.
- Validar o livro efetivo por occurred_at e sequência determinística, incluindo o efeito de operações retroativas sobre todos os saldos posteriores. Rejeitar backdating que criaria posição/caixa negativo. Estornos/correções cancelam o efeito contábil original e reprocessam o histórico dependente; não são tratados como trades inversos posteriores que distorceriam o custo médio. Também passam por essa validação; desfazer uma compra já consumida exige corrigir as movimentações dependentes.
- Nenhuma operação SWAP parcialmente gravada. Erro em qualquer perna, taxa ou cálculo reverte a transação inteira.
- Limite inicial proposto de30 movimentações por minuto por usuário, aplicado no banco sob bloqueio, além dos limites nativos do Auth. Validação também no servidor; sessões verificadas contra Auth, cookies seguros e proteção de origem/CSRF.
- Quantidades, preços, taxas e totais são strings decimais no transporte. Limites de escala/overflow explícitos; resultados derivados usam precisão interna mínima de80 dígitos, escala numeric(38,18), HALF_UP explícito e rejeição de overflow. Valores declarados que não couberem exatamente na escala são recusados. Nunca converter valores financeiros em Number/float.

## Patrimônio e rentabilidade

Caixa e posições vêm exclusivamente do livro. Patrimônio = caixa USDT + valor das posições com cotação válida na mesma moeda. Se qualquer posição estiver sem preço confiável/recente, indicar total parcial/indisponível e listar o motivo; não tratar ativo sem preço como zero. Usar Kraken, observed_at, qualidade e limite120s para cripto, sem reaproveitar VALID antigo.

Preço médio inclui taxas de compra. Venda reconhece valor líquido menos custo proporcional. Ganho não realizado usa preço atual menos custo remanescente. Retorno da posição usa preço efetivamente pago, sem somar variações de mercado com bases diferentes. Aporte, retirada, ganho realizado e valorização não realizada aparecem separados; percentual global de carteira só será exibido com método explícito que ajuste fluxos de caixa, sem dividir lucro por depósitos arbitrariamente.

## Simulador, concentração e radar

O simulador é somente leitura: comparar manter posição ou realocar10%/25%/50%, usando preços válidos e taxas declaradas pelo usuário. Sem taxas informadas, resultado líquido fica indisponível, sem inventar custo zero. Cenários de preço são hipóteses explicitamente fornecidas/rotuladas; não previsões. Simular não grava uma compra; confirmação manual cria a operação declarada com idempotência.

Concentração mostra exposição percentual em USDT quando todas as posições relevantes têm preço válido. Correlação precisa de históricos alinhados e amostra suficiente, com intervalo/tamanho informados; se faltarem dados, fica indisponível.

Radar pode observar ativos fora da carteira, dentro do catálogo validado. Primeiro usa os indicadores descritivos já disponíveis, sempre com evidências, timestamps e filtros de atualização/continuidade. Não apresenta chance de alta nem recomenda troca só porque um ativo caiu. Comparação de posição em lucro com outro ativo em correção é contexto para análise, não gatilho automático.

Os pesos25/25/20/20/10 do texto são proposta experimental não validada. Capitalização, qualidade do projeto e notícias não existem hoje nas fontes/tabelas aprovadas: não produzir score geral usando campos inventados, nem redistribuir pesos silenciosamente. Documentar essas dimensões como indisponíveis até escolher/configurar fontes e metodologia verificáveis. Um eventual score é nota de regras, não probabilidade; requer versionamento/evidências e avaliação histórica própria.

Alertas da nova carteira serão inicialmente **dentro do site**, configurados pelo usuário para alvo de lucro, perda e mudança técnica, sem acionar Telegram/email ou operar ativos. Guardar evento/snapshot imutável com preços, métricas, versão e observação real. Histórico de sinais permite verificar resultados futuros sem usar informação futura no sinal original.

Backtesting reaproveita o core existente com custos explícitos, dados suficientes e separação temporal; sem look-ahead nem promessa de taxa de acerto. Retenção pública Kraken limitada720 candles pode tornar uma avaliação longa indisponível; não prometer amostra/validação estatística inexistente. Fontes adicionais como CoinGecko dependem de plano/limites/credenciais confirmados e serão configuradas explicitamente, sem substituir silenciosamente Kraken.

## Entregas propostas

1. Auth individual, nova persistência/RLS/RPC, carteira vazia, depósitos/retiradas, compra/venda/troca/taxas, histórico e cálculos de posição/patrimônio. Testes de isolamento, concorrência, rollback, idempotência, backdating e decimais antes de publicar escrita.
2. Simulador, concentração e radar técnico ligado às posições e mercado, preservando sinais insuficientes e taxas desconhecidas.
3. Alertas internos, histórico versionado, backtesting e avaliação de fontes para dimensões ainda ausentes. Não declarar essas funções concluídas na primeira entrega.

Os três lotes preservam o pedido completo, mas permitem revisar e validar cada parte sem ativar operações reais. Este documento não aplica migrations, cria usuários, envia mensagens nem muda autenticação de produção.

## Critérios de aceite

ContasA/B não leem/escrevem carteiras uma da outra; double-click/retry não duplica; concorrência não gasta duas vezes; falha na segunda perna do swap não debita a primeira; saldos/preço médio/ganhos incluem taxas sem confundir depósito e lucro; lançamento retroativo incompatível é recusado; nenhum valor de protótipo aparece como patrimônio real; moedas não são misturadas; dados ausentes/futuros/antigos não geram patrimônio completo, score ou alerta; administrador não atribui carteiras legadas ao primeiro usuário cadastrado; fonte/versão/data e natureza virtual ficam visíveis.

## Aprovação necessária antes da nova escrita

Confirmar esta proposta de carteira individual USDT, persistência nova e Auth/RPC antes da implementação e aplicação de alterações no banco. A etapa de atualização mais frequente, já autorizada, segue independente.

## Revisão do desenho

Builder check independente: PASS, sem decisões materiais pendentes do usuário além da aprovação desta proposta. Foram explicitados replay de estornos, precisão Decimal e separação entre sessões/auxiliares administrativos e contas individuais. Nenhum código da carteira ou migration foi aplicado.

## Aprovação

Usuário respondeu sim ao desenho no chat em27/10/2026; USDT confirmado. Prosseguir com implementação sem repetir a aprovação. Execução de DDL depende de acesso real ao banco; credencial REST não implica acesso SQL.
