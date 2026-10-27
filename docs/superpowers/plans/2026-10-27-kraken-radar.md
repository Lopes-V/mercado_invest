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
- [ ] RED tests for canonical BTC alias, genuine trade price/time, online USDT metadata, API errors/wrong market, malformed decimals, 15m/1h closed/range filtering, duplicates, invalid OHLC and too-old range.
- [ ] GREEN implement strict public adapter and verify provider tests/whole Python suite; commit.

### Task 2: Source-aware radar
Files app/crypto/{catalog,radar,storage}.py, app/crypto_radar.py, workflow, tests/test_crypto_{radar,storage,cli}.py.
- [ ] RED provider-isolated catalog/scan/storage tests and explicit CLI source tests.
- [ ] GREEN add explicit provider selection/default Kraken, source-specific audit/HTTP codes, workflow CRYPTO_PROVIDER=kraken. Preserve Bybit caller compatibility and all quality gates. Run whole suite; commit.

### Task 3: Atlas source change
Files atlas-web/src/lib/data.ts, src/components/crypto.tsx, fixtures/e2e, README.
- [ ] RED fixture/query/header/source tests expecting Kraken; run baseline browser regression to observe failure.
- [ ] GREEN update source filters/labels, preserve auth/expiry and stock isolation. Verify lint/unit/build/typecheck/Chromium; commit.

### Task 4: Review and delivery
- [ ] One fresh whole-change review of both repos, fix important findings with RED/GREEN evidence.
- [ ] Push feature branches/draft PRs. Run manual Kraken collection in GitHub; inspect Supabase facts, errors and repeat idempotence. Deploy Atlas and verify HTTPS login/actual Kraken data.
- [ ] Record counts, successful/failed pairs, recurrence pending merge and reusable startup instructions. No automatic merge.
