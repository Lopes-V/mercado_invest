-- Virtual records only. Apply after domain/market migrations in Supabase.
-- All client writes enter authenticated RPCs; never grant service_role writes.
begin;

create table public.virtual_wallets (
    id uuid primary key default gen_random_uuid(),
    owner_id uuid not null references auth.users(id) on delete restrict,
    name text not null check (length(name) between 1 and 120 and name = btrim(name)),
    base_currency_code text not null default 'USDT' check (base_currency_code = 'USDT'),
    is_active boolean not null default true,
    creation_key uuid not null,
    created_at timestamptz not null default clock_timestamp(),
    unique (owner_id, creation_key)
);
create table public.virtual_operations (
    id uuid primary key default gen_random_uuid(),
    wallet_id uuid not null references public.virtual_wallets(id) on delete restrict,
    sequence bigint not null check (sequence between 1 and 9007199254740991),
    kind text not null check (kind in ('DEPOSIT','WITHDRAWAL','FEE','BUY','SELL','SWAP','REVERSAL')),
    occurred_at timestamptz not null check (isfinite(occurred_at)),
    created_at timestamptz not null default clock_timestamp(),
    idempotency_key uuid not null,
    request jsonb not null check (jsonb_typeof(request) = 'object'),
    -- Exact canonical JSON equality (including string values), not a lossy hash.
    reversal_of uuid references public.virtual_operations(id) on delete restrict,
    origin text not null default 'USER_DECLARED' check (origin = 'USER_DECLARED'),
    unique (wallet_id, sequence), unique (wallet_id, idempotency_key), unique (reversal_of),
    check ((kind = 'REVERSAL') = (reversal_of is not null))
);
create index virtual_operations_replay_idx on public.virtual_operations(wallet_id, occurred_at, sequence);
create table public.virtual_entries (
    id uuid primary key default gen_random_uuid(),
    operation_id uuid not null references public.virtual_operations(id) on delete restrict,
    leg smallint not null check (leg between 0 and 2),
    entry_class text not null check (entry_class in ('CASH','ASSET')),
    asset_id uuid references public.assets(id) on delete restrict,
    currency_code text not null default 'USDT' check (currency_code = 'USDT'),
    quantity numeric(38,18) not null,
    unit_price numeric(38,18),
    category text not null check (category in ('TRADE','FEE','CONTRIBUTION')),
    created_at timestamptz not null default clock_timestamp(),
    check ((entry_class = 'CASH' and asset_id is null and unit_price is null)
        or (entry_class = 'ASSET' and asset_id is not null and unit_price > 0 and category = 'TRADE' and quantity <> 0)),
    unique (operation_id, leg, entry_class, category)
);
create table public.virtual_wallet_rate_events (
    owner_id uuid not null references auth.users(id) on delete restrict,
    created_at timestamptz not null default clock_timestamp()
);
create index virtual_wallet_rate_events_owner_time_idx on public.virtual_wallet_rate_events(owner_id, created_at);

alter table public.virtual_wallets enable row level security;
alter table public.virtual_operations enable row level security;
alter table public.virtual_entries enable row level security;
alter table public.virtual_wallet_rate_events enable row level security;
revoke all on public.virtual_wallets, public.virtual_operations, public.virtual_entries, public.virtual_wallet_rate_events from public, anon, authenticated, service_role;
grant select on public.virtual_wallets, public.virtual_operations to authenticated;
create policy virtual_wallets_owner_read on public.virtual_wallets for select to authenticated using (owner_id = (select auth.uid()));
create policy virtual_operations_owner_read on public.virtual_operations for select to authenticated using (exists (select 1 from public.virtual_wallets w where w.id = wallet_id and w.owner_id = (select auth.uid())));
create policy virtual_entries_owner_read on public.virtual_entries for select to authenticated using (exists (select 1 from public.virtual_operations o join public.virtual_wallets w on w.id = o.wallet_id where o.id = operation_id and w.owner_id = (select auth.uid())));

create function public._virtual_wallet_immutable() returns trigger
language plpgsql set search_path = '' as $$ begin
    raise exception 'virtual ledger is immutable' using errcode = '55000';
end $$;
create trigger virtual_operations_immutable before update or delete on public.virtual_operations for each row execute function public._virtual_wallet_immutable();
create trigger virtual_entries_immutable before update or delete on public.virtual_entries for each row execute function public._virtual_wallet_immutable();

