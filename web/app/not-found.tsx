import Link from "next/link";
export default function NotFound() { return <main className="grid min-h-screen place-items-center p-6"><div><h1 className="text-xl font-semibold">Página não encontrada.</h1><Link className="mt-4 inline-block text-emerald-300 underline" href="/dashboard">Ir ao painel</Link></div></main>; }
