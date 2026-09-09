import Link from "next/link";
import { requireAdministrativeSession } from "@/lib/auth/guard";
import { dashboardData } from "@/lib/data/market";

export const dynamic = "force-dynamic";

export default async function HistoryPage() {
  await requireAdministrativeSession();
  const { opportunities } = await dashboardData();
  return <main className="mx-auto max-w-6xl p-6"><p className="text-emerald-300">HISTÓRICO</p><h1 className="mt-2 text-3xl font-semibold">Últimas oportunidades</h1><p className="mt-3 text-slate-400">A visualização exibe o último registro persistido por ativo.</p><div className="mt-6 overflow-x-auto rounded-xl border border-white/10"><table className="w-full text-left text-sm"><thead className="border-b border-white/10 text-slate-400"><tr><th className="p-3">Data/hora</th><th className="p-3">Ativo</th><th className="p-3">Nível</th><th className="p-3">Score</th><th className="p-3">Retorno</th><th className="p-3">RSI</th><th className="p-3">Volatilidade</th></tr></thead><tbody>{opportunities.map((item) => <tr key={item.assetId} className="border-b border-white/5"><td className="p-3">{item.evaluatedAt ? new Date(item.evaluatedAt).toLocaleString("pt-BR") : "indisponível"}</td><td className="p-3"><Link className="text-emerald-300" href={`/ativos/${encodeURIComponent(item.symbol)}`}>{item.symbol}</Link></td><td className="p-3">{item.level}</td><td className="p-3">{item.score}</td><td className="p-3">{item.metrics.RETURN ?? "—"}</td><td className="p-3">{item.metrics.RSI ?? "—"}</td><td className="p-3">{item.metrics.VOLATILITY ?? "—"}</td></tr>)}</tbody></table>{!opportunities.length ? <p className="p-4 text-slate-400">Nenhum histórico persistido.</p> : null}</div></main>;
}
