# Regras para agentes de IA

## Princípio principal
Implemente somente a tarefa atualmente autorizada em TASKS.md.

## Escopo
- Não implementar etapas futuras.
- Não adicionar funcionalidades não solicitadas.
- Não alterar arquitetura sem justificativa explícita.
- Não alterar schema do banco sem tarefa específica.

## Dados financeiros
- Nunca inventar cotações.
- Todo dado financeiro deve possuir timestamp.
- Dados inválidos ou antigos não podem gerar recomendação.
- Falha de dados deve interromper a análise dependente.
- Não substituir dado ausente por estimativa silenciosa.

## IA
- IA não é fonte de dados financeiros.
- IA não realiza cálculos críticos que possam ser determinísticos.
- Respostas da IA devem ser validadas.
- A IA pode responder que não existem evidências suficientes.

## Segurança
- Nunca expor secrets.
- Nunca registrar tokens em logs.
- Nunca versionar `.env`.
- Nunca expor chave administrativa do Supabase.
- Validar todas as entradas externas.

## Código
- Não engolir exceptions.
- Não remover testes para fazer o projeto passar.
- Não adicionar fallback silencioso.
- Evitar dependências desnecessárias.
- Não usar float para valores monetários quando precisão importar.
- Toda integração externa deve possuir timeout.
- Preferir código simples a abstrações desnecessárias.

## Testes
- Código novo deve possuir testes quando aplicável.
- Testar caminho normal.
- Testar falhas.
- Testar dados inválidos.
- Uma tarefa não está concluída apenas porque executou uma vez.

## Documentação
Atualizar documentação quando uma decisão arquitetural mudar.