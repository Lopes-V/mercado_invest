# Kraken Radar Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans inline. Existing isolated checkouts; no new worktree. User explicitly requested implementation after the public API probe.

**Goal:** Make Kraken prices and analysis-v2 visible in Atlas using the existing crypto radar.
**Architecture:** Kraken adapter → provider-aware catalog/radar/store/CLI → existing Supabase tables → authenticated Atlas. No automatic merge or orders.
**Tech Stack:** Python/httpx/Decimal/Supabase and Next.js/Playwright.
**Spec:** ../specs/2026-10-27-kraken-radar-design.md

## Global Constraints
Three USDT pairs; 15m/1h; quote120s; closed/continuous history; no synthetic data, fallback, secrets, migration or changes to stocks/analysis-v1/v2 formulas. Explicit source isolation.

## Review Focus
Wrong Kraken response market key; open/future/conflicting candles; truncated 720-row ranges; fresh analysis with stale quote; cross-provider persisted identity and repeated metric conflicts.

### Task 1: Kraken adapter
Files app/market_data/providers/kraken.py, tests/test_kraken_provider.py, providers exports.
Interface KrakenProvider(http_client, *, clock=UTCnow), same protocol, get_liquidity optional unavailable (no fabricated turnover).
- [x] RED tests for canonical BTC alias, genuine trade price/time, online USDT metadata, API errors/wrong market, malformed decimals, 15m/1h closed/range filtering, duplicates, invalid OHLC and too-old range.
- [x] GREEN implement strict public adapter and verify provider tests/whole Python suite; commit.

### Task 2: Source-aware radar
Files app/crypto/{catalog,radar,storage}.py, app/crypto_radar.py, workflow, tests/test_crypto_{radar,storage,cli}.py.
- [x] RED provider-isolated catalog/scan/storage tests and explicit CLI source tests.
- [x] GREEN add explicit provider selection/default Kraken, source-specific audit/HTTP codes, workflow CRYPTO_PROVIDER=kraken. Preserve Bybit caller compatibility and all quality gates. Run whole suite; commit.

### Task 3: Atlas source change
Files atlas-web/src/lib/data.ts, src/components/crypto.tsx, fixtures/e2e, README.
- [x] RED fixture/query/header/source tests expecting Kraken; run baseline browser regression to observe failure.
- [x] GREEN update source filters/labels, preserve auth/expiry and stock isolation. Verify lint/unit/build/typecheck/Chromium; commit.

### Task 4: Review and delivery
- [x] One fresh whole-change review of both repos, fix important findings with RED/GREEN evidence.
- [x] Push feature branches/draft PRs. Run manual Kraken collection in GitHub; inspect Supabase facts, errors and repeat idempotence. Deploy Atlas and verify HTTPS login/actual Kraken data.
- [x] Record counts, successful/failed pairs, recurrence pending merge and reusable startup instructions. No automatic merge.

## Delivery evidence

- Backend582passed/21opt-in skipped; frontend13unit/14Chromium and lint/build/typecheck passed.
- Whole-change independent review: two important temporal findings reproduced RED then fixed GREEN. Future Kraken trades rejected before persistence; latest200 closed candles anchor repeated indicator seeds. No critical or minor findings.
- Real feature-branch run40498138810: BTCUSDT and ETHUSDT READY, SOLUSDT STALE_OR_INVALID_QUOTE. Existing BTC/ETH analyses reused across repeated collections, source-separated quotes/candles and metrics verified in Supabase.
- Atlas deployment dpl_3avoC69PoufWFYE5ZoN8JaVPwKEm READY; production HTTPS auth and Kraken prices/EMA/RSI panels for BTC/ETH validated, SOL unavailable, stock records preserved. No secrets in authenticated HTML.
- DraftPR backend https://github.com/Lopes-V/mercado_invest/pull/5 and Atlas https://github.com/Lopes-V/atlas-web/pull/2 . No automatic merge. Scheduled Kraken source requires backend merge; manual feature collection succeeded for valid pairs, full three-pair report remains incomplete because SOL is stale.
