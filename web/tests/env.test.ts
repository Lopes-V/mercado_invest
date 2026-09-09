import { describe, expect, it } from "vitest";

import { ServerEnvironmentError, readServerEnvironment } from "@/lib/env";

const baseEnvironment = {
  NODE_ENV: "test",
  WEB_ADMIN_PASSWORD_HASH: "$argon2id$example",
  WEB_SESSION_SECRET: "a-session-secret-with-at-least-thirty-two-bytes",
  SUPABASE_URL: "https://project.supabase.co",
  SUPABASE_SECRET_KEY: "server-only-key",
};

describe("readServerEnvironment", () => {
  it("requires administrative server values in production", () => {
    expect(() =>
      readServerEnvironment({ ...baseEnvironment, NODE_ENV: "production", WEB_SESSION_SECRET: "" }),
    ).toThrow(new ServerEnvironmentError("WEB_SESSION_SECRET é obrigatória em produção"));
  });

  it("rejects a known secret provided through a NEXT_PUBLIC_ name", () => {
    expect(() =>
      readServerEnvironment({
        ...baseEnvironment,
        NEXT_PUBLIC_SUPABASE_SECRET_KEY: "leaked",
      }),
    ).toThrow(new ServerEnvironmentError("SUPABASE_SECRET_KEY não pode usar prefixo NEXT_PUBLIC_"));
  });

  it("returns only server-side configuration", () => {
    expect(readServerEnvironment(baseEnvironment)).toMatchObject({
      adminPasswordHash: "$argon2id$example",
      sessionSecret: "a-session-secret-with-at-least-thirty-two-bytes",
      supabaseUrl: "https://project.supabase.co",
      supabaseSecretKey: "server-only-key",
    });
  });
});