-- Unconstrained numeric arithmetic is exact for addition/multiplication. Division
-- operands use 100 fractional digits to exceed the required 80-digit precision.
-- round(numeric,18) rounds ties away from zero (decimal HALF_UP).
create function public._virtual_wallet_round(p_value numeric) returns numeric
language plpgsql immutable set search_path = '' as $$
declare v numeric;
begin
    v := round(p_value, 18);
    if v is null or v::text in ('NaN','Infinity','-Infinity') or abs(v) >= 100000000000000000000::numeric then
        raise exception 'financial numeric overflow' using errcode = '22003';
    end if;
    return v::numeric(38,18);
end $$;
create function public._virtual_wallet_decimal(p_value jsonb, p_allow_zero boolean default false) returns numeric
language plpgsql immutable set search_path = '' as $$
declare v numeric; s text;
begin
    s := p_value #>> '{}';
    if jsonb_typeof(p_value) is distinct from 'string' or length(s) > 80 or s !~ '^[0-9]+([.][0-9]+)?$' then
        raise exception 'financial value must be a plain decimal string' using errcode = '22023';
    end if;
    v := s::numeric;
    if v <> round(v,18) or v >= 100000000000000000000::numeric or v < 0 or (not p_allow_zero and v = 0) then
        raise exception 'financial value outside exact numeric(38,18) bounds' using errcode = '22003';
    end if;
    return v::numeric(38,18);
end $$;
create function public._virtual_wallet_owner(p_wallet_id uuid) returns uuid
language plpgsql stable set search_path = '' as $$
declare u uuid := auth.uid();
begin
    if u is null or not exists (select 1 from public.virtual_wallets w where w.id = p_wallet_id and w.owner_id = u and w.is_active) then
        raise exception 'wallet unavailable for authenticated owner' using errcode = '42501';
    end if;
    return u;
end $$;
create function public._virtual_wallet_rate(p_owner uuid) returns void
language plpgsql volatile set search_path = '' as $$ begin
    -- Caller has acquired the per-owner advisory transaction lock first.
    if (select count(*) from public.virtual_wallet_rate_events r where r.owner_id = p_owner and r.created_at > clock_timestamp() - interval '1 minute') >= 30 then
        raise exception 'wallet write rate limit exceeded' using errcode = 'P0001';
    end if;
    insert into public.virtual_wallet_rate_events(owner_id) values (p_owner);
end $$;
create function public._virtual_wallet_asset(p_asset uuid) returns void
language plpgsql stable set search_path = '' as $$ begin
    if not exists (
        select 1 from public.assets a
        join public.markets m on m.id = a.market_id
        join public.exchanges e on e.id = a.exchange_id and e.market_id = m.id
        join public.currencies c on c.id = a.currency_id
        where a.id = p_asset and a.is_active and m.is_active and e.is_active and c.is_active
        and a.asset_type = 'CRYPTO' and m.code = 'CRYPTO' and e.code = 'KRAKEN' and c.code = 'USDT'
    ) then raise exception 'asset unavailable for Kraken USDT wallet' using errcode = '22023'; end if;
end $$;
create function public._virtual_wallet_trade_entries(p_operation uuid, p_leg smallint, p_asset uuid, p_quantity numeric, p_price numeric, p_fees numeric, p_buy boolean) returns void
language plpgsql set search_path = '' as $$
declare gross numeric := public._virtual_wallet_round(p_quantity * p_price);
begin
    perform public._virtual_wallet_asset(p_asset);
    insert into public.virtual_entries(operation_id,leg,entry_class,asset_id,quantity,unit_price,category)
    values (p_operation,p_leg,'ASSET',p_asset,case when p_buy then p_quantity else -p_quantity end,p_price,'TRADE');
    insert into public.virtual_entries(operation_id,leg,entry_class,quantity,category)
    values (p_operation,p_leg,'CASH',case when p_buy then -gross else gross end,'TRADE'),
           (p_operation,p_leg,'CASH',-p_fees,'FEE');
end $$;

