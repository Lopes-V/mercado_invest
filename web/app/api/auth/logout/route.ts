import { NextResponse } from "next/server";

import { sessionCookieName } from "@/lib/auth/constants";
import { isSameOrigin } from "@/lib/security/origin";

export async function POST(request: Request): Promise<NextResponse> {
  if (!isSameOrigin(request)) return NextResponse.json({ error: "Origem da solicitação inválida." }, { status: 403 });
  const response = NextResponse.json({ ok: true });
  response.cookies.set(sessionCookieName, "", { httpOnly: true, maxAge: 0, path: "/", sameSite: "strict", secure: process.env.NODE_ENV === "production" });
  return response;
}
