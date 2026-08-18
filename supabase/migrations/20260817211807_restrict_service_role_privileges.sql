revoke all privileges on table public.currencies
    from service_role;
revoke all privileges on table public.markets
    from service_role;
revoke all privileges on table public.exchanges
    from service_role;
revoke all privileges on table public.assets
    from service_role;

grant select, insert, update, delete on table public.currencies
    to service_role;
grant select, insert, update, delete on table public.markets
    to service_role;
grant select, insert, update, delete on table public.exchanges
    to service_role;
grant select, insert, update, delete on table public.assets
    to service_role;
