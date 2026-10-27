# Uso da carteira e comparação de trocas

A entrada principal Carteira aponta para a conta individual em `/virtual`. O portfólio legado permanece acessível nas configurações do painel do operador; seus dados não são apagados nem atribuídos automaticamente à conta individual.

## Acompanhar uma posição

Crie uma carteira vazia e declare o saldo inicial em Adicionar saldo. Registre a compra com quantidade, preço efetivo, taxa e data. O preço médio inclui as taxas registradas. Depósitos e retiradas são fluxos de caixa, não lucro.

Cada posição reúne quantidade, custo médio, cotação atual, ganho em aberto e concentração. As ações partem do ativo: comprar mais, vender uma fração ou simular uma troca. Os percentuais de venda são calculados sem arredondar a quantidade para cima. Usar cotação atual é uma escolha explícita; para uma operação passada informe o preço efetivamente ocorrido. Nenhuma taxa ausente vira zero automaticamente.

Cotações precisam ser Kraken/USDT, válidas, positivas, não futuras e ter no máximo 120 segundos. Sem preço utilizável, os registros e o histórico continuam disponíveis; patrimônio completo e simulações atuais ficam indisponíveis. Atualizar a leitura não força uma nova negociação na corretora.

## Comparar manter ou trocar

Escolha a posição, a fração e a moeda de destino. Declare as duas taxas em USDT para obter valor líquido, quantidade de destino, resultado realizado estimado e eventual resíduo de caixa. A simulação não grava lançamento nem envia ordem.

As duas hipóteses de variação são opcionais e fornecidas pelo usuário. A comparação mostra quanto valeria o trecho mantido ou trocado sob essas hipóteses, antes de eventuais custos futuros de saída. Não é previsão nem probabilidade de ganho. Preparar troca apenas preenche um lançamento manual que ainda exige revisão e confirmação separadas.

## Contexto de mercado

As leituras de 15 minutos e 1 hora usam a análise `analysis-v2` já produzida pelo backend: direção, RSI, volatilidade e ATR, com fonte e horário. Alinhamento ou divergência entre intervalos descreve esses dados; não autoriza compra ou venda. O histórico contém somente candles de 15 minutos fechados, com lacunas explícitas, sem preenchimento artificial.

A leitura opcional de pesquisa verifica o JWT individual antes de consultar um conjunto fixo e limitado de fatos públicos globais no servidor. A chave de serviço nunca acessa carteiras privadas ou gravações nessa função. Falha da pesquisa não bloqueia o livro. Não há nova migration para esta evolução.

## Confirmação incerta

Fechar a ação e abri-la novamente preserva o rascunho e a chave da tentativa enquanto a tela permanece montada. Falhas temporárias de leitura ou de verificação da sessão pausam os envios. Não há persistência de rascunhos financeiros no dispositivo: após fechar a aba ou recarregar totalmente, confira o histórico antes de lançar novamente uma operação cuja confirmação não chegou.

## Bybit

O backend mantém o adapter público Bybit e a seleção explícita `--provider bybit`. A tentativa mais recente no ambiente atual foi bloqueada pelo proxy no CONNECT, antes de qualquer resposta Bybit. O domínio já consta no rascunho de rede, ainda sem aplicação à instância. Esse teste não confirma nem elimina a restrição regional vista anteriormente. A fonte da carteira continua Kraken; não são misturados preços ou históricos de corretoras diferentes.

## Validação desta evolução

Atlas:46 testes unitários e53 de navegador aprovados, lint/build/tipos aprovados, revisão independente final aprovada após correções de rascunhos, rejeição transacional e relógio de cotação. Não houve mudança no livro SQL, contas reais de teste ou lançamentos financeiros remotos. Código na branch `feat/actionable-crypto-wallet`; publicação desta nova interface ainda depende de acesso à Vercel.

A tela usa um timestamp do servidor capturado após as leituras, tempo monotônico e duração de requisição quando disponível para avaliar a validade. Não é possível prometer um limite exato de entrega se o relógio do dispositivo estiver atrasado e o navegador não fornecer uma medição utilizável de transporte.
