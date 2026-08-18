# Arquitetura

## Estilo
Monólito modular assíncrono.

## Fluxo principal

Market Provider
    ↓
Collector
    ↓
Validator
    ↓
Supabase
    ↓
Analysis Engine
    ↓
AI Engine
    ↓
Opportunity Engine
    ↓
Alert Engine
    ↓
Telegram

## Módulos

### Market
Responsável pela obtenção e normalização dos dados.

### Portfolio
Responsável pelas operações e posições.

### Analysis
Calcula indicadores e métricas.

### AI
Interpreta dados já validados.

### Opportunity
Avalia relevância das condições detectadas.

### Alert
Decide se uma notificação deve ser enviada.

### Telegram
Interface com o usuário.

### Monitoring
Logs e estado dos serviços.

## Dependências permitidas

Telegram -> Services
Services -> Domain
Services -> Repositories
Services -> Providers

Domain não deve depender de Telegram, Supabase ou API externa.

## Persistência do domínio

Os repositories do domínio recebem `supabase.Client` por injeção de dependência; a criação do client permanece em `app.database.client`. Eles traduzem somente respostas externas validadas para modelos de persistência tipados e não substituem as constraints do PostgreSQL. O schema da Etapa 2 foi aplicado e validado no Supabase, inclusive pelo teste E2E opt-in.

## Mercados
A arquitetura deve suportar:
- múltiplas exchanges
- moedas
- países
- fusos horários
- providers
