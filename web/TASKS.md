# Web Dashboard — TASKS

## Projeto

Frontend do `mercado_invest`.

## Diretório

```text
web/
```

## Objetivo da v1

Construir um painel web privado em Next.js + TypeScript, hospedado na Vercel, que:

- consulte dados reais já persistidos no Supabase;
- mostre oportunidades, análises e histórico;
- exiba gráficos de preço, retorno, RSI e volatilidade;
- permita disparar manualmente o workflow `investment-automation`;
- permita alterar o horário do resumo diário;
- mantenha o Telegram funcionando de forma independente;
- nunca exponha secrets no navegador.

## Regras gerais

- [ ] O frontend não calcula score financeiro.
- [ ] O frontend não altera `candidate-v1`.
- [ ] O frontend não substitui o backend Python.
- [ ] O frontend não inventa dados ausentes.
- [ ] Toda informação financeira exibida deve ter timestamp quando disponível.
- [ ] Nenhuma secret pode usar prefixo `NEXT_PUBLIC_`.
- [ ] Nunca versionar `.env.local`.
- [ ] Nunca expor `SUPABASE_SECRET_KEY`.
- [ ] Nunca expor `GITHUB_ACTIONS_TOKEN`.
- [ ] Nunca armazenar senha administrativa em texto puro.
- [ ] Mudanças de comportamento devem possuir testes.
- [ ] Seguir TDD em funcionalidades e correções.
- [ ] O GitHub continua sendo a fonte oficial do código.
- [ ] A Biblioteca do ChatGPT pode manter cópias de trabalho sem secrets.

---

# ETAPA WEB 1 — Bootstrap do frontend

## Status

CONCLUÍDA

## Objetivo

Criar a aplicação Next.js dentro de `web/` sem interferir no backend Python existente.

## Tarefas

### WEB-1.1 — Scaffold Next.js

- [ ] Criar projeto Next.js com App Router em `web/`.
- [ ] Usar TypeScript.
- [ ] Configurar Tailwind CSS.
- [ ] Criar `package.json`.
- [ ] Gerar e versionar lockfile.
- [ ] Configurar scripts `dev`, `build`, `test`, `lint` e `typecheck`.
- [ ] Não adicionar bibliotecas sem uso imediato.

### WEB-1.2 — Estrutura base

Criar:

```text
web/
├── app/
├── components/
├── lib/
├── tests/
└── public/
```

- [ ] Criar layout raiz.
- [ ] Criar página inicial mínima.
- [ ] Criar tratamento global de erro.
- [ ] Criar página 404.
- [ ] Validar build sem secrets reais.

### WEB-1.3 — Tema visual

- [ ] Tema dark profissional.
- [ ] Fundo quase preto.
- [ ] Cards discretos.
- [ ] Verde/vermelho apenas com significado financeiro.
- [ ] Layout responsivo desktop/mobile.
- [ ] Garantir contraste e legibilidade.

## Gate WEB 1

- [ ] `npm run lint` passa.
- [ ] `npm run typecheck` passa.
- [ ] `npm test` passa.
- [ ] `npm run build` passa.
- [ ] Nenhuma secret adicionada.

---

# ETAPA WEB 2 — Autenticação administrativa

## Status

CONCLUÍDA APÓS REVISÃO DE SEGURANÇA

## Objetivo

Proteger todo o painel com uma única senha administrativa, sem armazenar a senha em texto puro.

## Tarefas

### WEB-2.1 — Configuração segura

Variáveis server-only:

```text
WEB_ADMIN_PASSWORD_HASH
WEB_SESSION_SECRET
```

- [ ] Validar presença das variáveis em produção.
- [ ] Nunca usar `NEXT_PUBLIC_`.
- [ ] Usar Argon2id para verificar a senha.

### WEB-2.2 — Login

Criar:

```text
/login
```

- [ ] Campo de senha.
- [ ] Validação server-side.
- [ ] Mensagem genérica para senha inválida.
- [ ] Não registrar senha em logs.
- [ ] Limitação básica contra brute force.

### WEB-2.3 — Sessão

- [ ] Criar sessão assinada.
- [ ] Cookie `HttpOnly`.
- [ ] Cookie `Secure` em produção.
- [ ] Cookie `SameSite=Strict`.
- [ ] Expiração máxima de 12 horas.
- [ ] Implementar logout.

### WEB-2.4 — Proteção de rotas

- [ ] Bloquear dashboard sem sessão.
- [ ] Bloquear rotas `/api/*` administrativas sem sessão.
- [ ] Testar sessão válida.
- [ ] Testar sessão inválida.
- [ ] Testar sessão expirada.

