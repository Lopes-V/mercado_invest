"""Real PostgreSQL16 tests. Opt in: VIRTUAL_WALLET_DB_TEST=1 python -m pytest ...

Only the local Docker socket, networkless atlas-wallet-pg container and dedicated
wallet_test database are used. No production credentials, Python DB drivers or
network connections are involved. The test bootstrap replaces local schemas.
"""
import json
import os
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path
import subprocess
from uuid import uuid4

import pytest

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / 'supabase/migrations/20261027130000_virtual_wallet.sql'
DOCKER = ['docker', '--host=unix:///var/run/docker.sock']
BTC = '40000000-0000-0000-0000-000000000001'
ETH = '40000000-0000-0000-0000-000000000002'
USD = '40000000-0000-0000-0000-000000000003'
T0 = '2026-01-01T00:00:00Z'
T1 = '2026-01-02T00:00:00Z'
T2 = '2026-01-03T00:00:00Z'
T3 = '2026-01-04T00:00:00Z'


def literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def sql(query, user=None, role='authenticated', ok=True):
    prefix = '' if user is None else f"set role {role}; set request.jwt.claim.sub = {literal(user)};"
    result = subprocess.run(DOCKER + ['exec', '-i', 'atlas-wallet-pg', 'psql', '-X', '-qAt', '-v', 'ON_ERROR_STOP=1', '-U', 'postgres', '-d', 'wallet_test'], input=prefix + query, text=True, capture_output=True, timeout=30)
    if ok:
        assert result.returncode == 0, result.stderr
        return result.stdout.strip()
    assert result.returncode != 0, 'Expected SQL rejection: ' + query
    return result.stderr


@pytest.fixture(scope='module', autouse=True)
def database():
    if os.environ.get('VIRTUAL_WALLET_DB_TEST') != '1':
        pytest.skip('Set VIRTUAL_WALLET_DB_TEST=1 with isolated atlas-wallet-pg PostgreSQL16')
    inspect = subprocess.run(DOCKER + ['inspect', 'atlas-wallet-pg'], capture_output=True, text=True, timeout=10, check=True)
    container = json.loads(inspect.stdout)[0]
    assert container['HostConfig']['NetworkMode'] == 'none'
    assert not container['NetworkSettings']['Ports']
    assert sql('select current_database()') == 'wallet_test'
    assert sql('show server_version_num').startswith('16')
    sql((ROOT / 'tests/virtual_wallet_db/bootstrap.sql').read_text())
    for path in sorted((ROOT / 'supabase/migrations').glob('20260817*.sql')):
        sql(path.read_text())
    sql((ROOT / 'supabase/migrations/20260821194749_create_market_data_tables.sql').read_text())
    sql((ROOT / 'tests/virtual_wallet_db/catalog.sql').read_text())
    if MIGRATION.exists():
        sql(MIGRATION.read_text())


@pytest.fixture
def owner():
    user = str(uuid4())
    sql(f'insert into auth.users values ({literal(user)})')
    sql('delete from public.market_quotes')
    return user


def create(user, key=None, name='Minha carteira'):
    return sql(f'select public.virtual_wallet_create({literal(name)}, {literal(key or uuid4())})', user)


def request(kind, when=T1, **kwargs):
    return dict(kind=kind, occurred_at=when, **kwargs)


def apply(user, wallet, req, key=None, ok=True):
    return sql(f'select public.virtual_wallet_apply({literal(wallet)}, {literal(json.dumps(req))}::jsonb, {literal(key or uuid4())})', user, ok=ok)


def state(user, wallet):
    return json.loads(sql(f'select public.virtual_wallet_state({literal(wallet)})', user))


def money(data, **values):
    for key, value in values.items():
        assert isinstance(data[key], str), (key, data[key])
        assert Decimal(data[key]) == Decimal(value), (key, data[key], value)


def funded(user, amount='1000'):
    wallet = create(user)
    apply(user, wallet, request('DEPOSIT', T0, amount=amount))
    return wallet


def trade(kind='BUY', asset=BTC, qty='2', price='100', fees='2', when=T1):
    return request(kind, when, asset_id=asset, quantity=qty, unit_price=price, fees=fees)


def quote(asset=BTC, price='120', age='0 seconds', quality='VALID', provider='kraken', currency='USDT'):
    sql(f"insert into public.market_quotes(asset_id,provider,provider_symbol,price,currency_code,observed_at,received_at,quality) values ({literal(asset)},{literal(provider)},'TEST',{literal(price)},{literal(currency)},now()-interval {literal(age)},now(),{literal(quality)})")


