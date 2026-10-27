# Bybit Radar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Tasks use TDD, existing isolated checkouts and independent file ownership.

**Goal:** Collect and explain short-term Bybit spot crypto conditions in the authenticated Atlas.
**Architecture:** Python public adapter → versioned technical analysis → existing Supabase facts → Next.js server reads. Separate five-minute workflow; existing stock automation and frozen policies remain unchanged.
**Tech Stack:** Python 3.12, httpx, Decimal, Supabase, Next.js, Zod, Playwright.
**Spec:** ../specs/2026-10-26-bybit-short-term-radar-design.md (approved by user).

## Global Constraints
- No new worktree; use current /workspace checkouts. No migrations or automatic merge.
- Public Bybit category=spot, initial BTCUSDT/ETHUSDT/SOLUSDT, quote currency USDT, 15m/1h.
- Preserve analysis-v1 and all stock policy/automation behavior.
- Never invent prices, volume, missing history, performance probabilities or fees. All facts have timestamps. Only closed valid candles enter analysis.
- No order APIs or private exchange credentials. TLS verification and timeouts remain enabled.
- Secrets stay in ignored local configuration/server environments.

## Review Focus
- Conflicting overlapping history pages and open last candle → reject conflict; filter open candle.
- Missing volume or zero denominator → explicit missing metrics, never synthetic volume/returns.
- Sparse or stale persisted data → generic unavailable UI, no current-looking trend.
- Same asset but wrong provider/interval → reject analysis input and isolate catalog.
- Recurring workflow not deployed to default branch → never claim active recurrence.

### Task 1: Public Bybit provider
**Files:** app/market_data/providers/bybit.py, tests/test_bybit_provider.py.
**Interfaces:** `BybitProvider(http_client, *, clock=UTC_now)` implements MarketDataProvider. `get_liquidity(symbol: str) -> BybitLiquidity` with symbol, bid, ask, volume24h, turnover24h, timestamp and optional `spread_bps` property. `get_quote` obtains true recent-trade time and validates instrument identity/currency. `get_assets` uses spot instruments. Use existing ProviderHttpClient/normalization/errors.
- [x] RED: tests for exact spot query, recent-trade timestamps, decimal parsing, retCode/category/symbol mismatch, reversed/paginated history, identical vs conflicting duplicates, open candle, empty/malformed responses.
- [x] GREEN: implement adapter with bounded pagination and explicit range, only USDT Trading spot instruments. Cache validated instrument metadata per provider lifetime.
- [x] Verify: `python -m pytest -q tests/test_bybit_provider.py` → all tests pass.

### Task 2: Versioned technical engine
**Files:** app/analysis/crypto.py, tests/test_crypto_analysis.py.
**Interfaces:** `CryptoAnalysisEngine.algorithm_version='analysis-v2'`; `.analyze(candles, *, period=14) -> AnalysisResult` using existing result/metric dataclasses. Separate class; no modification of v1 defaults.
Metrics: CLOSE, RETURN (ratio over period), MOMENTUM_PCT (100*RETURN), EMA20/EMA50, RSI (Wilder seed then smoothing), VOLATILITY (population stddev last period returns), ATR (Wilder TR), MAX_DRAWDOWN, AVERAGE_VOLUME (previous period candles excluding current), RELATIVE_VOLUME (current/baseline), TREND_DIRECTION (+1 when close>EMA20>EMA50, -1 when close<EMA20<EMA50, otherwise 0=mixed). Omit unavailable volume metrics; never substitute zero. Minimum history max(51,period+1). period integer 2..200. Reject mixed asset/provider/symbol/interval, duplicate/gapped timestamps, non-VALID inputs and zero/non-positive OHLC. Only 15m/1h supported in this crypto engine. Decimal local precision 38+.
- [x] RED: exact published Wilder vector, EMA seed/update, period-local volatility, missing volume, no gaps/mixed data, warm-up and period boundaries.
- [x] GREEN: implement independent pure engine and document formulas.
- [x] Verify: `python -m pytest -q tests/test_crypto_analysis.py` and legacy suite → pass.