## Gate WEB 2

- [ ] Login correto funciona.
- [ ] Login incorreto não cria sessão.
- [ ] Rotas privadas não ficam acessíveis anonimamente.
- [ ] Cookies não expõem secrets.
- [ ] Testes de autenticação passam.

---

# ETAPA WEB 3 — Integração server-side com Supabase

## Status

PENDENTE — arquivos existentes não concluem a etapa

## Objetivo

Permitir que o Next.js consulte dados financeiros persistidos sem expor chave administrativa ao navegador.

## Tarefas

### WEB-3.1 — Cliente Supabase server-only

Criar:

```text
web/lib/supabase/
```

- [ ] Cliente acessível apenas no servidor.
- [ ] Configuração por variáveis de ambiente.
- [ ] Proibir import do cliente administrativo em componentes client-side.
- [ ] Configurar timeout quando aplicável.

### WEB-3.2 — View models

Criar modelos de leitura para:

- [ ] ativos;
- [ ] cotações;
- [ ] análises;
- [ ] métricas;
- [ ] opportunities;
- [ ] AI runs;
- [ ] job runs.

### WEB-3.3 — Queries

- [ ] Última cotação válida por ativo.
- [ ] Última análise por ativo.
- [ ] Última oportunidade por ativo.
- [ ] Último AI run relacionado.
- [ ] Últimos job runs.
- [ ] Histórico paginado.
- [ ] Dados históricos para gráficos.

### WEB-3.4 — Estados de falha

Diferenciar:

- [ ] dado ausente;
- [ ] dado inválido;
- [ ] dado antigo;
- [ ] erro Supabase;
- [ ] resultado vazio.

- [ ] Nunca converter ausência em `0`.
- [ ] Nunca mascarar erro como sucesso.

## Gate WEB 3

- [ ] Nenhuma chamada Supabase administrativa ocorre no browser.
- [ ] Queries possuem testes.
- [ ] Estados vazios são tratados.
- [ ] Nenhum dado financeiro é inventado.

---

# ETAPA WEB 4 — Dashboard

## Status

PENDENTE — arquivos existentes não concluem a etapa

## Objetivo

Criar a tela principal do sistema.

## Rota

```text
/dashboard
```

## Tarefas

### WEB-4.1 — Status operacional

Exibir:

- [ ] última execução;
- [ ] status: sucesso, falha ou em andamento;
- [ ] horário da execução;
- [ ] quantidade de ativos analisados.

### WEB-4.2 — Contadores

Exibir:

- [ ] `NONE`;
- [ ] `WATCH`;
- [ ] `INTERESTING`;
- [ ] `HIGH_INTEREST`.

### WEB-4.3 — Melhores oportunidades

Para cada ativo:

- [ ] símbolo;
- [ ] preço;
- [ ] timestamp;
- [ ] retorno;
- [ ] RSI;
- [ ] volatilidade;
- [ ] nível;
- [ ] score.

### WEB-4.4 — Navegação

- [ ] Link para detalhes do ativo.
- [ ] Link para histórico.
- [ ] Link para resumo diário.
- [ ] Link para configurações.

## Gate WEB 4

- [ ] Dashboard funciona com dados reais persistidos.
- [ ] Dashboard funciona com banco sem oportunidades.
- [ ] Dados possuem formatação humana.
- [ ] Valores não têm casas decimais absurdas.

---

# ETAPA WEB 5 — Página de ativo e gráficos

## Status

PENDENTE — arquivos existentes não concluem a etapa

## Objetivo

Permitir análise visual de cada ativo.

## Rota

```text
/ativos/[symbol]
```

## Tarefas

### WEB-5.1 — Cabeçalho do ativo

Exibir:

- [ ] símbolo;
- [ ] nome;
- [ ] último preço válido;
- [ ] timestamp;
- [ ] última classificação;
- [ ] score.

### WEB-5.2 — Gemini

Exibir, quando existir:

- [ ] resumo;
- [ ] fatores positivos;
- [ ] fatores negativos;
- [ ] riscos.

- [ ] Não renderizar HTML bruto vindo do Gemini.

### WEB-5.3 — Gráficos

Adicionar Recharts.

Gráficos:

- [ ] preço;
- [ ] retorno;
- [ ] RSI;
- [ ] volatilidade.

Cada gráfico deve:

- [ ] possuir eixo temporal;
- [ ] mostrar período;
- [ ] tratar ausência de dados;
- [ ] não fabricar pontos intermediários.

### WEB-5.4 — Histórico do ativo