def test_deposit_is_cash_and_contribution_not_profit(owner):
    wallet = funded(owner)
    data = state(owner, wallet)
    assert data['wallet'] == dict(id=wallet, name='Minha carteira', base_currency_code='USDT')
    money(data, cash='1000', net_contributions='1000', realized_pnl='0', fees='0', cost_basis='0', market_value='1000', known_market_value='1000', unrealized_pnl='0')
    assert data['valuation_complete'] is True
    assert data['positions'] == []


def test_buy_sell_weighted_basis_fees_and_flat_position(owner):
    wallet = funded(owner)
    apply(owner, wallet, trade())  # cost 202, cash 798
    apply(owner, wallet, trade(qty='1', price='200', fees='1', when=T2))  # cost 403 / 3
    apply(owner, wallet, trade('SELL', qty='1', price='180', fees='3', when=T3))
    data = state(owner, wallet)
    money(data, cash='774', cost_basis='268.666666666666666667', realized_pnl='42.666666666666666667', fees='6')
    money(data['positions'][0], quantity='2', average_cost='134.333333333333333334')
    apply(owner, wallet, trade('SELL', qty='2', price='150', fees='0', when=T3))
    data = state(owner, wallet)
    money(data, cash='1074', cost_basis='0', realized_pnl='74')
    assert data['positions'] == []


def test_withdrawal_and_standalone_fee(owner):
    wallet = funded(owner)
    apply(owner, wallet, request('WITHDRAWAL', amount='100'))
    apply(owner, wallet, request('FEE', amount='3'))
    money(state(owner, wallet), cash='897', net_contributions='900', fees='3', realized_pnl='-3')


def test_same_creation_and_operation_keys_are_idempotent_and_conflicts_reject(owner):
    key = str(uuid4())
    wallet = create(owner, key)
    assert create(owner, key) == wallet
    sql(f"select public.virtual_wallet_create('changed',{literal(key)})", owner, ok=False)
    req = request('DEPOSIT', amount='10')
    op = apply(owner, wallet, req, key)
    assert apply(owner, wallet, req, key) == op
    assert 'idempotency' in apply(owner, wallet, request('DEPOSIT', amount='11'), key, ok=False).lower()
    assert state(owner, wallet)['operations_total'] == 1


def test_owner_rls_and_private_rpc_and_direct_mutations(owner):
    wallet = funded(owner)
    other = str(uuid4())
    sql(f'insert into auth.users values ({literal(other)})')
    assert sql('select count(*) from public.virtual_wallets', other) == '0'
    assert sql('select count(*) from public.virtual_operations', other) == '0'
    for user in [owner, other]:
        sql('select * from public.virtual_entries', user, ok=False)
    for rpc in [f"public.virtual_wallet_state('{wallet}')", f"public.virtual_wallet_history('{wallet}')", f"public.virtual_wallet_apply('{wallet}', '{{}}', '{uuid4()}')"]:
        sql(f'select {rpc}', other, ok=False)
    for role in ['anon', 'service_role']:
        sql(f"select public.virtual_wallet_state('{wallet}')", '', role=role, ok=False)
        sql('select public.virtual_wallet_market()', '', role=role, ok=False)
        sql('select * from public.virtual_wallets', '', role=role, ok=False)
    for table in ['virtual_wallets', 'virtual_operations', 'virtual_entries']:
        for command in [f'delete from public.{table}', f'update public.{table} set id=id', f'insert into public.{table}(id) values (gen_random_uuid())']:
            sql(command, owner, ok=False)
            sql(command, owner, role='service_role', ok=False)
    sql('select public.virtual_wallet_market()', '', ok=False)
    sql('select * from public.market_quotes', owner, ok=False)


