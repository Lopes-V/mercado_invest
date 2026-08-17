# Alert Engine

## Objetivo
Evitar alertas irrelevantes.

## Princípio
Um único indicador não deve gerar alerta financeiro.

## Fluxo

dados
-> métricas
-> pré-filtro
-> IA
-> opportunity engine
-> alert engine

## Níveis
- NONE
- WATCH
- INTERESTING
- HIGH_INTEREST

## Condições obrigatórias
- dados recentes
- qualidade válida
- quantidade mínima de evidências
- risco dentro das regras

## Cooldown
O mesmo evento não deve gerar spam.

## Futuro
Limites serão calibrados através de backtesting.