- [ ] oportunidades recentes;
- [ ] score;
- [ ] nível;
- [ ] timestamp.

## Gate WEB 5

- [ ] Quatro gráficos funcionam.
- [ ] Estado vazio funciona.
- [ ] Página é responsiva.
- [ ] Nenhum gráfico usa dado inventado.

---

# ETAPA WEB 6 — Histórico

## Status

PENDENTE — arquivos existentes não concluem a etapa

## Objetivo

Consultar registros anteriores sem carregar a base inteira no navegador.

## Rota

```text
/historico
```

## Tarefas

### WEB-6.1 — Tabela

Colunas:

- [ ] data/hora;
- [ ] ativo;
- [ ] nível;
- [ ] score;
- [ ] retorno;
- [ ] RSI;
- [ ] volatilidade.

### WEB-6.2 — Filtros

- [ ] ativo;
- [ ] período;
- [ ] nível.

### WEB-6.3 — Paginação

- [ ] Paginação server-side.
- [ ] Limite explícito por página.
- [ ] Não carregar histórico completo.

## Gate WEB 6

- [ ] Filtros combinados funcionam.
- [ ] Paginação funciona.
- [ ] Query permanece server-side.

---

# ETAPA WEB 7 — Resumo diário

## Status

PENDENTE — arquivos existentes não concluem a etapa

## Objetivo

Mostrar no site o fechamento diário consolidado.

## Rota

```text
/resumo
```

## Tarefas

- [ ] quantidade de ativos analisados;
- [ ] melhores oportunidades;
- [ ] preço;
- [ ] retorno;
- [ ] RSI;
- [ ] volatilidade;
- [ ] nível;
- [ ] score;
- [ ] resumo Gemini;
- [ ] novas oportunidades;
- [ ] mantidas;
- [ ] deixaram de ser interessantes;
- [ ] principais riscos.

## Regra

- [ ] O frontend não cria uma segunda policy.
- [ ] O frontend não recalcula score.
- [ ] Transformações duplicadas devem ser apenas visuais.

## Gate WEB 7

- [ ] Resumo do site representa os mesmos fatos persistidos usados pelo fechamento Telegram.
- [ ] Estado sem oportunidades é exibido claramente.

---

# ETAPA WEB 8 — Executar análise agora

## Status

PENDENTE — arquivos existentes não concluem a etapa

## Objetivo

Permitir disparo manual da automação existente sem executar Python na Vercel.

## Fluxo

```text
POST /api/analysis/run
        ↓
sessão válida
        ↓
GitHub Actions API
        ↓
workflow_dispatch
        ↓
investment-automation
```

## Tarefas

### WEB-8.1 — Cliente GitHub server-only

Variáveis:

```text
GITHUB_ACTIONS_TOKEN
GITHUB_REPOSITORY_OWNER
GITHUB_REPOSITORY_NAME
GITHUB_WORKFLOW_FILE
```

- [ ] Usar token com menor permissão possível.
- [ ] Nunca expor token ao browser.
- [ ] Timeout em chamada externa.

### WEB-8.2 — Route handler

Criar:

```text
POST /api/analysis/run
```

- [ ] Exigir sessão.
- [ ] Validar origem da requisição.
- [ ] Tratar 401.
- [ ] Tratar 403.
- [ ] Tratar 404.
- [ ] Tratar 422.
- [ ] Tratar 5xx.
- [ ] Não retornar token ou payload sensível.

### WEB-8.3 — UI

- [ ] Botão `Executar análise agora`.
- [ ] Desabilitar durante requisição.
- [ ] Mostrar `solicitação enviada`.
- [ ] Não mostrar `concluído` antes do job real concluir.
- [ ] Atualizar status consultando `job_runs`.

## Gate WEB 8

- [ ] Workflow é disparado de forma autenticada.
- [ ] Cliques repetidos não causam comportamento confuso.
- [ ] Estado final vem do backend persistido.

---

# ETAPA WEB 9 — Configuração do horário do resumo

## Status

PARCIAL — ver WEB-9.1 e WEB-9.2

## Objetivo

Alterar pelo painel o horário do resumo diário sem editar GitHub Actions Variables.

## Rota

```text
/configuracoes
```

## Tarefas

### WEB-9.1 — Persistência

Status: IMPLEMENTADA ANTECIPADAMENTE — aguardando validação remota da migration.

- [ ] Criar migration específica para configuração runtime.
- [ ] Campo `telegram_summary_hour_brt`.
- [ ] Validar inteiro entre `0` e `23`.
- [ ] Preservar RLS deny-by-default.

