import "server-only";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { readServerEnvironment } from "@/lib/env";
import { sessionCookieName } from "@/lib/auth/constants";
import { readSession } from "@/lib/auth/session";

export async function hasAdministrativeSession(): Promise<boolean> {
  const environment = readServerEnvironment();
  if (!environment.sessionSecret) return false;
  const token = (await cookies()).get(sessionCookieName)?.value;
  return Boolean(token && (await readSession(token, environment.sessionSecret)));
}

export async function requireAdministrativeSession(): Promise<void> {
  if (!(await hasAdministrativeSession())) redirect("/login");
}
