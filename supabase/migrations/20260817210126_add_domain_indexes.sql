create index markets_default_currency_id_idx
    on public.markets (default_currency_id);

create index assets_currency_id_idx
    on public.assets (currency_id);