### WEB-9.2 — Backend Python

Status: PARCIAL — repositório e fallback local existem; integração real depende da migration aplicada.

- [ ] Ler configuração persistida.
- [ ] Se existir, ela prevalece sobre o default de ambiente.
- [ ] Se não existir, usar `TELEGRAM_SUMMARY_HOUR_BRT`.
- [ ] Registrar uso do fallback em log.
- [ ] Não usar fallback silencioso.
- [ ] Preservar idempotência do scheduler.

### WEB-9.3 — API web

- [ ] GET da configuração.
- [ ] PUT/PATCH autenticado.
- [ ] Validar `0..23`.
- [ ] Proteção CSRF/origin.

### WEB-9.4 — UI

- [ ] Input de horário.
- [ ] Salvar.
- [ ] Exibir sucesso.
- [ ] Exibir erro.
- [ ] Não alterar GitHub Variables.

## Gate WEB 9

- [ ] Alteração no site persiste.
- [ ] Backend Python respeita novo horário.
- [ ] Resumo Telegram continua funcionando.
- [ ] Testes de regressão do scheduler passam.

---

# ETAPA WEB 10 — Segurança e hardening

## Status

PENDENTE

## Tarefas

- [ ] Security headers.
- [ ] CSP adequada.
- [ ] `X-Content-Type-Options`.
- [ ] `Referrer-Policy`.
- [ ] Proteção contra clickjacking.
- [ ] CSRF/origin check nas mutações.
- [ ] Sanitização/escaping de conteúdo externo.
- [ ] Nenhuma secret em bundle client-side.
- [ ] Nenhuma secret em logs.
- [ ] Validação de inputs.
- [ ] Testes de rotas não autenticadas.
- [ ] Revisar dependências.
- [ ] Lockfile versionado.

## Gate WEB 10

- [ ] Build analisado sem secrets públicas.
- [ ] Rotas administrativas protegidas.
- [ ] Testes de segurança básicos passam.

---

# ETAPA WEB 11 — CI

## Status

PARCIAL — CI Web local configurado; execução remota pendente.

## Objetivo

Adicionar validação do frontend sem quebrar o CI Python existente.

## Tarefas

- [ ] Instalar dependências de `web/`.
- [ ] Rodar lint.
- [ ] Rodar typecheck.
- [ ] Rodar testes.
- [ ] Rodar build.
- [ ] Usar mocks/configuração de teste para secrets.
- [ ] Manter suíte Python obrigatória.

## Gate WEB 11

- [ ] Python CI passa.
- [ ] Web CI passa.
- [ ] Build passa.
- [ ] Nenhuma secret usada no CI.

---

# ETAPA WEB 12 — Deploy Vercel

## Status

PENDENTE

## Objetivo

Publicar a v1 para uso pessoal.

## Tarefas

- [ ] Configurar Root Directory da Vercel como `web/`.
- [ ] Configurar variáveis de ambiente server-only.
- [ ] Configurar senha administrativa por hash.
- [ ] Configurar segredo de sessão.
- [ ] Configurar Supabase server-side.
- [ ] Configurar token GitHub Actions.
- [ ] Fazer deploy.
- [ ] Validar login em produção.
- [ ] Validar dashboard.
- [ ] Validar gráficos.
- [ ] Validar histórico.
- [ ] Validar resumo.
- [ ] Validar disparo manual.
- [ ] Validar configuração do horário.
- [ ] Validar Telegram após deploy.

## Gate WEB 12

- [ ] URL Vercel acessível.
- [ ] Painel protegido.
- [ ] Fluxo completo validado.
- [ ] Telegram permanece independente.
- [ ] Nenhuma secret exposta.

---

# Gate final da Web v1

Status: NÃO INICIADO

A v1 será aprovada somente quando:

- [ ] autenticação estiver funcionando em produção;
- [ ] todas as páginas privadas exigirem sessão;
- [ ] dashboard usar dados reais;
- [ ] página de ativo possuir os quatro gráficos;
- [ ] histórico possuir filtros e paginação;
- [ ] resumo diário estiver disponível;
- [ ] workflow manual puder ser disparado;
- [ ] horário do resumo puder ser alterado;
- [ ] backend Python respeitar a configuração persistida;
- [ ] Telegram continuar funcionando;
- [ ] CI Python e Web estiverem verdes;
- [ ] Vercel estiver em produção;
- [ ] nenhuma secret estiver versionada ou enviada ao navegador.

## Próxima tarefa autorizada

```text
WEB-1.1 — Scaffold Next.js
```
