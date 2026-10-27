# Faster Market Refresh Implementation Plan

User requests shorter cooldown for crypto and companies. Implement directly in existing isolated checkouts; no new worktree or automatic merge.

**Goal:** Atlas polls persisted data every30s; crypto collects every60s within a bounded GitHub job; independent quote-only stocks round every5min, down from30min. GitHub cron minimum5min and dispatch delays remain explicit; no guarantee of continuous hosting.
**Architecture:** bounded monotonic collector around existing CLI/scheduler; dedicated stock job with production/shadow/AI/Telegram disabled; read-only authenticated router.refresh polling. Existing formulas, freshness120s, schedules for stock analysis/alerts and provider identities unchanged.

## Review focus
No rapid catch-up requests or overlapping loops; slow/failing source does not spin; quote-only settings cannot enable orders/alerts; refresh preserves filters/privacy/auth; hidden/offline tabs and pending requests do not multiply queries; old trades never become fresh by changing validity thresholds.

### Task1 Backend
- [ ] RED fake-clock tests for60s interval, deadline, long-call skip, exception recovery/aggregate failure and mininterval; settings tests ensuring only quote jobs can run.
- [ ] GREEN app/market_refresh.py wrapper for crypto duration270s and stock once with300s slots, existing clients/jobs; no schema changes.
- [ ] Workflow cron5min retained; crypto repeats60s, separate stocks job with existing provider secrets, no Telegram/Gemini env; only quote collection, analysis workflow unchanged.
- [ ] Full Python suite; manual feature workflow verifies timestamps and records, report blocked provider access explicitly.
### Task2 Atlas
- [ ] RED browser request test proves30s polling, filter/privacy preservation, offline/hidden pause and resume; TTL test offline to isolate expiry independently from polling.
- [ ] GREEN authenticated connected-panel refresh, no direct browser source/secret access, preserve manualbutton and pending guard.
- [ ] Lint/unit/build/typecheck/fullChromium.
### Task3 Delivery
- [ ] One fresh review, regression fixes for important findings, draftPRs, existing Vercel deployment and HTTPS validation; no automatic merge.
- [ ] Document actual intervals, source/market/API restrictions and GitHub scheduler gaps; save current setup instructions.