-- Replay the complete effective ledger. A reversal cancels the original at its
-- original place in time; it is never booked as an inverse trade at today's cost.
create function public._virtual_wallet_replay(p_wallet_id uuid) returns jsonb
language plpgsql stable set search_path = '' as $$
declare
    op record; legrow record; ar record; pos jsonb := '{}'::jsonb; item jsonb;
    cash numeric := 0; contributions numeric := 0; fees numeric := 0; pnl numeric := 0;
    q numeric; basis numeric; removed numeric; trade_cash numeric; leg_fee numeric; delta numeric;
    total_basis numeric := 0; positions jsonb := '[]'::jsonb;
begin
    for op in select o.* from public.virtual_operations o where o.wallet_id = p_wallet_id and o.kind <> 'REVERSAL'
        and not exists (select 1 from public.virtual_operations r where r.reversal_of = o.id)
        order by o.occurred_at, o.sequence
    loop
        for legrow in select distinct e.leg from public.virtual_entries e where e.operation_id = op.id order by e.leg loop
            select coalesce(sum(e.quantity) filter(where e.entry_class='CASH' and e.category='TRADE'),0),
                   coalesce(-sum(e.quantity) filter(where e.entry_class='CASH' and e.category='FEE'),0),
                   coalesce(sum(e.quantity) filter(where e.entry_class='CASH'),0)
                into trade_cash, leg_fee, delta from public.virtual_entries e where e.operation_id=op.id and e.leg=legrow.leg;
            for ar in select e.* from public.virtual_entries e where e.operation_id=op.id and e.leg=legrow.leg and e.entry_class='ASSET' loop
                item := pos -> ar.asset_id::text;
                q := coalesce((item->>'quantity')::numeric,0);
                basis := coalesce((item->>'cost_basis')::numeric,0);
                if ar.quantity > 0 then
                    q := public._virtual_wallet_round(q + ar.quantity);
                    basis := public._virtual_wallet_round(basis - trade_cash + leg_fee);
                else
                    if q < -ar.quantity then raise exception 'insufficient asset balance during chronological replay' using errcode='23514'; end if;
                    if q = -ar.quantity then removed := basis;
                    else removed := public._virtual_wallet_round((basis * -ar.quantity)::numeric(180,100) / q); end if;
                    basis := public._virtual_wallet_round(basis - removed);
                    q := public._virtual_wallet_round(q + ar.quantity);
                    pnl := public._virtual_wallet_round(pnl + trade_cash - leg_fee - removed);
                end if;
                pos := jsonb_set(pos,array[ar.asset_id::text],jsonb_build_object('quantity',q::text,'cost_basis',basis::text));
            end loop;
            cash := public._virtual_wallet_round(cash + delta);
            if cash < 0 then raise exception 'insufficient cash during chronological replay' using errcode='23514'; end if;
            fees := public._virtual_wallet_round(fees + leg_fee);
            if op.kind in ('DEPOSIT','WITHDRAWAL') then contributions := public._virtual_wallet_round(contributions + delta); end if;
            if op.kind = 'FEE' then pnl := public._virtual_wallet_round(pnl - leg_fee); end if;
        end loop;
    end loop;
    for ar in select key,value from jsonb_each(pos) order by key loop
        q := (ar.value->>'quantity')::numeric; basis := (ar.value->>'cost_basis')::numeric;
        if q > 0 then
            total_basis := public._virtual_wallet_round(total_basis + basis);
            positions := positions || jsonb_build_array(jsonb_build_object('asset_id',ar.key,'quantity',q::text,'cost_basis',basis::text,
                'average_cost',public._virtual_wallet_round(basis::numeric(180,100)/q)::text));
        end if;
    end loop;
    return jsonb_build_object('cash',public._virtual_wallet_round(cash)::text,'net_contributions',public._virtual_wallet_round(contributions)::text,
        'fees',public._virtual_wallet_round(fees)::text,'realized_pnl',public._virtual_wallet_round(pnl)::text,
        'cost_basis',public._virtual_wallet_round(total_basis)::text,'positions',positions);
end $$;

create function public.virtual_wallet_create(p_name text,p_key uuid) returns uuid
language plpgsql security definer set search_path = '' as $$
declare u uuid := auth.uid(); w public.virtual_wallets%rowtype;
begin
    if u is null then raise exception 'authentication required' using errcode='42501'; end if;
    if p_name is null or p_name <> btrim(p_name) or length(p_name) not between 1 and 120 or p_key is null then
        raise exception 'invalid wallet name or idempotency key' using errcode='22023'; end if;
    perform pg_advisory_xact_lock(hashtextextended(u::text, 752196));
    select * into w from public.virtual_wallets where owner_id=u and creation_key=p_key;
    if found then
        if w.name <> p_name then raise exception 'idempotency key conflicts with creation request' using errcode='22023'; end if;
        return w.id;
    end if;
    perform public._virtual_wallet_rate(u);
    insert into public.virtual_wallets(owner_id,name,creation_key) values(u,p_name,p_key) returning * into w;
    return w.id;