def test_overspend_backdated_oversell_and_reversal_dependency_are_atomic(owner):
    wallet = funded(owner, '100')
    op = apply(owner, wallet, trade(qty='1', price='80', fees='0', when=T2))
    before = state(owner, wallet)
    for req in [request('WITHDRAWAL', amount='21'), trade('SELL', qty='2', price='100', fees='0', when=T3), request('WITHDRAWAL', T1, amount='30')]:
        apply(owner, wallet, req, ok=False)
    assert state(owner, wallet)['operations_total'] == before['operations_total']
    sell = apply(owner, wallet, trade('SELL', qty='1', price='90', fees='0', when=T3))
    apply(owner, wallet, request('REVERSAL', T3, reversal_of=op), ok=False)
    apply(owner, wallet, request('REVERSAL', T3, reversal_of=sell))
    apply(owner, wallet, request('REVERSAL', T3, reversal_of=op))
    money(state(owner, wallet), cash='100', cost_basis='0', realized_pnl='0')
    apply(owner, wallet, request('REVERSAL', T3, reversal_of=op), ok=False)


def test_reversal_replays_basis_and_keeps_original_audit(owner):
    wallet = funded(owner)
    first = apply(owner, wallet, trade(qty='1', price='100', fees='0'))
    apply(owner, wallet, trade(qty='1', price='200', fees='0', when=T2))
    apply(owner, wallet, trade('SELL', qty='1', price='300', fees='0', when=T3))
    money(state(owner, wallet), realized_pnl='150', cost_basis='150')
    reversal = apply(owner, wallet, request('REVERSAL', T3, reversal_of=first))
    data = state(owner, wallet)
    money(data, cash='1100', realized_pnl='100', cost_basis='0')
    assert next(o for o in data['operations'] if o['id'] == first)['reversed']
    assert next(o for o in data['operations'] if o['id'] == reversal)['reversal_of'] == first
    apply(owner, wallet, request('REVERSAL', T3, reversal_of=reversal), ok=False)


def test_swap_commits_both_legs_and_rollback_if_second_leg_fails(owner):
    wallet = funded(owner, '100')
    apply(owner, wallet, trade(qty='1', price='100', fees='0'))
    swap = request('SWAP', T2, sell_asset_id=BTC, sell_quantity='1', sell_unit_price='120', sell_fees='1', buy_asset_id=ETH, buy_quantity='2', buy_unit_price='60', buy_fees='1')
    apply(owner, wallet, swap, ok=False)
    data = state(owner, wallet)
    assert data['operations_total'] == 2
    money(data['positions'][0], quantity='1')
    swap['buy_unit_price'] = '50'
    apply(owner, wallet, swap)
    data = state(owner, wallet)
    money(data, cash='18', cost_basis='101', realized_pnl='19', fees='2')
    assert [p['asset_id'] for p in data['positions']] == [ETH]


@pytest.mark.parametrize('bad', [0, '0', '-1', 'NaN', 'Infinity', '1e2', '0.0000000000000000001', '100000000000000000000', None, True, {}, ' 1'])
def test_declared_numeric_rejects_invalid_precision_types_and_overflow(owner, bad):
    wallet = create(owner)
    apply(owner, wallet, request('DEPOSIT', amount=bad), ok=False)
    assert state(owner, wallet)['operations_total'] == 0


def test_decimal_smallest_unit_and_derived_half_up(owner):
    wallet = funded(owner, '0.000000000000000003')
    apply(owner, wallet, trade(qty='0.000000000000000001', price='1.5', fees='0'))
    data = state(owner, wallet)
    money(data, cash='0.000000000000000001', cost_basis='0.000000000000000002')
    assert isinstance(data['operations'][0]['request']['unit_price'], str)
    apply(owner, wallet, request('DEPOSIT', amount='99999999999999999999.999999999999999999'), ok=False)


def test_unknown_fields_missing_fees_future_and_invalid_catalog_reject(owner):
    wallet = funded(owner)
    bad_requests = [dict(request('DEPOSIT', amount='1'), owner_id=owner), request('DEPOSIT', '2999-01-01T00:00:00Z', amount='1'), request('DEPOSIT', 'today', amount='1'), trade(asset=USD), dict(trade(), quantity='0')]
    missing = trade()
    del missing['fees']
    bad_requests.extend([missing, [], None, dict(trade(), asset_id=str(uuid4()))])
    for req in bad_requests:
        apply(owner, wallet, req, ok=False)
    assert state(owner, wallet)['operations_total'] == 1


