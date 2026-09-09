import { requireAdministrativeSession } from "@/lib/auth/guard";
import { dashboardData } from "@/lib/data/market";

export const dynamic = "force-dynamic";

export default async function SummaryPage() {
  await requireAdministrativeSession();
  const { opportunities } = await dashboardData();
  const relevant = opportunities.filter((item) => item.level === "INTERESTING" || item.level === "HIGH_INTEREST");
  return <main className="mx-auto max-w-5xl p-6"><p className="text-emerald-300">RESUMO DIÁRIO</p><h1 className="mt-2 text-3xl font-semibold">Fechamento persistido</h1><p className="mt-3 text-slate-300">{opportunities.length} ativos analisados nesta leitura.</p>{relevant.length ? <div className="mt-6 space-y-4">{relevant.map((item) => <article key={item.assetId} className="rounded-xl border border-white/10 p-4"><h2 className="font-semibold">{item.symbol} · {item.level} · score {item.score}</h2><p className="mt-2 text-sm text-slate-300">Preço {item.price ?? "indisponível"}; retorno {item.metrics.RETURN ?? "indisponível"}; RSI {item.metrics.RSI ?? "indisponível"}; volatilidade {item.metrics.VOLATILITY ?? "indisponível"}.</p>{item.summary ? <p className="mt-3 whitespace-pre-wrap text-sm text-slate-300">{item.summary}</p> : null}{item.risks.length ? <p className="mt-3 text-sm text-amber-200">Riscos: {item.risks.join(", ")}</p> : null}</article>)}</div> : <p className="mt-6 text-slate-400">Nenhuma oportunidade relevante persistida.</p>}</main>;
}
