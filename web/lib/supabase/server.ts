import "server-only";
import { createClient } from "@supabase/supabase-js";
import { readServerEnvironment, ServerEnvironmentError } from "@/lib/env";

export function getServerSupabase() {
  const environment = readServerEnvironment();
  if (!environment.supabaseUrl || !environment.supabaseSecretKey) throw new ServerEnvironmentError("Supabase não está configurado no servidor");
  return createClient(environment.supabaseUrl, environment.supabaseSecretKey, { auth: { autoRefreshToken: false, persistSession: false }, global: { fetch: (input, init) => fetch(input, { ...init, signal: init?.signal ?? AbortSignal.timeout(10_000) }) } });
}
