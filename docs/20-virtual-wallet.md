# Livro virtual USDT

Primeira entrega do desenho aprovado: carteiras individuais, lançamentos declarados e valoração com preços Kraken. Não envia ordens nem comprova posse de ativos. As tabelas legadas de portfolio permanecem separadas. Consulte [a ativação](21-virtual-wallet-activation.md) antes de usar em produção.

## Contrato e segurança

A migração `supabase/migrations/20261027130000_virtual_wallet.sql` cria carteiras, operações, entradas e orçamento de escrita. RLS permite leitura somente ao proprietário `auth.uid()`; entradas não têm leitura direta. O acesso às entradas ocorre somente por estado/histórico via RPC, que serializa valores financeiros como texto para evitar que a representação numérica nativa exponha números JSON com perda de precisão. O cliente usa a chave pública e JWT individual; não recebe chave administrativa. Escritas diretas são revogadas, inclusive para `service_role`; apenas as RPCs autenticadas criam registros. Operações/entradas não podem ser editadas ou apagadas. Correções usam estorno auditável.

RPCs: `virtual_wallet_create(p_name,p_key)`, `virtual_wallet_apply(p_wallet_id,p_request,p_key)`, `virtual_wallet_state(p_wallet_id)`, `virtual_wallet_history(p_wallet_id,p_before,p_limit)` e `virtual_wallet_market()`. Carteiras podem ser enumeradas pela leitura RLS de `virtual_wallets`. Os contratos completos estão no [plano](superpowers/plans/2026-10-27-virtual-wallet.md).

Cada escrita adquire um advisory lock por usuário e bloqueia a carteira. Até30 escritas confirmadas/minuto por usuário, incluindo criação, são permitidas. Retries idênticos não consomem outro lançamento nem orçamento. A solicitação JSON canônica é armazenada e comparada integralmente, em vez de usar hash: a mesma chave com conteúdo diferente é recusada, sem risco de colisão. Eventos do orçamento ficam retidos; sua manutenção administrativa pode ser adicionada separadamente se o volume exigir.

## Contabilidade

`DEPOSIT`, `WITHDRAWAL`, `FEE`, `BUY`, `SELL`, `SWAP` e `REVERSAL` aceitam somente os campos previstos. Quantidades, preços, taxas e totais trafegam como strings decimais. Valores declarados precisam caber exatamente em `numeric(38,18)`; resultados derivados usam HALF_UP, operações exatas de soma/multiplicação e divisão com100 casas internas. Overflow é erro, nunca truncamento silencioso.

O livro efetivo inteiro é reprocessado por data e sequência. Depósitos/retiradas afetam aportes líquidos, não lucro. Compra capitaliza taxa; venda reconhece valor líquido menos custo médio proporcional; taxa avulsa reduz lucro realizado. Um estorno cancela o efeito original no ponto histórico e reprocessa dependências. Saldo negativo em qualquer ponto invalida toda a transação. Uma troca registra venda e compra atômicas com preços/taxas explícitos e conserva a diferença em caixa.

O histórico tem páginas por sequência (50 por padrão, máximo100); o cálculo nunca fica limitado à página exibida. O estado inclui caixa, aportes líquidos, taxas, custo, lucro realizado, posições, ganhos não realizados e timestamps. O valor total inclui caixa. Se uma posição não tiver cotação Kraken/USDT válida, positiva, não futura e com até120s, o total é `null`, com subtotal conhecido explicitamente separado. Não se usa cotação anterior para esconder a mais recente inválida.

## Verificação isolada

Os testes opt-in usam exclusivamente PostgreSQL16 no contêiner local `atlas-wallet-pg`, sem rede nem portas expostas, banco `wallet_test`. O bootstrap apaga apenas os schemas desse banco de teste; nunca executar os fixtures no Supabase.

```sh
docker run --detach --name atlas-wallet-pg --network none \
  -e POSTGRES_HOST_AUTH_METHOD=trust -e POSTGRES_DB=wallet_test postgres:16-alpine
VIRTUAL_WALLET_DB_TEST=1 python -m pytest tests/test_virtual_wallet_database.py -q
```

Há testes reais de isolamento, permissões, precisão, preço médio/taxas, replay/estornos, histórico completo, dados inválidos/antigos/futuros, rollback e concorrência. Testes de navegador validam interação e contratos com mocks restritos ao processo de teste; não substituem essas verificações de banco.