end $$;

create function public.virtual_wallet_apply(p_wallet_id uuid,p_request jsonb,p_key uuid) returns uuid
language plpgsql security definer set search_path = '' as $$
declare
    u uuid := auth.uid(); existing public.virtual_operations%rowtype; target public.virtual_operations%rowtype;
    k text; fields text[]; field text; happened timestamptz; reversal uuid; op uuid; seq bigint;
    amount numeric; q numeric; price numeric; fee numeric; aid uuid; leg smallint; prefix text;
begin
    if u is null then raise exception 'authentication required' using errcode='42501'; end if;
    perform pg_advisory_xact_lock(hashtextextended(u::text, 752196));
    perform public._virtual_wallet_owner(p_wallet_id);
    perform 1 from public.virtual_wallets where id=p_wallet_id for update;
    if p_key is null then raise exception 'idempotency key required' using errcode='22023'; end if;
    select * into existing from public.virtual_operations where wallet_id=p_wallet_id and idempotency_key=p_key;
    if found then
        if existing.request is distinct from p_request then raise exception 'idempotency key conflicts with request' using errcode='22023'; end if;
        return existing.id;
    end if;
    if jsonb_typeof(p_request) is distinct from 'object' or pg_column_size(p_request)>4096 then raise exception 'invalid operation request' using errcode='22023'; end if;
    k := p_request->>'kind';
    fields := case k
      when 'DEPOSIT' then array['kind','occurred_at','amount'] when 'WITHDRAWAL' then array['kind','occurred_at','amount'] when 'FEE' then array['kind','occurred_at','amount']
      when 'BUY' then array['kind','occurred_at','asset_id','quantity','unit_price','fees'] when 'SELL' then array['kind','occurred_at','asset_id','quantity','unit_price','fees']
      when 'SWAP' then array['kind','occurred_at','sell_asset_id','sell_quantity','sell_unit_price','sell_fees','buy_asset_id','buy_quantity','buy_unit_price','buy_fees']
      when 'REVERSAL' then array['kind','occurred_at','reversal_of'] else null end;
    if fields is null or not (p_request ?& fields) or exists(select 1 from jsonb_object_keys(p_request) key where not(key=any(fields))) then
        raise exception 'unknown or missing operation fields' using errcode='22023'; end if;
    foreach field in array fields loop
        if jsonb_typeof(p_request->field) is distinct from 'string' then raise exception 'operation fields must be strings' using errcode='22023'; end if;
    end loop;
    if (p_request->>'occurred_at') !~ '^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}([.]\d{1,6})?(Z|[+-]\d{2}:\d{2})$' then
        raise exception 'occurred_at must be ISO timestamp with timezone' using errcode='22023'; end if;
    happened := (p_request->>'occurred_at')::timestamptz;
    if not isfinite(happened) or happened > clock_timestamp() then raise exception 'occurred_at cannot be future' using errcode='22023'; end if;
    if k='REVERSAL' then
        reversal := (p_request->>'reversal_of')::uuid;
        select * into target from public.virtual_operations where id=reversal and wallet_id=p_wallet_id;
        if not found or target.kind='REVERSAL' or happened < target.occurred_at or exists(select 1 from public.virtual_operations where reversal_of=reversal) then
            raise exception 'invalid reversal target or timestamp' using errcode='22023'; end if;
    end if;
    perform public._virtual_wallet_rate(u);
    select coalesce(max(sequence),0)+1 into seq from public.virtual_operations where wallet_id=p_wallet_id;
    insert into public.virtual_operations(wallet_id,sequence,kind,occurred_at,idempotency_key,request,reversal_of)
        values(p_wallet_id,seq,k,happened,p_key,p_request,reversal) returning id into op;
    if k in ('DEPOSIT','WITHDRAWAL','FEE') then
        amount := public._virtual_wallet_decimal(p_request->'amount');
        insert into public.virtual_entries(operation_id,leg,entry_class,quantity,category)
            values(op,0,'CASH',case when k='DEPOSIT' then amount else -amount end,case when k='FEE' then 'FEE' else 'CONTRIBUTION' end);
    elsif k in ('BUY','SELL','SWAP') then
        for leg in 1..case when k='SWAP' then 2 else 1 end loop
            prefix := case when k='SWAP' and leg=1 then 'sell_' when k='SWAP' then 'buy_' else '' end;
            aid := (p_request->>(prefix || 'asset_id'))::uuid;
            q := public._virtual_wallet_decimal(p_request->(prefix || 'quantity'));
            price := public._virtual_wallet_decimal(p_request->(prefix || 'unit_price'));
            fee := public._virtual_wallet_decimal(p_request->(prefix || 'fees'),true);
            perform public._virtual_wallet_trade_entries(op,leg::smallint,aid,q,price,fee,k='BUY' or (k='SWAP' and leg=2));
        end loop;
    end if;
    perform public._virtual_wallet_replay(p_wallet_id); -- any error rolls back operation, entries and budget
    return op;
