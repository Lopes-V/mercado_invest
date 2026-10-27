# Carteira cripto útil — implementation plan

> **For agentic workers:** Use superpowers:subagent-driven-development. One implementer per task with independent review. Continue the approved wallet design and user's explicit request to exercise judgment; don't ask again for approval of the same objectives.

**Goal:** Replace the bookkeeping-first wallet with practical position tracking, contextual manual actions and a usable reallocation simulator/radar.
**Architecture:** Keep PostgreSQL ledger/UserJWT Auth intact; add pure Decimal simulation/market interpretation, a server-only public-market reader behind verified individual Auth, and focused wallet components. No new schema or provider.
**Tech Stack:** Existing Next/React/TypeScript/Zod/Decimal, Supabase REST/Auth, Node tests/Chromium.
**Spec:** ../specs/2026-10-27-actionable-wallet-design.md plus original approved virtual-wallet design.

## Global Constraints
USDT only; no realorders, fake balances/prices/fees/probabilities. All financial transports decimal strings, Decimal precision80, HALF_UP18 derived money, floor18 quantities. Ledger unchanged and userJWT only. Authenticated server reader can use servicekey solely for fixed global market query, never private/user/financial tables. Quotes Kraken, VALID, nonfuture, <=120s; analysis-v2 latestclosed15m/1h only. Missing data explicitly unavailable. Preserve identity isolation, retry keys/payload through transient failures, privacy and legacy direct routes. No new SDK/dependency, SQL migration, password change or auto merge.

## Review Focus
- Ambiguous write + modal close/reopen + failedread preserves samepayload/key; no rekey until confirmed success or explicit safe new draft.
- Expired/future quotes never prepare a swap; both fees mandatory for net results, no default0.
- Sell100% doesn't exceed heldquantity or round up; huge/small Decimal inputs don't overflow silently.
- Unknown/revoked identity cannot trigger service reads; only fixed public-market assets/children, no arbitrary table/ID injection.
- Older/missing/open/duplicate candles don't become current evidence or connect misleading chart segments; optional research failure leaves ledger usable.

### Task1 Pure tools
Files frontend src/lib/wallet-tools.ts, tests/wallet-tools.test.ts.
Exports: `SimulationInput`, `SimulationResult`, `simulateReallocation(input)`, `quantityForPercent(heldQuantity,percent)`; `ResearchAsset`, `WalletResearch`, `researchAnalysis(asset,interval,quote,now,receivedAt)`, `researchCandles(asset,receivedAt)`.
SimulationInput: heldQuantity,costBasis,percent,sourcePrice,targetPrice:string; sellFee,buyFee,sourceScenarioPct,targetScenarioPct:string|null. Result: status ready/fees-required/invalid; reason:string|null; sourceQuantity,grossProceeds,costBasisSold:string|null; totalFees,netProceeds,targetQuantity,targetCost,cashRemainder,estimatedRealizedPnl,keepScenarioValue,swapScenarioValue,scenarioDifference:string|null. Percent >0<=100, fees>=0, positiveprices/quantity, scenarios >=-100 withfinite boundednumeric; no monetaryNumber. ResearchAsset {id,symbol,name,analyses:CryptoAnalysis[],candles:Candle[]}; WalletResearch {fetchedAt:string,assets:ResearchAsset[],error:string|null}. Research analysis returns `{analysis:CryptoAnalysis|null,direction:'up'|'down'|'mixed'|'unavailable',reason:string|null,metrics:Record<string,string>}`. Require full core metrics CLOSE/RETURN/MOMENTUM_PCT/EMA20/EMA50/RSI/VOLATILITY/ATR/MAX_DRAWDOWN/TREND_DIRECTION. Latest reference, no older favorable fallback. Rule reference+interval<=receivedAt, created in[reference+interval,receivedAt], age<=2interval+120s. researchCandles returns closed valid positive finite kraken rows ascending; retains gaps via timestamps, no padding.
- [ ] RED exactscenario example: held2,basis200,percent50,source120,target50,sellfee1,buyfee1 =>source1,gross120,basis100,net119,target2.36,targetcost119,cash0,realized19,totalfees2; scenarios source+10,target+20 =>keep132,swap141.6,difference9.6. Missingfees=>no net/target; zero explicitallowed; sell100%floor notoverspend; invalid/overflow/scenario<-100 denied. Metric/candle stale/future/provider/missing coverage.
- [ ] GREEN puremodule with no server/side effects, allmoneystrings; run npmtest, commit/report.

### Task2 Server research (root integration, independent of Task1 UI)
Files frontend src/lib/wallet-research.ts, tests/wallet-research.test.ts. `getWalletResearch(token:string,assetIds:string[]):Promise<WalletResearch>`. VerifyAccess before anyadminrequest. Empty/invalid UUIDset bounded<=10 returns honestempty/error. Fixedassets query activeCRYPTO/KRAKEN/USDT and IDs fromRPC, max10assets; nested latestanalysis-v2 15m/1h withmetrics::text, last96closed15mkrakencandles close::text. No financial/private reads, no arbitrary table parameters. Timeout10s,no-store; credentialsserveronly. MarketquotesstillRPC. Rawcontractvalidated, provider/currency/catalog enforced; optionallyunavailableerrorneverthrowwalletreadfailure.
- [ ] RED deniedinvalidJWT causeszero privilegedrequests; exactfixedquery/ids/numericstrings; provider/catalog/error contract.
- [ ] GREEN reader/unitcases. Root wires page/screen props after Task3 interface and verifiesoptional failures.

### Task3 Useful UI
Files frontend newwallet components, virtual-wallet.tsx, virtual-wallet-screen.tsx, virtual/page.tsx integrationownedroot, globals.css, atlas.tsx/settings navigation, tests/e2e/{setup,connected,virtual}.spec.ts and mock-virtual-supabase.cjs.
Consumes Task1tools + WalletResearch through optional `research` prop in VirtualWallet and WalletScreenSnapshot (root adds page fetching). Existing market/state/RPC/actions remain exact.
- [ ] RED new usecases singleprimaryCarteira; compactsummary+positions; onlyopenforms onactions; selectedasset/sell25/50/100; explicitcurrentquote autofill; accounting/history detailscollapsed; preserve existing retries/session/privacy/degradedstates. Tests meaningfulaction workflows, no removed invariants.
- [ ] GREEN splitfocusedcomponents. Modalclosing doesn't unmount unconfirmeddraft. Emptyfirstwallet simplecreate; otherwalletcreationsecondary, multiwalletselectorifneeded. Keeplegacy /carteira directoperator route +secondarysettingslink. Gain/cashflows remain distinct, no fakeglobalreturn. Showamounts/assetnames/dates inhistory, hideUUID/code underdetails. Addread-only simulator withfees/hypotheses/liveexpiry+PrepareSwap requiringmanualconfirm. Optionalresearch showscontext/closedhistory, never recommendations/probability or fakefallback.
- [ ] Verify lint, npmtest, build, types, allChromium adapted+new. Screenshots desktop/mobile, commit/report.

### Task4 Review/deploy (root)
- [ ] Scopedtools+UI/integrationreview; fixesfinancial/privacy/rate boundaries beforeprod.
- [ ] Verifyallchecks; deploysameVercelproject preserving privateenv; publicconta/walletguard, legacyviews/secretabsence, no realuser/wallet writes for test.
- [ ] PushfeaturePRs no merge; documentactualusefulchanges and remaininglimits; update environmentstartinstructions exactheads/status.
