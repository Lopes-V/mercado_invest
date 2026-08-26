# Opportunity, Gemini and Telegram Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the investment pipeline deterministic before Gemini, add safe operational summaries and separate Telegram recipients without enabling production.

**Architecture:** `OpportunityPreFilter` and `OpportunityService` keep financial evaluation/persistence separate from Gemini context. `TelegramMessageFormatter` receives only presentation data, while bootstrap selects an explicit production or dry-run mode and injects a sender accordingly.

**Tech Stack:** Python 3.12, Decimal, pytest, Supabase repositories, httpx Telegram/Gemini clients, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-08-26-opportunity-gemini-telegram-design.md`

## Global Constraints

- Do not modify frozen policy rows, `candidate-v1`, calibration history, GitHub Secrets/Variables, `AUTOMATION_ENABLED`, or `PRODUCTION_READY` values.
- Production only exists with both gates; simulation requires explicit simulation and dry-run settings and never performs Telegram HTTP.
- Gemini never changes opportunity score, level, evidence categories, or matched financial criteria.
- Shadow remains isolated from Gemini, Telegram, AlertService and paper trading.
- Do not introduce a database migration; stop for authorization if one becomes necessary.
- Use Decimal for financial/ranking arithmetic, explicit timestamps and injected dependencies.
- Never log credentials, authorization headers, tokens or unnecessary chat IDs.

---

## File Structure

- `app/config/settings.py`: new settings, parsers, bounded top-N validation and deprecated env rejection.
- `app/automation_config.py`: mode-aware validation and removal of runtime financial-rule parsing.
- `app/shadow_policy.py`: frozen-policy structural validation and production rejection of legacy AI rules.
- `app/opportunity/core.py`: deterministic engine/service without AI score input.
- `app/opportunity/pipeline.py`: pre-filter result and presentation-only candidate ranking.
- `app/telegram/messages.py`: Portuguese presentation dataclasses and renderers.
- `app/telegram/client.py`: no-HTTP dry-run transport.
- `app/alerts/core.py`: recipient-specific dedupe, supplied content and dry-run suppression.
- `app/jobs/investment_pipeline.py`: orchestration, counts, summary and per-recipient alerts.
- `app/bootstrap.py`: mode resolution and dependency composition.
- `.env.example`, workflow, README and relevant docs: public operation contract.
- focused pytest files: unit and integration-style regression coverage.

## Implementation Tasks

### Task 1: Configuration and explicit execution modes

**Files:**
- Modify: `app/config/settings.py`, `app/automation_config.py`
- Modify: `.env.example`, `.github/workflows/automation.yml`
- Test: `tests/test_settings.py`, `tests/test_automation_config.py`

**Interfaces:**
- Produce `parse_telegram_alert_chat_ids(raw: str | None) -> tuple[int, ...]`.
- Produce `Settings.telegram_alert_chat_ids`, `telegram_summary_enabled`, `telegram_summary_top_n`, `pipeline_simulation_enabled`, `telegram_dry_run`, and `dry_run_allow_ai`.
- Reject non-empty legacy `OPPORTUNITY_RULES_JSON` explicitly; do not parse or forward it.
- Keep `TELEGRAM_ALLOWED_USER_IDS` as a positive-ID `frozenset`; alert chat IDs preserve input order, reject zero/duplicates, and allow negative group IDs.

- [ ] Write failing parser/default/mode tests, including top-N bounds `1..10` and legacy variable rejection.
- [ ] Run `pytest tests/test_settings.py tests/test_automation_config.py -q` and verify the new tests fail.
- [ ] Implement only the parsers, fields, mode validation, and workflow/example wiring; leave both production gates false.
- [ ] Re-run the focused tests and `git diff --check`.

### Task 2: Deterministic opportunity contract and frozen-policy validation

**Files:**
- Modify: `app/opportunity/core.py`, `app/shadow_policy.py`, `app/automation_config.py`
- Test: `tests/test_decision_engines.py`, `tests/test_shadow_runtime.py`, `tests/test_automation_config.py`

**Interfaces:**
- `OpportunityEngine.assess` has no AI scoring input; `OpportunityService.record(...)` persists a previously calculated `OpportunityAssessment` with nullable `ai_run_id`.
- Add an explicit production-policy validator that rejects `EvidenceCategory.AI_CONTEXT` with a legacy-policy error.

- [ ] Add tests proving the same metrics produce identical score/level/evidence regardless of former AI-positive input and that AI_CONTEXT policy loading fails clearly for production.
- [ ] Run focused tests and verify failure before implementation.
- [ ] Remove the AI score/category branch and update all call sites; preserve `candidate-v1` data and existing frozen status checks.
- [ ] Run opportunity, shadow, calibration, and policy-lifecycle tests.

### Task 3: Pre-filter and presentation-only ranking

**Files:**
- Create: `app/opportunity/pipeline.py`
- Test: `tests/test_opportunity_pipeline.py`

**Interfaces:**
- `PreFilteredOpportunity` contains the deterministic assessment, metrics, matched criteria, symbol, and `presentation_rank`.
- `OpportunityPreFilter.assess(...) -> PreFilteredOpportunity` delegates scoring to `OpportunityEngine`.
- Ranking orders by financial score, evidence count, normalized threshold proximity where defined, then symbol; ranking never feeds persistence or level calculation.

- [ ] Add tests for NONE/WATCH/candidate ranking, deterministic ties, zero/invalid threshold proximity, and no score mutation.
- [ ] Run `pytest tests/test_opportunity_pipeline.py -q` and observe failure.
- [ ] Implement the thin delegation and Decimal-only presentation ranking.
- [ ] Run the focused test and existing opportunity tests.

### Task 4: Portuguese message formatting and dry-run transport

**Files:**
- Create: `app/telegram/messages.py`
- Modify: `app/telegram/client.py`, `app/alerts/core.py`
- Test: `tests/test_telegram_messages.py`, `tests/test_telegram_client.py`, `tests/test_decision_engines.py`

**Interfaces:**
- `TelegramMessageFormatter.render_summary(summary: PipelineSummary) -> str`.
- `TelegramMessageFormatter.render_opportunity_alert(content: OpportunityAlertContent) -> str`.
- Formatter accepts prepared values only and omits unavailable metrics without calculations or policy decisions.
- `TelegramClient(..., dry_run=True)` records rendered messages and never calls HTTP.
- Alert dedupe key is `<asset>:<opportunity>:<recipient>:<evaluated_at UTC>`; dry-run renders then persists `SUPPRESSED` with `dry_run`.

- [ ] Add tests for Portuguese real values, missing metrics, no invented fields, multiple-recipient dedupe, and dry-run HTTP isolation.
- [ ] Run the focused tests and observe failure.
- [ ] Implement formatter/client/alert changes with no financial rules in the formatter.
- [ ] Re-run Telegram and alert tests, including existing failure tests.

### Task 5: Pipeline orchestration, summary, and observability

**Files:**
- Modify: `app/jobs/investment_pipeline.py`
- Modify: `app/bootstrap.py`
- Test: `tests/test_automated_pipeline.py`, `tests/test_shadow_runtime.py`

**Interfaces:**
- Pipeline executes quality and analysis first, calls pre-filter once, calls AI only for INTERESTING/HIGH_INTEREST (and optional WATCH override), and records NONE/WATCH with `ai_run_id=None`.
- Summary aggregates considered/succeeded/quality-blocked/niveau counts, top-N candidates, render/send counters, and AI avoided/effective counts.
- Production mode requires both gates; simulation is explicit and never changes gate values. Shadow composition remains untouched by production dependencies.

- [ ] Add failing tests for all pre-filter branches, quality blocking, summary counts/top-N, AI dry-run opt-in, shadow isolation, and production gate behavior.
- [ ] Run focused tests and observe failure.
- [ ] Implement orchestration using injected pre-filter, formatter, senders, and recipient tuple; log aggregate safe counters only.
- [ ] Run pipeline, shadow, bootstrap, and full existing job tests.

### Task 6: Documentation and contract regression coverage

**Files:**
- Modify: `README.md`, `docs/01-architecture.md`, `docs/03-telegram-contract.md`, `docs/06-ai-engine.md`, `docs/07-alert-engine.md`, `docs/08-logging.md`, `docs/10-testing.md`, `docs/11-deployment.md`, `docs/12-opportunity-calibration.md`
- Test: relevant existing tests and documentation/config smoke checks.

- [ ] Document the exact production/simulation/shadow lifecycles, WATCH semantics, recipients separation, dry-run commands, and legacy policy rejection.
- [ ] Verify docs contain no real tokens/IDs and no invalid threshold policy.
- [ ] Run the complete test suite and static checks.

### Task 7: Final verification and handoff

**Files:**
- Inspect: all changed files, `.env`, GitHub workflow, frozen-policy migration/tests.

- [ ] Run focused tests, then `python -m pytest -q` and available lint/type checks.
- [ ] Run `python -m compileall -q app tests` and `git diff --check`.
- [ ] Search changed files for secrets and verify `AUTOMATION_ENABLED=false`, `PRODUCTION_READY=false` in examples/workflow defaults.
- [ ] Verify no migration changed/created, no `candidate-v1` rule changed, shadow has no Gemini/Telegram/AlertService dependency, and dry-run has no Telegram HTTP.
- [ ] Commit by responsibility on the feature branch; do not merge automatically. Push/PR only if the remote operation is available and safe.
