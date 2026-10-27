# Carteira cripto útil — evolução do desenho aprovado

## Objetivo e autorização

O usuário pediu uma revisão crítica: visual aceitável, pouca utilidade; remover o inútil e acrescentar funcionalidades úteis. Contexto já confirmado: operações de cripto de poucos dias, Kraken/USDT e carteira virtual sem corretora. O desenho aprovado `2026-10-27-virtual-wallet-design.md` já prevê simulador, concentração e radar na segunda entrega. Esta evolução executa esse objetivo e simplifica os fluxos existentes; as escolhas abaixo são do implementador sob a orientação de exercer julgamento, não novas preferências atribuídas ao usuário. Prosseguir sem repetir aprovação de funcionalidades já autorizadas.

## Diagnóstico

Hoje há duas carteiras no menu, um hero alto, seis números sem hierarquia, um formulário contábil permanente, criação de outra carteira sempre exposta, histórico verboso e preços repetidos em cartões sem ação. As posições não dão atalhos para vender/comprar/simular. A análise técnica existente vive atrás do acesso legado. A interface consome espaço para registrar dados, mas pouco ajuda a acompanhar uma posição e comparar uma troca.

## Abordagens

1. Apenas reduzir textos e formularios: menor esforço, mas não entrega a utilidade solicitada.
2. Reescrever autenticação/livro e criar novo backend: alto risco de regressão e outra ativação SQL, sem benefício para esses fluxos.
3. Evoluir a carteira existente com ações contextuais, simulador e leitura de pesquisa pública: escolhida pelo implementador. Preserva contas, saldos, precisão, auditoria e mecanismos de retry; não exige nova migração ou fonte.

## Resultado do produto

Uma única entrada principal **Carteira** aponta a `/virtual`. A antiga continua acessível em área secundária do operador como portfólio anterior, preservando seus dados e guardas. Nada é apagado ou atribuído a outro usuário.

A carteira abre com resumo curto (patrimônio, caixa e ganho em aberto), ações Adicionar saldo/Comprar e posições compactas com quantidade, preço médio/atual, ganho USDT/% e peso. Vender, Comprar e Simular troca partem da posição escolhida. Contabilidade complementar, taxa avulsa, retirada, estorno e gerenciamento de outras carteiras ficam em detalhes/ações secundárias; não são excluídos do livro.

Lançamentos abrem somente quando solicitados. Ativo e saldo disponível são contextualizados; venda oferece25/50/100% sem exceder a quantidade. Data local pode iniciar no momento atual e ser alterada. Cotação atual só preenche preço quando o usuário solicita e a fonte está válida; operações históricas não dependem de preço atual. Taxa zero exige declaração explícita. Modal fechado não descarta silenciosamente uma confirmação incerta. Retry mantém chave e payload, inclusive nas falhas de leitura/identidade já testadas.

Histórico permite entender moeda, quantidade/valor, data e estorno sem exibir JSON, UUIDs ou códigos internos como conteúdo principal. Detalhes técnicos permanecem em expansão auditável. Não inventar rentabilidade global que confunda aportes com lucro.

## Simulador

Escolher ativo da posição, percentual10/25/50/100 e moeda de destino do catálogo Kraken. Mostrar quanto seria vendido, valor bruto, taxas explícitas de venda/compra, quantidade estimada de destino, caixa remanescente e resultado realizado estimado do trecho. Sem ambas as taxas, resultado líquido fica indisponível. Nunca assumir custo zero.

Comparar manter o trecho ou trocá-lo com cenários percentuais opcionais fornecidos para ambas as moedas. Rotular hipóteses e valores antes de custos de saída futuros; não prever preço ou probabilidade. Usar Decimal com precisão80, derivadas HALF_UP18 e quantidades truncadas para18 casas, sem Number em dinheiro. Rejeitar overflow, saldos/taxas impossíveis e cenários abaixo de-100%. Preços precisam ser positivos, Kraken/USDT, válidos, não futuros e com até120s. Falta de preço desabilita simulação, não o registro histórico.

Preparar troca preenche um lançamento declarado que ainda exige revisão/confirmação; simular não grava. Dados vencidos não podem preparar operação como se fossem atuais.

## Pesquisa do mercado

Radar enxuto para o catálogo existente: tendência15m/1h, RSI, volatilidade/ATR e contexto da posição. Sem nota de oportunidade, notícias inventadas ou probabilidade. Mostrar alinhamento/divergência dos intervalos e fontes/horários; dados insuficientes ficam indisponíveis. Detalhe do ativo pode mostrar até96 candles fechados de15m, com lacunas visíveis. Não conectar períodos ausentes nem mostrar candle aberto/futuro como fato fechado.

Para evitar nova instalação SQL, um helper server-only verifica JWT individual no Auth e lê somente dados globais de mercado já coletados (`assets`, `analyses`, `analysis_metrics`, `market_candles`). A chave de serviço permanece no servidor e não é usada para contas, carteiras ou lançamentos. Query fixa, catálogo delimitado pelos IDs da RPC autenticada, CRYPTO/KRAKEN/USDT, sem tabela/path arbitrários. Preços e carteira continuam via RPC com JWT do usuário. Falha opcional da pesquisa não bloqueia o livro.

## Limites e validação

Preservar RLS, idempotência, atomicidade, precisão, máscaras de preço vencido, privacidade, isolamento e recuperação de sessão. Sem nova conexão de corretora, ordem real, cadastro de usuário por ferramenta, e-mail ou alteração de senha/PIN. Não misturar esta tarefa com a revisão de segurança do login legado.

Testes: simulação com taxas/ausência, proporção, cenários, poeira/overflow; indicadores ausentes/antigos/futuros e fonte errada; fonte de pesquisa verifica JWT e não lê dados privados; fluxos rápidos/contextuais, uma carteira no menu, modal e rascunho/retry, perda de resposta, histórico/privacidade/mobile. Manter os31 testes de navegador anteriores adaptados aos fluxos deliberadamente alterados. Lint/unit/build/types e Chromium, revisão independente, produção HTTPS e PRs sem merge automático.
