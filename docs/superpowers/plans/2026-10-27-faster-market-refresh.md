# Faster Market Refresh Implementation Plan

User requests shorter cooldown for crypto and companies. Implement directly in existing isolated checkouts; no new worktree or automatic merge.

**Goal:** Atlas polls persisted data every30s; crypto collects every60s within a bounded GitHub job; independent quote-only stocks round every5min, down from30min. GitHub cron minimum5min and dispatch delays remain explicit; no guarantee of continuous hosting.
**Architecture:** bounded monotonic collector around existing CLI/scheduler; dedicated stock job with production/shadow/AI/Telegram disabled; read-only authenticated router.refresh polling. Existing formulas, freshness120s, schedules for stock analysis/alerts and provider identities unchanged.

## Review focus
No rapid catch-up requests or overlapping loops; slow/failing source does not spin; quote-only settings cannot enable orders/alerts; refresh preserves filters/privacy/auth; hidden/offline tabs and pending requests do not multiply queries; old trades never become fresh by changing validity thresholds.

### Task1 Backend
- [x] RED fake-clock tests for60s interval, deadline, long-call skip, exception recovery/aggregate failure and mininterval; settings tests ensuring only quote jobs can run.
- [x] GREEN app/market_refresh.py wrapper for crypto duration270s and stock once with300s slots, existing clients/jobs; no schema changes.
- [x] Workflow cron5min retained; crypto repeats60s, separate stocks job with existing provider secrets, no Telegram/Gemini env; only quote collection, analysis workflow unchanged.
- [x] Full Python suite; manual feature workflow verifies timestamps and records, report blocked provider access explicitly.
### Task2 Atlas
- [x] RED browser request test proves30s polling, filter/privacy preservation, offline/hidden pause and resume; TTL test offline to isolate expiry independently from polling.
- [x] GREEN authenticated connected-panel refresh, no direct browser source/secret access, preserve manualbutton and pending guard.
- [x] Lint/unit/build/typecheck/fullChromium.
### Task3 Delivery
- [x] One fresh review, regression fixes for important findings, draftPRs, existing Vercel deployment and HTTPS validation; no automatic merge.
- [x] Document actual intervals, source/market/API restrictions and GitHub scheduler gaps; save current setup instructions.

## Verification and delivery

588 backend tests passed/21 integrations skipped. Atlas13unit and15Chromium passed, plus lint/build/typecheck. Run40500365669 completed SUCCESS: crypto rounds at12:00:26 and12:01:26 UTC (60seconds), allthreepairsREADY; BRAPI/TwelveDataquotejobsSUCCEEDED. Stock providers returned the same observed price/reference when there was no new business data; no fabricated time or freshness.

Production dpl_Cz2w7RTqZdaerX5MR16vxgLUvjeC READY. HTTPS login, source labels, stock rows and30s automaticrefresh marker validated; market prices remain unavailable after expiry until new collection. Source freshness was not relaxed.

DraftPRs backend#6/Atlas#3. No automaticmerge; backendfrequencies require merge. Review found no Critical/Important issues. Deferredminors: recheckdeadline afteroversleep/suspension; holdbrowserrefreshpendingacrossanother tick toexplicitlytestnooverlap. Independentreview declinedlivequota/schedulerpunctuality, verified only observedrunanddocumentedlimits.

Newuploadedwalletrequest is separate; userselectedUSDT. Designpreparedandbuilderchecked, notimplementedandnomigrationsapplied pendingdesignapproval.
