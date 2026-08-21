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
