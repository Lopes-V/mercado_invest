# Mercado Invest — Web Dashboard v1

Data: 2026-09-09
Status: design aprovado em conversa, aguardando revisão da especificação antes da implementação

## Objetivo

Adicionar ao repositório `mercado_invest` um painel web privado, hospedado na Vercel, que coexista com o Telegram e reutilize o pipeline financeiro já existente. O painel será uma interface de consulta e controle operacional, não um novo motor de decisão financeira.

A automação Python continua sendo a fonte de verdade para coleta, análise, policy, Gemini, persistência e alertas Telegram. O frontend não recalcula score, não redefine níveis financeiros e não inventa dados ausentes.

## Escopo da v1

A primeira versão deve incluir:

- login com uma única senha administrativa;
- dashboard com estado geral do sistema;
- oportunidades atuais;
- histórico de análises;
- página detalhada por ativo;
- gráficos históricos de preço, retorno, RSI e volatilidade;
- exibição das análises do Gemini já persistidas;
- visualização do resumo diário;
- botão para solicitar uma nova execução da automação;
- configuração do horário do resumo diário;
- layout responsivo para desktop e celular;
- deploy na Vercel.

Ficam fora da v1:

- cadastro de múltiplos usuários;
- compra ou venda de ativos;
- paper trading pelo frontend;
- alteração da policy financeira;
- edição de thresholds de score;
- criação de recomendações pela interface;
- acesso direto do navegador a secrets;
- substituição do Telegram.

## Arquitetura escolhida

A solução será um monorepo simples, preservando o backend atual e adicionando o frontend em `web/`.

```text
mercado_invest/
├── app/                 # backend Python existente
├── supabase/            # migrations e banco
├── tests/               # testes Python existentes
└── web/                 # Next.js + TypeScript
```

Fluxo principal:

```text
Navegador
   ↓ HTTPS
Next.js na Vercel
   ├── server-side → Supabase
   └── server-side → GitHub Actions API

GitHub Actions
   ↓
Python existente
   ↓
Supabase / Gemini / Telegram
```

O navegador nunca recebe `SUPABASE_SECRET_KEY`, token do GitHub, token do Telegram, chave do Gemini ou segredo de sessão.

## Stack do frontend

- Next.js com App Router;
- TypeScript;
- Tailwind CSS para layout e tema;
- Recharts para gráficos;
- APIs e Server Components do Next.js para acesso server-side;
- Vercel para deploy.

Bibliotecas adicionais só devem ser incluídas quando tiverem função clara. Não será usado um framework visual pesado na v1.

## Autenticação

O painel terá uma única senha administrativa, sem cadastro de usuário e sem Supabase Auth.

Variáveis server-only na Vercel:

```text
WEB_ADMIN_PASSWORD_HASH
WEB_SESSION_SECRET
```

Requisitos:

- nunca armazenar a senha em texto puro no repositório;
- usar hash de senha resistente, preferencialmente Argon2id;
- comparação feita somente no servidor;
- após login válido, criar sessão assinada;
- cookie `HttpOnly`, `Secure` em produção e `SameSite=Strict`;
- sessão com expiração máxima de 12 horas;
- logout invalida o cookie;
- todas as páginas administrativas e rotas de mutação exigem sessão válida;
- resposta de login inválido não deve revelar detalhes internos;
- aplicar limitação simples de tentativas de login para reduzir brute force.

A senha real nunca será armazenada na Biblioteca do ChatGPT, GitHub ou código-fonte.

## Acesso ao Supabase

O navegador não acessará o Supabase diretamente.

O Next.js utilizará uma camada server-only em `web/lib/supabase/`. A chave administrativa existente poderá ser fornecida à Vercel apenas como variável server-side e nunca poderá usar prefixo `NEXT_PUBLIC_`.

A camada web terá apenas as operações necessárias para:

- ler ativos;
- ler cotações;
- ler análises e métricas;
- ler opportunities;
- ler AI runs;
- ler job runs/status operacional;
- ler e alterar configurações web permitidas.

A interface não terá operações genéricas de SQL, delete ou edição de dados financeiros.

## Configurações runtime

O horário do resumo diário não será alterado por GitHub Actions Variables.

Será criada uma persistência específica no Supabase para configurações runtime administráveis pelo painel. O contrato inicial precisa suportar:

```text
telegram_summary_hour_brt
```

O valor permitido será inteiro de `0` a `23`.

A fonte de verdade para esse horário passa a ser a configuração persistida quando existir. O valor de ambiente continua sendo o default explícito para instalações sem configuração persistida. Esse fallback deve ser documentado e registrado em log, nunca silencioso.

O backend Python continuará responsável pelo scheduler. O frontend apenas altera a configuração permitida.

## Dashboard

A página principal deve apresentar, sem excesso visual:

- horário da última execução concluída;
- estado da última execução: sucesso, falha ou em andamento;
- total de ativos analisados;
- contagem por nível `NONE`, `WATCH`, `INTERESTING` e `HIGH_INTEREST`;
- melhores oportunidades atuais;
- preço atual validado;
- retorno;
- RSI;
- volatilidade;
- score;
- botão `Executar análise agora`.

Tema visual:

- fundo quase preto;
- alto contraste;
- cards discretos;
- verde e vermelho usados apenas quando possuem significado financeiro;
- sem gradientes decorativos desnecessários;
- legibilidade prioritária em celular.

## Página de ativo

Rota proposta:

```text
/ativos/[symbol]
```

Conteúdo:

- símbolo e nome;
- último preço válido e timestamp;
- última classificação e score;
- última análise Gemini disponível;
- riscos persistidos;
- gráfico de preço;
- gráfico de retorno;
- gráfico de RSI;
- gráfico de volatilidade;
- histórico recente de oportunidades.

Todos os gráficos devem mostrar período/timestamp e estado vazio quando não houver dados suficientes.

## Histórico

Rota proposta:

```text
/historico
```

Filtros mínimos:

- ativo;
- período;
- nível da oportunidade.

Tabela:

- data/hora;
- ativo;
- nível;
- score;
- retorno;
- RSI;
- volatilidade.

Paginação server-side deve ser usada para evitar carregar histórico completo no navegador.

## Resumo diário

Rota proposta:

```text
/resumo
```

A tela deve consolidar os mesmos fatos persistidos usados pelo fechamento diário:

- quantidade de ativos analisados;
- melhores oportunidades;
- preço;
- retorno;
- RSI;
- volatilidade;
- nível;
- score;
- resumo Gemini quando disponível;
- novas oportunidades;
- oportunidades mantidas;
- oportunidades que deixaram de ser interessantes;
- riscos principais.

A interface não deve recalcular score nem criar um segundo motor financeiro. Se alguma transformação de apresentação precisar ser duplicada entre Python e web, ela deve ser estritamente visual.

## Executar análise agora

O botão não executará Python na Vercel.

Fluxo:

```text
POST /api/analysis/run
   ↓
validar sessão
   ↓
GitHub API workflow_dispatch
   ↓
investment-automation
   ↓
pipeline Python existente
```

A Vercel terá um token GitHub dedicado com o menor escopo possível para disparar Actions no repositório.

Variáveis server-only propostas:

```text
GITHUB_ACTIONS_TOKEN
GITHUB_REPOSITORY_OWNER
GITHUB_REPOSITORY_NAME
GITHUB_WORKFLOW_FILE
```

A rota deve:

- exigir autenticação;
- impedir múltiplos cliques simultâneos do mesmo navegador;
- retornar estado de solicitação, não fingir que a análise terminou;
- nunca expor o token GitHub;
- tratar 401/403/404/422/5xx do GitHub com mensagem operacional segura.

Depois do disparo, o dashboard consulta os `job_runs` persistidos para exibir o estado real da execução.

## Estrutura proposta do frontend

```text
web/
├── app/
│   ├── login/
│   │   └── page.tsx
│   ├── dashboard/
│   │   └── page.tsx
│   ├── ativos/
│   │   └── [symbol]/
│   │       └── page.tsx
│   ├── historico/
│   │   └── page.tsx
│   ├── resumo/
│   │   └── page.tsx
│   ├── configuracoes/
│   │   └── page.tsx
│   └── api/
│       ├── auth/
│       ├── analysis/
│       │   └── run/
│       └── settings/
├── components/
│   ├── layout/
│   ├── dashboard/
│   ├── charts/
│   └── ui/
├── lib/
│   ├── auth/
│   ├── supabase/
│   ├── github/
│   ├── formatting/
│   └── validation/
├── middleware.ts
└── package.json
```

