alter table public.currencies enable row level security;
alter table public.markets enable row level security;
alter table public.exchanges enable row level security;
alter table public.assets enable row level security;

revoke all privileges on table public.currencies
    from anon, authenticated, public;
revoke all privileges on table public.markets
    from anon, authenticated, public;
revoke all privileges on table public.exchanges
    from anon, authenticated, public;
revoke all privileges on table public.assets
    from anon, authenticated, public;

grant select, insert, update, delete on table public.currencies
    to service_role;
grant select, insert, update, delete on table public.markets
    to service_role;
grant select, insert, update, delete on table public.exchanges
    to service_role;
grant select, insert, update, delete on table public.assets
    to service_role;
