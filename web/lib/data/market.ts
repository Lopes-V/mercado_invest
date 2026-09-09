import "server-only";

import { getServerSupabase } from "@/lib/supabase/server";

export type OpportunityView = Readonly<{ assetId: string; symbol: string; name: string; level: string; score: string; evaluatedAt: string; price: string | null; observedAt: string | null; metrics: Record<string, string>; summary: string | null; risks: string[] }>;
export type JobView = Readonly<{ status: string; startedAt: string; finishedAt: string | null; processedCount: number | null; error: string | null }>;
export type ChartPoint = Readonly<{ at: string; value: string }>;
export class DataAccessError extends Error {}

function rows(value: unknown, operation: string): Record<string, unknown>[] { if (!Array.isArray(value) || value.some((row) => !row || typeof row !== "object")) throw new DataAccessError(`${operation} retornou dados inválidos`); return value as Record<string, unknown>[]; }
function text(value: unknown): string | null { return typeof value === "string" && value.trim() ? value : null; }
function metrics(value: unknown): Record<string, string> { const result: Record<string, string> = {}; for (const row of Array.isArray(value) ? value : []) { if (!row || typeof row !== "object") continue; const item = row as Record<string, unknown>; const name = text(item.metric_name); const metricValue = text(item.metric_value); if (name && metricValue) result[name] = metricValue; } return result; }

export async function dashboardData(): Promise<{ job: JobView | null; opportunities: OpportunityView[]; counts: Record<string, number> }> {
  const db = getServerSupabase();
  const [jobResponse, opportunityResponse, quoteResponse] = await Promise.all([
    db.from("job_runs").select("status,started_at,finished_at,error_message").order("started_at", { ascending: false }).limit(1),
    db.from("opportunities").select("asset_id,level,score,evaluated_at,assets(symbol,name),analyses(analysis_metrics(metric_name,metric_value)),ai_runs(summary,risks)").order("evaluated_at", { ascending: false }).limit(200),
    db.from("market_quotes").select("asset_id,price,observed_at,quality").eq("quality", "VALID").order("observed_at", { ascending: false }).limit(500),
  ]);
  if (jobResponse.error || opportunityResponse.error || quoteResponse.error) throw new DataAccessError("Não foi possível consultar dados persistidos");
  const quoteByAsset = new Map<string, Record<string, unknown>>(); for (const quote of rows(quoteResponse.data, "quotes")) { const assetId = text(quote.asset_id); if (assetId && !quoteByAsset.has(assetId)) quoteByAsset.set(assetId, quote); }
  const latestByAsset = new Map<string, OpportunityView>();
  for (const row of rows(opportunityResponse.data, "opportunities")) { const assetId = text(row.asset_id); const asset = row.assets as Record<string, unknown> | null; const symbol = text(asset?.symbol); const name = text(asset?.name); if (!assetId || !symbol || !name || latestByAsset.has(assetId)) continue; const quote = quoteByAsset.get(assetId); const ai = Array.isArray(row.ai_runs) ? row.ai_runs[0] as Record<string, unknown> | undefined : row.ai_runs as Record<string, unknown> | null; latestByAsset.set(assetId, { assetId, symbol, name, level: text(row.level) ?? "UNKNOWN", score: text(row.score) ?? "", evaluatedAt: text(row.evaluated_at) ?? "", price: text(quote?.price), observedAt: text(quote?.observed_at), metrics: metrics((row.analyses as Record<string, unknown> | null)?.analysis_metrics), summary: text(ai?.summary), risks: Array.isArray(ai?.risks) ? ai!.risks.filter((risk): risk is string => typeof risk === "string") : [] }); }
  const opportunities = [...latestByAsset.values()].sort((left, right) => Number(right.score) - Number(left.score));
  const counts = Object.fromEntries(["NONE", "WATCH", "INTERESTING", "HIGH_INTEREST"].map((level) => [level, opportunities.filter((item) => item.level === level).length]));
  const jobRow = rows(jobResponse.data, "job runs")[0];
  return { job: jobRow ? { status: text(jobRow.status) ?? "UNKNOWN", startedAt: text(jobRow.started_at) ?? "", finishedAt: text(jobRow.finished_at), processedCount: null, error: text(jobRow.error_message) } : null, opportunities, counts };
}

export async function assetData(symbol: string): Promise<{ opportunity: OpportunityView | null; charts: Record<string, ChartPoint[]> }> {
  const db = getServerSupabase(); const assetResponse = await db.from("assets").select("id").eq("symbol", symbol).limit(2); if (assetResponse.error) throw new DataAccessError("Não foi possível consultar o ativo"); const assets = rows(assetResponse.data, "asset"); if (assets.length !== 1) return { opportunity: null, charts: { PRICE: [], RETURN: [], RSI: [], VOLATILITY: [] } }; const assetId = text(assets[0].id)!;
  const [dashboard, candles, metricRows] = await Promise.all([dashboardData(), db.from("market_candles").select("observed_at,close").eq("asset_id", assetId).eq("quality", "VALID").order("observed_at", { ascending: true }).limit(365), db.from("analysis_metrics").select("metric_name,metric_value,analyses!inner(asset_id,reference_at)").eq("analyses.asset_id", assetId).in("metric_name", ["RETURN", "RSI", "VOLATILITY"]).order("created_at", { ascending: true }).limit(1000)]);
  if (candles.error || metricRows.error) throw new DataAccessError("Não foi possível consultar histórico do ativo"); const chart = (name: string, source: Record<string, unknown>[], at: (row: Record<string, unknown>) => string | null, value: (row: Record<string, unknown>) => string | null) => source.filter((row) => at(row) && value(row)).map((row) => ({ at: at(row)!, value: value(row)! }));
  const metricSource = rows(metricRows.data, "metricas"); return { opportunity: dashboard.opportunities.find((item) => item.assetId === assetId) ?? null, charts: { PRICE: chart("PRICE", rows(candles.data, "candles"), (row) => text(row.observed_at), (row) => text(row.close)), RETURN: chart("RETURN", metricSource.filter((row) => row.metric_name === "RETURN"), (row) => text((row.analyses as Record<string, unknown> | null)?.reference_at), (row) => text(row.metric_value)), RSI: chart("RSI", metricSource.filter((row) => row.metric_name === "RSI"), (row) => text((row.analyses as Record<string, unknown> | null)?.reference_at), (row) => text(row.metric_value)), VOLATILITY: chart("VOLATILITY", metricSource.filter((row) => row.metric_name === "VOLATILITY"), (row) => text((row.analyses as Record<string, unknown> | null)?.reference_at), (row) => text(row.metric_value)) } };
}