Os módulos server-only devem permanecer isolados dos componentes client-side.

## Segurança

Requisitos obrigatórios:

- nenhuma secret em `NEXT_PUBLIC_*`;
- nenhum token em logs;
- validação de todo input de rota;
- autenticação obrigatória nas APIs internas;
- proteção CSRF nas mutações, ou uso de estratégia equivalente compatível com cookies `SameSite=Strict` e verificação de origem;
- headers de segurança apropriados;
- nenhuma renderização de HTML fornecido pelo Gemini sem escaping;
- timeouts em chamadas Supabase/GitHub quando aplicável;
- mensagens de erro sem detalhes de credenciais;
- valores financeiros tratados como strings/Decimal no backend de origem e formatados apenas para apresentação no frontend.

## Tratamento de falhas

O painel diferencia:

- dado indisponível;
- dado antigo;
- execução em andamento;
- execução falhou;
- integração externa indisponível;
- sessão expirada.

Não deve substituir dado ausente por zero nem esconder erro operacional como sucesso.

O botão de execução manual não altera o estado visual para "concluído" até que o backend persista uma execução concluída.

## Testes

Frontend:

- testes das funções de autenticação;
- login correto/incorreto;
- sessão expirada;
- proteção de rotas;
- validação da configuração de horário;
- cliente GitHub com sucesso e falhas;
- transformação de dados Supabase para view models;
- estados vazios dos gráficos;
- componentes críticos do dashboard.

Backend Python:

- leitura da configuração runtime;
- validação do horário `0..23`;
- precedência da configuração persistida sobre o default de ambiente;
- comportamento explícito quando a configuração não existe;
- scheduler continua idempotente;
- regressão do resumo Telegram.

CI:

- suíte Python existente continua obrigatória;
- adicionar lint/typecheck/test/build do projeto `web/`;
- build Next.js deve passar sem secrets reais usando configuração de teste/mocks apropriados.

## Deploy

O frontend será hospedado na Vercel a partir da pasta `web/` do mesmo repositório.

Secrets/configurações de produção serão inseridas na Vercel, nunca versionadas.

A aplicação deve funcionar com domínio padrão da Vercel inicialmente. Domínio próprio fica fora da v1.

## Biblioteca do ChatGPT

A documentação e os artefatos de trabalho do frontend serão espelhados na pasta existente:

```text
/mercado investimento
```

O GitHub continua sendo a fonte oficial de código e histórico de versão.

A Biblioteca do ChatGPT funciona como cópia persistente de trabalho e documentação para permitir continuidade entre conversas.

Nunca serão armazenados na Biblioteca:

- senha real;
- hash de produção se o usuário preferir mantê-lo exclusivamente na Vercel;
- `SUPABASE_SECRET_KEY`;
- `GITHUB_ACTIONS_TOKEN`;
- `TELEGRAM_BOT_TOKEN`;
- `GEMINI_API_KEY`;
- `.env` de produção.

## Critérios de conclusão da v1

A v1 estará concluída quando:

1. o usuário consegue acessar a URL Vercel e autenticar com a senha única;
2. uma sessão inválida não acessa nenhuma página ou API administrativa;
3. o dashboard mostra dados reais persistidos sem acessar secrets no navegador;
4. oportunidades e análises Gemini podem ser consultadas;
5. os quatro gráficos funcionam por ativo;
6. histórico possui filtros e paginação;
7. o resumo diário pode ser consultado;
8. o botão de análise dispara o workflow existente e o estado posterior é mostrado corretamente;
9. o horário do resumo pode ser alterado e é respeitado pelo backend Python;
10. Telegram continua funcionando independentemente do frontend;
11. CI Python e web passam;
12. nenhuma secret é versionada ou enviada ao browser;
13. documentação é atualizada;
14. o projeto é implantado na Vercel.

## Decisões explicitamente preservadas

- o frontend não substitui o backend Python;
- Telegram continua existindo;
- Gemini não define score financeiro;
- `candidate-v1` não é alterada por este projeto;
- GitHub Actions continua executando a automação;
- Supabase continua sendo a persistência central;
- Vercel hospeda apenas a camada web;
- a primeira versão é administrativa e para uso pessoal.
