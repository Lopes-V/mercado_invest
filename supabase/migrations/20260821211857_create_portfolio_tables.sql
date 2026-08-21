create table public.portfolios (
    id uuid primary key default gen_random_uuid(),
    name text not null,
    base_currency_code text not null,
    is_active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint portfolios_name_non_blank check (btrim(name) <> ''),
    constraint portfolios_currency_code_check check (base_currency_code ~ '^[A-Z0-9]{3,10}$')
);

create table public.portfolio_transactions (
    id uuid primary key default gen_random_uuid(),
    portfolio_id uuid not null references public.portfolios(id) on delete restrict,
    asset_id uuid not null references public.assets(id) on delete restrict,
    transaction_type text not null,
    quantity numeric(38,18) not null,
    unit_price numeric(38,18) not null,
    fees numeric(38,18) not null default 0,
    currency_code text not null,
    occurred_at timestamptz not null,
    external_reference text,
    created_at timestamptz not null default now(),
    constraint portfolio_transactions_type_check check (transaction_type in ('BUY', 'SELL')),
    constraint portfolio_transactions_quantity_check check (quantity > 0),
    constraint portfolio_transactions_unit_price_check check (unit_price >= 0),
    constraint portfolio_transactions_fees_check check (fees >= 0),
    constraint portfolio_transactions_currency_check check (currency_code ~ '^[A-Z0-9]{3,10}$')
);
create unique index portfolio_transactions_external_reference_unique
    on public.portfolio_transactions (portfolio_id, external_reference)
    where external_reference is not null;

create table public.portfolio_snapshots (
    id uuid primary key default gen_random_uuid(),
    portfolio_id uuid not null references public.portfolios(id) on delete restrict,
    as_of timestamptz not null,
    total_cost_basis numeric(38,18) not null,
    market_value numeric(38,18) not null,
    unrealized_pnl numeric(38,18) not null,
    created_at timestamptz not null default now(),
    constraint portfolio_snapshots_identity_unique unique (portfolio_id, as_of)
);

alter table public.portfolios enable row level security;
alter table public.portfolio_transactions enable row level security;
alter table public.portfolio_snapshots enable row level security;
revoke all privileges on table public.portfolios, public.portfolio_transactions, public.portfolio_snapshots from anon, authenticated, public, service_role;
grant select, insert, update, delete on table public.portfolios, public.portfolio_transactions, public.portfolio_snapshots to service_role;