### Task 3: Catalog, report service and collection workflow
**Files:** app/crypto/{__init__,catalog,radar}.py; app/crypto_radar.py; tests/test_crypto_radar.py; .github/workflows/crypto-radar.yml; docs/17-crypto-radar.md; TASKS.md.
**Consumes:** Tasks 1/2 interfaces. Produces existing market_quotes, market_candles, analyses and analysis_metrics with v2. Reports contain per-symbol statuses/reasons and separate liquidity snapshot timestamp, no fee assumptions.
- [x] RED: fake provider/repositories verify plan-only catalog does not write, apply idempotence, only crypto identity, freshness and gap failures, partial report, and persistence isolation.
- [x] GREEN: catalog uses existing repositories, CRYPTO market, BYBIT exchange UTC, USDT currency and CRYPTO assets. Default bootstrap is dry-run; --apply creates missing records only.
- [x] Service fetches 200 closed candles per interval, quote freshness <=120s, latest candle close <=one interval old, future tolerance 2 minutes. Validate before any analysis write. Batch compare/read existing candles and insert missing only, reject conflicting immutable facts. Reuse quote idempotence. Preserve analysis-v1.
- [x] CLI `python -m app.crypto_radar --bootstrap [--apply]`, `--symbols`, `--persist`, `--output` (optional report file). CLI loads existing backend environment, never sibling credentials implicitly. Output JSON decimal strings, UTC. Record executions in job_runs with sanitized errors; nonzero exit for failures. No order or Telegram calls.
- [x] Dedicated workflow cron */5, manual dispatch, concurrency single runner, existing Supabase secret names, bootstrap apply + persist, reports as artifacts; old workflow unchanged.
- [x] Verify whole Python suite; public Bybit smoke if network allows; dry-run before approved catalog writes. Any external blocker is recorded, never replaced by fixtures.

### Task 4: Atlas crypto section
**Files:** atlas-web/src/lib/{contracts,data}.ts, src/components/{atlas,crypto}.tsx, workspace route, styles, tests/mock-supabase.cjs and tests/e2e, README.
**Consumes:** versioned analysis metrics above. Server-only authenticated query for Bybit catalog assets and latest analyses per interval, no Python formula duplication. Existing tables only. Quote <=120s and last closed candle start within 2*interval+120s. Stale/non-VALID/future/missing data shows unavailable. TREND_DIRECTION is only decoded to labels. Decimal monetary display supports USDT. No liquid spread/fees presented as persisted when unavailable.
- [x] RED: browser fixtures cover crypto quote, v2 analyses, 15m/1h metrics, generic unavailable and stale/future states, auth and privacy. No production fixture mode.
- [x] GREEN: Cripto navigation/route/card layout following DESIGN.md. Timestamp and interval explicit. Stocks and other routes unchanged.
- [x] Verify lint, unit tests, build, typecheck and full Playwright suite.

### Task 5: Review and delivery
- [x] Independent review adapter/engine/service/UI, fix important findings with regression tests.
- [x] Run required full suites and inspect diff/secrets metadata.
- [ ] Deploy current Atlas to existing Vercel project and validate HTTPS login/crypto.
- [ ] Backend changes on a feature branch/draft PR if Git access permits. No automatic merge. Confirm whether recurring workflow is actually active separately.
- [ ] Save reusable startup instructions and report blockers precisely.

## Verification evidence (2026-10-27)

Backend: `python -m pytest -q` → 541 passed, 21 opt-in integrations skipped. Atlas: lint, production build and typecheck passed; 13 unit and 14 Chromium browser tests passed. Independent provider/engine reviews passed. Integration findings on quote expiry and stock-query isolation were fixed with regressions; page-open expiry and initially future-dated records are covered. Exact crypto Supabase query returned HTTP 200 with zero rows. Public Bybit bootstrap returned HTTP 403 regional restriction, so live collection/persistence and recurrence are not validated.
