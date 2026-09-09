import { requireAdministrativeSession } from "@/lib/auth/guard";
import { SettingsForm } from "./settings-form";
export const dynamic = "force-dynamic";
export default async function SettingsPage() { await requireAdministrativeSession(); return <main className="mx-auto max-w-4xl p-6"><p className="text-emerald-300">CONFIGURAÇÕES</p><h1 className="mt-2 text-3xl font-semibold">Resumo diário</h1><p className="mt-3 text-slate-300">O horário é persistido no banco e não altera variáveis do GitHub.</p><SettingsForm /></main>; }
