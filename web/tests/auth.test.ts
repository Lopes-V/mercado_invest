import { hash } from "@node-rs/argon2";
import { describe, expect, it } from "vitest";

import { createSession, readSession, verifyAdminPassword } from "@/lib/auth/session";

const secret = "0123456789abcdef0123456789abcdef";

describe("administrative authentication", () => {
  it("verifies only the password represented by an Argon2id hash", async () => {
    const passwordHash = await hash("correct-horse-battery-staple");
    expect(passwordHash.startsWith("$argon2id$")).toBe(true);

    await expect(verifyAdminPassword("correct-horse-battery-staple", passwordHash)).resolves.toBe(true);
    await expect(verifyAdminPassword("incorrect", passwordHash)).resolves.toBe(false);
  });

  it("rejects a malformed configured password hash", async () => {
    await expect(verifyAdminPassword("password", "not-an-argon2-hash")).rejects.toThrow(
      "WEB_ADMIN_PASSWORD_HASH deve usar Argon2id",
    );
  });

  it("reads a valid session and rejects it after its twelve-hour expiry", async () => {
    const issuedAt = new Date("2026-09-09T12:00:00.000Z");
    const token = await createSession(secret, issuedAt);

    await expect(readSession(token, secret, new Date("2026-09-09T23:59:59.000Z"))).resolves.toEqual({ authenticated: true });
    await expect(readSession(token, secret, new Date("2026-09-10T00:00:01.000Z"))).resolves.toBeNull();
  });
});
