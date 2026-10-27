# Virtual Wallet USDT — implementation plan, delivery 1

> **For agentic workers:** Use superpowers:subagent-driven-development with one implementer per task and independent scoped reviews. Existing isolated checkouts only. The user approved the design and implementation; do not ask for approval again.

**Goal:** Deliver the approved first lot: individual accounts and a working manual virtual wallet in USDT, with audit-safe atomic cash/trades/swaps, positions and history.
**Architecture:** PostgreSQL functions own accounting and authorization; server-only Next.js Auth REST/user JWT invokes them; existing Kraken market tables supply valuations. Existing shared-admin routes and refresh improvements remain intact.
**Tech Stack:** PostgreSQL16/SupabaseAuth/RLS/PLpgSQL, Next.js/TypeScript/Zod/Decimal, pytest/Docker/Playwright.
**Spec:** ../specs/2026-10-27-virtual-wallet-design.md (approved in chat).

## Global constraints
USDT only, no broker connection or real trades. No fabricated balances/prices/fees/probabilities. All money transports as decimal strings; user numeric values fit numeric(38,18) exactly, derived rounding HALF_UP, intermediateprecision80+. New tables only; preserve legacy portfolios. Ownership derives from auth.uid(), never callerowner_id. Financial writes only authenticated RPC with wallet lock, per-user rate limit30/min and idempotency. Replay occurred_at/sequence including reversals and backdating, reject negative balances at any point. Missing/stale/future price makes whole valuation incomplete, never zero. Kraken quotes max120s.

## Review focus
Concurrent overspend; partial swap rollback; cross-user JWT/table/RPC access; changedpayload/sameidempotencykey; reversal/backdatingcostbasis; unsafe numeric JSON precision; missing production schema/Auth configuration must be truthful unavailable, not fixture fallback.

## Shared interfaces
SQL functions:
- virtual_wallet_create(p_name text,p_key uuid) -> uuid; idempotent owner+creation key.
- virtual_wallet_apply(p_wallet_id uuid,p_request jsonb,p_key uuid) -> uuid.
- virtual_wallet_state(p_wallet_id uuid) -> jsonb.
- virtual_wallet_history(p_wallet_id uuid,p_before bigint default null,p_limit int default50) -> jsonb.
- virtual_wallet_market() -> jsonb, authenticated read-only Kraken market data.
All financial JSON values are TEXT, including nested operation request numbers. Sequences/counters can be ordinary safe integers (bounded below2^53).
`p_request` exact schema: kind; occurred_at ISO timestamp; amount string for DEPOSIT/WITHDRAWAL/FEE; for BUY/SELL asset_id uuid,quantity string,unit_price string,fees string(required,explicit0 allowed); SWAP sell_asset_id,sell_quantity,sell_unit_price,sell_fees,buy_asset_id,buy_quantity,buy_unit_price,buy_fees; REVERSAL reversal_of uuid. Unknown keys rejected. Positivequantity/price/amount, fees>=0. Timestamp notfuture. All operations create ledgerentries server-side, never accept arbitraryentries.
State JSON: wallet{id,name,base_currency_code}; cash,net_contributions,realized_pnl,fees,cost_basis (decimalstrings); positions[{asset_id,symbol,name,quantity,average_cost,cost_basis,price:null|string,observed_at:null|timestamp,market_value:null|string,unrealized_pnl:null|string,concentration_pct:null|string}]; market_value:null|string,known_market_value:string,unrealized_pnl:null|string,valuation_complete:boolean,evaluated_at:timestamp; operations:[historyentry],operations_total:int,next_before:null|bigint. Full history paginated50; calculations replay full effective ledger, never limited to50.
History entry: id,sequence,kind,occurred_at,created_at,request(JSON financialvaluesstrings),reversed:boolean,reversal_of:null|uuid. Responsehistory {operations,total,next_before}.
Market JSON: {evaluated_at,assets:[{id,symbol,name,currency_code:'USDT',quote:null|{price:string,observed_at,quality,provider,currency_code}}]}; only active CRYPTO/KRAKEN/USDT assets and latest kraken quote. No service key required to read through RPC, no grant to financial tables outside ownRLS.