end $$;

create function public.virtual_wallet_history(p_wallet_id uuid,p_before bigint default null,p_limit int default 50) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare result jsonb; total bigint; cursor_value bigint;
begin
    perform public._virtual_wallet_owner(p_wallet_id);
    if p_limit is null or p_limit not between 1 and 100 or (p_before is not null and p_before not between 1 and 9007199254740991) then
        raise exception 'invalid history page' using errcode='22023'; end if;
    select count(*) into total from public.virtual_operations where wallet_id=p_wallet_id;
    select coalesce(jsonb_agg(jsonb_build_object('id',o.id,'sequence',o.sequence,'kind',o.kind,'occurred_at',o.occurred_at,'created_at',o.created_at,'request',o.request,
        'reversal_of',o.reversal_of,'reversed',exists(select 1 from public.virtual_operations r where r.reversal_of=o.id)) order by o.sequence desc),'[]'::jsonb),min(o.sequence)
        into result,cursor_value from (select * from public.virtual_operations where wallet_id=p_wallet_id and (p_before is null or sequence<p_before) order by sequence desc limit p_limit) o;
    if not exists(select 1 from public.virtual_operations where wallet_id=p_wallet_id and sequence<cursor_value) then cursor_value:=null; end if;
    return jsonb_build_object('operations',result,'total',total,'next_before',cursor_value);
end $$;

create function public.virtual_wallet_market() returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare result jsonb;
begin
    if auth.uid() is null then raise exception 'authentication required' using errcode='42501'; end if;
    select coalesce(jsonb_agg(jsonb_build_object('id',a.id,'symbol',a.symbol,'name',a.name,'currency_code','USDT','quote',
        case when q.id is null or q.price::text in ('NaN','Infinity','-Infinity') or q.price<=0 or q.currency_code<>'USDT' then null else jsonb_build_object('price',q.price::text,'observed_at',q.observed_at,'quality',q.quality,'provider',q.provider,'currency_code',q.currency_code) end) order by a.symbol,a.id),'[]'::jsonb)
        into result from public.assets a join public.markets m on m.id=a.market_id
        join public.exchanges e on e.id=a.exchange_id and e.market_id=m.id join public.currencies c on c.id=a.currency_id
        left join lateral (select mq.* from public.market_quotes mq where mq.asset_id=a.id and mq.provider='kraken' order by mq.observed_at desc,mq.created_at desc,mq.id desc limit 1) q on true
        where a.is_active and m.is_active and e.is_active and c.is_active and a.asset_type='CRYPTO' and m.code='CRYPTO' and e.code='KRAKEN' and c.code='USDT';
    return jsonb_build_object('evaluated_at',statement_timestamp(),'assets',result);
end $$;

create function public.virtual_wallet_state(p_wallet_id uuid) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare
    ledger jsonb; history jsonb; w public.virtual_wallets%rowtype; p jsonb; a record; q record;
    positions jsonb := '[]'::jsonb; enriched jsonb := '[]'::jsonb;
    evaluated timestamptz := statement_timestamp(); complete boolean := true;
    known numeric; value numeric; unrealized numeric; all_unrealized numeric := 0;
    concentration numeric; unrealized_pct numeric;
