"use client";
export default function ErrorPage({ reset }: { error: Error; reset: () => void }) { return <main className="grid min-h-screen place-items-center p-6"><div><h1 className="text-xl font-semibold">Não foi possível carregar esta página.</h1><button className="mt-4 rounded bg-white/10 px-3 py-2" onClick={reset}>Tentar novamente</button></div></main>; }
