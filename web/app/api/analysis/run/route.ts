import { NextResponse } from "next/server";
import { hasAdministrativeSession } from "@/lib/auth/guard";
import { dispatchAutomation } from "@/lib/github/dispatch";
import { isSameOrigin } from "@/lib/security/origin";
export async function POST(request: Request) { if (!isSameOrigin(request)) return NextResponse.json({ error: "Origem da solicitação inválida." }, { status: 403 }); if (!(await hasAdministrativeSession())) return NextResponse.json({ error: "Não autorizado." }, { status: 401 }); try { await dispatchAutomation(); return NextResponse.json({ accepted: true }, { status: 202 }); } catch (error) { const code = error instanceof Error ? error.message : "GITHUB_UNAVAILABLE"; const status = code === "GITHUB_401" ? 401 : code === "GITHUB_403" ? 403 : code === "GITHUB_404" ? 404 : code === "GITHUB_422" ? 422 : 502; return NextResponse.json({ error: "Não foi possível solicitar a automação." }, { status }); } }
