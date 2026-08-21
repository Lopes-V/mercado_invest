# Deployment

## Estado
Ainda não definido.

## Requisitos futuros
- execução 24/7
- scheduler
- variáveis de ambiente
- logs persistentes
- restart automático
- health check
- backup
- monitoramento

## Regra
Deploy será definido somente depois que o sistema local estiver validado.

## Jobs locais

A Etapa 4 oferece somente `SchedulerService.run_forever` como loop local cooperativo. Não há daemon, cron gerenciado, scheduler distribuído, recuperação de `RUNNING` abandonado ou deployment 24/7. Um crash pode deixar `job_runs` em `RUNNING`; hardening e deployment continuam responsabilidade da Etapa 13.
# Worker readiness

O worker continua síncrono e single-process. `run_forever` é um loop local com parada cooperativa por SIGINT/SIGTERM; ele não é um scheduler distribuído nem um deploy 24/7 por si só. O Dockerfile usa usuário não-root e não copia `.env`. A escolha e o rollout do ambiente remoto permanecem fora do repositório.
