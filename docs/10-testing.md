# Testing

## Tipos

### Unit
Funções isoladas.

### Integration
Supabase, providers, Telegram.

### E2E
Fluxos completos.

## Casos obrigatórios

Happy Path.

Provider indisponível.

Banco indisponível.

Dados antigos.

Dados incompletos.

Outlier.

IA inválida.

Telegram indisponível.

## Regra
Uma tarefa não pode ser aprovada apenas por teste manual.

## Persistência Supabase

Os testes unitários dos repositories usam uma fronteira Supabase controlada e não acessam rede. A integração real é opt-in para evitar escrita remota acidental na suíte diária:

```bash
RUN_SUPABASE_INTEGRATION=1 \
python -m pytest tests/integration/test_domain_persistence.py -vv
```

Ela requer migrations aplicadas e credenciais de backend já presentes no ambiente; os dados temporários são únicos e o cleanup usa somente os UUIDs criados pelo próprio teste. Um teste skipped sem a variável não valida a persistência remota. A execução remota da Etapa 2 passou, validando constraints, RLS de backend e cleanup sem dados temporários restantes.
