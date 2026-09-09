import "server-only";

import { verify as verifyArgon2 } from "@node-rs/argon2";
import { errors, jwtVerify, SignJWT } from "jose";

const sessionIssuer = "mercado-invest-web";
const sessionAudience = "admin";
const sessionLifetimeSeconds = 12 * 60 * 60;

function signingKey(secret: string): Uint8Array {
  return new TextEncoder().encode(secret);
}

export async function verifyAdminPassword(password: string, passwordHash: string): Promise<boolean> {
  if (!passwordHash.startsWith("$argon2id$")) {
    throw new Error("WEB_ADMIN_PASSWORD_HASH deve usar Argon2id");
  }
  return verifyArgon2(passwordHash, password);
}

export async function createSession(secret: string, issuedAt = new Date()): Promise<string> {
  const issuedAtSeconds = Math.floor(issuedAt.getTime() / 1000);
  return new SignJWT({ authenticated: true })
    .setProtectedHeader({ alg: "HS256", typ: "JWT" })
    .setIssuer(sessionIssuer)
    .setAudience(sessionAudience)
    .setIssuedAt(issuedAtSeconds)
    .setExpirationTime(issuedAtSeconds + sessionLifetimeSeconds)
    .sign(signingKey(secret));
}

export async function readSession(token: string, secret: string, currentDate = new Date()): Promise<{ authenticated: true } | null> {
  try {
    const { payload } = await jwtVerify(token, signingKey(secret), {
      audience: sessionAudience,
      currentDate,
      issuer: sessionIssuer,
    });
    return payload.authenticated === true ? { authenticated: true } : null;
  } catch (error) {
    if (error instanceof errors.JOSEError) {
      return null;
    }
    throw error;
  }
}
