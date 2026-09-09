import { NextResponse } from "next/server";

import { sessionCookieName } from "@/lib/auth/constants";
import { createSession, verifyAdminPassword } from "@/lib/auth/session";
import { readServerEnvironment } from "@/lib/env";
import { isSameOrigin } from "@/lib/security/origin";

const attempts = new Map<string, { count: number; resetAt: number }>();
const maximumAttempts = 5;
const attemptWindowMilliseconds = 15 * 60 * 1000;

function requestKey(request: Request): string {
  return request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() || "unknown";
}

function rejected(message: string, status: number): NextResponse {
  return NextResponse.json({ error: message }, { status });
}

export async function POST(request: Request): Promise<NextResponse> {
  if (!isSameOrigin(request)) return rejected("Origem da solicitação inválida.", 403);
  const key = requestKey(request);
  const now = Date.now();
  const current = attempts.get(key);
  if (current && current.resetAt > now && current.count >= maximumAttempts) {
    return rejected("Não foi possível autenticar.", 429);
  }

  const body: unknown = await request.json().catch(() => null);
  const password = typeof (body as { password?: unknown } | null)?.password === "string"
    ? (body as { password: string }).password
    : "";
  const environment = readServerEnvironment();
  if (!environment.adminPasswordHash || !environment.sessionSecret) {
    return rejected("Autenticação indisponível.", 503);
  }
  const valid = await verifyAdminPassword(password, environment.adminPasswordHash);
  if (!valid) {
    attempts.set(key, { count: (current?.resetAt ?? 0) > now ? (current?.count ?? 0) + 1 : 1, resetAt: now + attemptWindowMilliseconds });
    return rejected("Não foi possível autenticar.", 401);
  }
  attempts.delete(key);
  const response = NextResponse.json({ ok: true });
  response.cookies.set(sessionCookieName, await createSession(environment.sessionSecret), {
    httpOnly: true,
    maxAge: 12 * 60 * 60,
    path: "/",
    sameSite: "strict",
    secure: process.env.NODE_ENV === "production",
  });
  return response;
}