### Task1 Database ledger and valuation
Files new supabase/migrations/20261027130000_virtual_wallet.sql, tests/virtual_wallet_db/*, tests/test_virtual_wallet_database.py, docs/20-virtual-wallet.md.
- [ ] RED real PostgreSQL tests ownerA/B, anon/directwrites denied, depositsnotprofit, BUY/SELL fees/costbasis, SWAP all-or-nothing, duplicates/conflict, overspend/backdating/reversal,replay,walletrate budget, exactdecimals/overflow, stale/missing/futureprice partialvaluation, historypagination, parallelwithdrawals.
- [ ] GREEN implement newtables/immutableentries,RLS,qualifiedSECURITYDEFINER functions, locks, secureRPCgrants, accounting and textJSON. No remote writes or migration application by implementer.
- [ ] Verify Docker PostgreSQL16 without exposedports, existingdomain/market migrations plusnewmigration; run newDBtests and wholepytest. Commit ownedfiles and report evidence/interface/rulings.

### Task2 Individual Auth and wallet UI
Files Atlas new src/lib/virtual-{auth,api,contracts}.ts, src/app/conta/**, src/app/virtual/**, src/components/virtual-wallet.tsx, additiveCSS, navlink, tests/auth/mock/e2e, README/envexample.
- [ ] RED tests valid/expired/userA/Bsessions, cookie flags, authentication not shared-admin, RPC usespublishablekey+userJWT only, safeerrors/idempotency and no servicekey inbrowser; browser signup/login/empty/create/deposit/buy/sell/swap/history/validation/stalevaluation/logout/mobile.
- [ ] GREEN Auth REST server-only (noSDKneeded): SUPABASE_URL plus SUPABASE_PUBLISHABLE_KEY; signin/signup/logout, verifiedGET/auth/v1/user; HttpOnly Secure SameSiteLax separatecookies access/refresh, refresh onserveraction and a safe same-origin renewalPOST route (GETnevermutates). Validate anyreturnURL tolocal/virtual. Keep adminhelpers separate. Emailconfirmationhoneststate, no fakeauto-login.
- [ ] UI /virtual with own /conta identity, forms callSQLRPCexactcontract; no duplicated monetaryaccounting. Provide explicit recordedswapprices/fees; absentcurrentquote isunavailable, no prototypevalues. Manualhistorypaging, privacy, currentpositiongain and cashflowsseparate. Forms keep stableUUIDidempotencykey throughretry, newkeyonsuccess. Handle schema-not-applied with meaningful setupstatus, nofakewallet.
- [ ] Verify lint/unit/build/typecheck/fullChromium; preserve existing15browsertests/13unit. Commit ownedfiles and report.

### Task3 Integration/review/deployment
Root owns secureexistingpublickeylocal/Vercelenv configuration, repositoryPRs, approvedmigrationaccessdiagnosis, schemaapplication onlyaftertests/review, read-onlylivevalidation and docsdelivery.
- [ ] Independent scoped security/accounting reviews and wholechange review; fix Important/Critical with regressions.
- [ ] Attempt authorized SQL management access only through existing credentials/tools. If absent, deliver complete testedSQLforoperatorSQLeditor and finish all unaffectedcode/config/deployment; don't invent adminSQLaccessfromRESTkey.
- [ ] Deploy existingAtlasproject; verify legacyHTTPS and /conta public + /virtualprotected; no manufacturing realuseraccounts or sending emailvia tools. Real user signup starts onlythroughuseraction.
- [ ] Document requiredSupabaseAuthSiteURL/redirectallowlist, migrationapplication/status and strict activationgap. Newwritingnotliveuntilschema exists. FeaturePRs,noautomaticmerge; save startinstructions.

## Later approved lots (not claimed in delivery1)
Simulador/concentração/radar técnico (lot2), then internalalerts/signalhistory/backtesting/data-sourceevaluation (lot3). Preserve requirements and create their plans after corewallet is usable; don't call them delivered withlot1. New inputscore/news/capitalization stays unavailable until verified sources are configured.
