# Ativação da carteira virtual USDT

Esta ativação é separada da coleta de preços e da senha compartilhada das telas legadas. A carteira virtual usa contas individuais do Supabase Auth. Não conecta corretora, não movimenta dinheiro real e não usa valores de demonstração como saldo.

## Status verificado em 27/10/2026

Frontend publicado em `https://atlas-web-azure-two.vercel.app`, deployment `dpl_FX3GV3Zuv6huYTMULegg4dKpum9Y` READY. `/conta` público, `/virtual` protegido por conta individual, renovação apenas por POST da mesma origem e telas legadas validadas por HTTPS. Uma sessão administrativa válida não autentica a carteira.

A leitura do schema REST remoto confirmou ausência das RPCs `virtual_wallet_*`: **migração ainda não aplicada, gravações da carteira ainda não ativadas**. Não foram criadas contas reais nem realizadas operações financeiras remotas. As etapas abaixo são necessárias para completar a ativação; cadastrar o frontend na Vercel não executa SQL automaticamente.

## Pré-requisitos do projeto existente

O projeto é o mesmo já usado pelo Atlas e pelo radar Kraken. No servidor Atlas: `SUPABASE_URL` e `SUPABASE_PUBLISHABLE_KEY`; a chave administrativa existente continua restrita às funções legadas autorizadas. Nunca preencher o novo campo de chave pública com uma chave `sb_secret_` e nunca publicar a chave administrativa em `NEXT_PUBLIC_`.

A chave pública fornecida pelo operador foi validada contra o endpoint Auth e registrada no ambiente Production da Vercel, sem copiar seu valor para esta documentação. E-mail/login estão habilitados no projeto; a confirmação de e-mail está exigida. Não foi criada conta de usuário nem enviado e-mail por ferramentas durante a instalação.

## Migração PostgreSQL

Revisar e executar o arquivo completo `supabase/migrations/20261027130000_virtual_wallet.sql` no [SQL Editor do projeto Supabase](https://supabase.com/dashboard/project/gwkiihmmgjoypmdykrmw/sql/new): **New query → colar o arquivo completo → Run**. Também pode ser usada uma conexão administrativa PostgreSQL autorizada. A migração é nova, adiciona a persistência virtual e funções RLS/RPC; não atribui carteiras legadas a novos usuários, não insere saldos e não altera registros de produção existentes.

A execução SQL administrativa exige um acesso diferente da chave REST usada pelo Atlas. No ambiente desta tarefa foram confirmados Auth/REST funcionais, mas nenhuma conexão SQL/Management API nem função administrativa SQL exposta. Isso não é resolvido trocando a chave pública por uma chave administrativa nas chamadas dos usuários. Não instalar funções genéricas `exec_sql` para contornar a ausência de conexão administrativa.

Após aplicar, validar que as funções `virtual_wallet_create`, `virtual_wallet_apply`, `virtual_wallet_state`, `virtual_wallet_history` e `virtual_wallet_market` aparecem na API. Solicitar reload do schema PostgREST conforme a migração; aguardar a atualização do cache. Até a migração existir, a aplicação deve informar indisponibilidade, sem montar uma carteira fictícia.

## Auth e URLs de produção

No Supabase, **Authentication → URL Configuration**:

- Site URL: `https://atlas-web-azure-two.vercel.app`.
- Permitir redirecionamento para a área de conta do mesmo site (`https://atlas-web-azure-two.vercel.app/conta` e os caminhos de conta realmente usados pela aplicação).
- Manter o provider de e-mail habilitado e a confirmação conforme a política do operador. Não desabilitar confirmação silenciosamente para fazer testes passarem.

A primeira pessoa cria sua própria conta pela interface; após confirmar o e-mail, entra com sua senha individual. A senha do painel legado não cria sessão individual. O sistema não associa automaticamente carteiras antigas à primeira conta cadastrada.

## Validação após ativar

1. Entrar com uma conta individual e criar carteira USDT vazia: saldo zero, sem posições ou exemplos predefinidos.
2. Declarar um depósito virtual e registrar compra usando preço/taxa/data efetivos. Depósito não aparece como lucro.
3. Testar retry com a mesma chave de operação sem duplicar lançamento. Compra/venda/troca/retirada rejeitam saldo ou quantidade insuficientes. O formulário preserva a solicitação durante falhas temporárias de leitura enquanto a tela permanece aberta. Se fechar ou recarregar totalmente o navegador após uma resposta incerta, conferir o histórico antes de registrar novamente; os rascunhos financeiros não são persistidos no dispositivo.
4. Uma segunda conta não deve listar nem abrir a carteira da primeira. Não usar chave de serviço para simular essas verificações: testar com os JWTs próprios dos usuários.
5. Patrimônio atual só fica completo quando as posições têm cotações Kraken válidas/USDT e com até120s. Dados antigos, futuros ou ausentes ficam indisponíveis.

Os testes locais usam PostgreSQL16 em contêiner sem portas expostas e dados exclusivos de teste; não constituem validação de escrita remota em contas reais. Os testes de navegador usam processo com mocks apenas de teste, nunca fallback de produção.

Validação do livro nesta entrega:34 testes PostgreSQL reais, incluídos na suíte de622 testes aprovados e21 integrações remotas não habilitadas. Há regressões para leitura monetária como texto, cotação não finita, zero e moeda incompatível; preços inutilizáveis não impedem registros históricos declarados. Compilação Python e dependências também verificadas.

Atlas:19 testes unitários e31 de navegador aprovados, lint/build/tipos verificados, incluindo fluxos legados, isolamento, precisão do transporte, leitura temporariamente indisponível, confirmação incerta e recuperação de sessão. Revisão independente final aprovada após corrigir os dois casos de integração. Nenhum teste de navegador cria conta real ou envia e-mail.

## Escopo desta entrega

Lote1: conta individual, livro virtual/operacional USDT, saldo, posições, ganhos, histórico e transações atômicas. Lotes2/3 do desenho aprovado mantêm simulador/concentração/radar, depois alertas internos e backtesting como entregas posteriores; não são anunciados como implementados pela ativação da carteira básica.