@pytest.mark.parametrize('age,quality,provider,currency', [('121 seconds','VALID','kraken','USDT'), ('-1 hour','VALID','kraken','USDT'), ('0 seconds','INVALID','kraken','USDT'), ('0 seconds','VALID','other','USDT'), ('0 seconds','VALID','kraken','USD')])
def test_untrusted_quotes_make_whole_valuation_incomplete(owner, age, quality, provider, currency):
    wallet = funded(owner)
    apply(owner, wallet, trade(qty='1', price='100', fees='0'))
    quote(age=age, quality=quality, provider=provider, currency=currency)
    data = state(owner, wallet)
    assert data['valuation_complete'] is False
    assert data['market_value'] is None and data['unrealized_pnl'] is None
    money(data, known_market_value='900')
    position = data['positions'][0]
    assert position['price'] is None and position['market_value'] is None and position['concentration_pct'] is None


def test_partial_and_complete_valuation_and_latest_quote_quality(owner):
    wallet = funded(owner)
    apply(owner, wallet, trade(qty='1', price='100', fees='0'))
    apply(owner, wallet, trade(asset=ETH, qty='2', price='50', fees='0'))
    quote(price='120')
    data = state(owner, wallet)
    money(data, known_market_value='920')
    assert data['market_value'] is None
    assert all(p['concentration_pct'] is None for p in data['positions'])
    quote(ETH, price='40')
    data = state(owner, wallet)
    money(data, market_value='1000', known_market_value='1000', unrealized_pnl='0')
    money(next(p for p in data['positions'] if p['asset_id'] == BTC), market_value='120', unrealized_pnl='20', concentration_pct='12')
    quote(price='130', age='-1 hour')  # latest is future; older valid cannot hide it
    assert state(owner, wallet)['market_value'] is None
    market = json.loads(sql('select public.virtual_wallet_market()', owner))
    assert len(market['assets']) == 2
    q = next(a for a in market['assets'] if a['id'] == ETH)['quote']
    assert q['provider'] == 'kraken' and q['currency_code'] == 'USDT' and isinstance(q['price'], str)


def test_nan_quote_is_unavailable_to_state_and_market(owner):
    wallet = funded(owner)
    apply(owner, wallet, trade(qty='1', price='100', fees='0'))
    quote(price='NaN')

    data = state(owner, wallet)
    assert data['valuation_complete'] is False
    assert data['market_value'] is None and data['unrealized_pnl'] is None
    position = data['positions'][0]
    assert position['price'] is None and position['market_value'] is None
    assert position['unrealized_pnl'] is None and position['concentration_pct'] is None

    market = json.loads(sql('select public.virtual_wallet_market()', owner))
    bitcoin = next(asset for asset in market['assets'] if asset['id'] == BTC)
    assert bitcoin['quote'] is None


def test_rate_limit_is_per_owner_across_wallets_with_retries_free(owner):
    one = create(owner)
    two = create(owner)
    key = str(uuid4())
    req = request('DEPOSIT', amount='1')
    op = apply(owner, one, req, key)
    for _ in range(27):
        apply(owner, two, req)
    assert apply(owner, one, req, key) == op
    assert 'rate' in apply(owner, one, req, ok=False).lower()
    assert state(owner, one)['operations_total'] == 1


def test_history_pages_full_replay_past_fifty(owner):
    wallet = create(owner)
    # Test harness alone ages rate events; production has no write grant.
    for batch in range(3):
        for _ in range(20):
            apply(owner, wallet, request('DEPOSIT', amount='1'))
        sql(f"delete from public.virtual_wallet_rate_events where owner_id={literal(owner)}")
    data = state(owner, wallet)
    money(data, cash='60', net_contributions='60')
    assert data['operations_total'] == 60 and len(data['operations']) == 50
    assert data['next_before'] is not None
    page = json.loads(sql(f"select public.virtual_wallet_history('{wallet}',{data['next_before']},50)", owner))
    assert len(page['operations']) == 10 and page['total'] == 60 and page['next_before'] is None
    assert not ({o['id'] for o in page['operations']} & {o['id'] for o in data['operations']})
    for limit in [0, 101]:
        sql(f"select public.virtual_wallet_history('{wallet}',null,{limit})", owner, ok=False)


def test_concurrent_withdrawals_cannot_double_spend(owner):
    wallet = funded(owner, '100')
    def withdraw(_):
        try:
            apply(owner, wallet, request('WITHDRAWAL', amount='70'))
            return True
        except AssertionError as exc:
            assert 'insufficient' in str(exc).lower()
            return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(withdraw, range(2))) == [False, True]
    money(state(owner, wallet), cash='30', net_contributions='30')
    assert state(owner, wallet)['operations_total'] == 2