begin
    perform public._virtual_wallet_owner(p_wallet_id);
    select * into w from public.virtual_wallets where id=p_wallet_id;
    ledger := public._virtual_wallet_replay(p_wallet_id);
    known := (ledger->>'cash')::numeric;
    for p in select * from jsonb_array_elements(ledger->'positions') loop
        select x.*,m.is_active and m.code='CRYPTO' and e.is_active and e.code='KRAKEN' and c.is_active and c.code='USDT' and x.is_active and x.asset_type='CRYPTO' as allowed
            into a from public.assets x join public.markets m on m.id=x.market_id join public.exchanges e on e.id=x.exchange_id and e.market_id=m.id join public.currencies c on c.id=x.currency_id where x.id=(p->>'asset_id')::uuid;
        select * into q from public.market_quotes mq where mq.asset_id=(p->>'asset_id')::uuid and mq.provider='kraken' order by mq.observed_at desc,mq.created_at desc,mq.id desc limit 1;
        value := null; unrealized := null; unrealized_pct := null;
        if a.allowed and q.id is not null and q.quality='VALID' and q.currency_code='USDT' and q.price::text not in ('NaN','Infinity','-Infinity') and q.price>0 and q.observed_at<=evaluated and q.observed_at>=evaluated-interval '120 seconds' then
            value := public._virtual_wallet_round((p->>'quantity')::numeric*q.price);
            unrealized := public._virtual_wallet_round(value-(p->>'cost_basis')::numeric);
            known := public._virtual_wallet_round(known+value);
            all_unrealized := public._virtual_wallet_round(all_unrealized+unrealized);
            if (p->>'cost_basis')::numeric>0 then unrealized_pct:=public._virtual_wallet_round((unrealized*100)::numeric(180,100)/(p->>'cost_basis')::numeric); end if;
        else complete:=false; end if;
        positions:=positions || jsonb_build_array(p || jsonb_build_object('symbol',a.symbol,'name',a.name,'price',case when value is not null then q.price::text else null end,
            'observed_at',q.observed_at,'market_value',value::text,'unrealized_pnl',unrealized::text,'unrealized_pnl_pct',unrealized_pct::text));
    end loop;
    for p in select * from jsonb_array_elements(positions) loop
        concentration:=null;
        if complete and known>0 then concentration:=public._virtual_wallet_round(((p->>'market_value')::numeric*100)::numeric(180,100)/known); end if;
        enriched:=enriched || jsonb_build_array(p || jsonb_build_object('concentration_pct',concentration::text));
    end loop;
    history := public.virtual_wallet_history(p_wallet_id);
    return ledger || jsonb_build_object('wallet',jsonb_build_object('id',w.id,'name',w.name,'base_currency_code',w.base_currency_code),
        'positions',enriched,'market_value',case when complete then public._virtual_wallet_round(known)::text else null end,
        'known_market_value',public._virtual_wallet_round(known)::text,'unrealized_pnl',case when complete then public._virtual_wallet_round(all_unrealized)::text else null end,
        'valuation_complete',complete,'evaluated_at',evaluated,'operations',history->'operations','operations_total',history->'total','next_before',history->'next_before');
end $$;

-- Revoke default PUBLIC execution, including internal helpers. Explicit list
-- avoids affecting any pre-existing functions or domain/market privileges.
revoke all on function public._virtual_wallet_immutable(), public._virtual_wallet_round(numeric), public._virtual_wallet_decimal(jsonb,boolean),
    public._virtual_wallet_owner(uuid), public._virtual_wallet_rate(uuid), public._virtual_wallet_asset(uuid),
    public._virtual_wallet_trade_entries(uuid,smallint,uuid,numeric,numeric,numeric,boolean), public._virtual_wallet_replay(uuid),
    public.virtual_wallet_create(text,uuid), public.virtual_wallet_apply(uuid,jsonb,uuid), public.virtual_wallet_history(uuid,bigint,int),
    public.virtual_wallet_market(), public.virtual_wallet_state(uuid) from public, anon, authenticated, service_role;
grant execute on function public.virtual_wallet_create(text,uuid), public.virtual_wallet_apply(uuid,jsonb,uuid),
    public.virtual_wallet_history(uuid,bigint,int), public.virtual_wallet_market(), public.virtual_wallet_state(uuid) to authenticated;
notify pgrst, 'reload schema';
commit;
