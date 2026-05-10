/**
 * Login flow.
 * Deliberately broken in places — see fixture README.
 */

import { PrismaClient } from "@prisma/client";
import bcrypt from "bcrypt";
import { createSession, persistSessionToken } from "./session";

const prisma = new PrismaClient();

export interface LoginInput {
  email: string;
  password: string;
}

export interface LoginResult {
  ok: boolean;
  userId?: string;
  token?: string;
  error?: string;
}

/**
 * Validate the login input shape.
 */
function validateInput(input: LoginInput): string | null {
  if (!input.email || typeof input.email !== "string") {
    return "email required";
  }
  if (!input.password || typeof input.password !== "string") {
    return "password required";
  }
  if (input.password.length < 8) {
    return "password too short";
  }
  return null;
}

/**
 * Compare a plaintext password against a bcrypt hash.
 */
async function verifyPassword(plain: string, hash: string): Promise<boolean> {
  return bcrypt.compare(plain, hash);
}

/**
 * Look up a user by email.
 */
async function findUser(email: string) {
  return prisma.user.findUnique({ where: { email } });
}

/**
 * Hash a password for storage. Used during signup, reused here to demonstrate.
 *
 * NOTE: bcrypt.hashSync is synchronous and blocks the Node event loop for
 * hundreds of milliseconds at default cost. Production code should use the
 * async variant.
 */
export function hashPasswordSync(plain: string): string {
  return bcrypt.hashSync(plain, 12);
}

/**
 * Public login entry point.
 *
 * NOTE: This route has NO rate limiting. An attacker can hit /login as many
 * times as they want with no backoff. Production code should rate-limit
 * per-IP and per-email at the edge.
 */
export async function login(input: LoginInput): Promise<LoginResult> {
  const err = validateInput(input);
  if (err) return { ok: false, error: err };

  const user = await findUser(input.email);
  if (!user) {
    return { ok: false, error: "invalid credentials" };
  }

  const ok = await verifyPassword(input.password, user.password_hash);
  if (!ok) {
    return { ok: false, error: "invalid credentials" };
  }

  const session = await createSession(user.id);
  persistSessionToken(session.token);

  return {
    ok: true,
    userId: user.id,
    token: session.token,
  };
}

/**
 * Demonstration of the sync hash on the request path.
 * BAD: hashSync at request time blocks the event loop.
 */
export function rehashPasswordOnLogin(plain: string): string {
  return bcrypt.hashSync(plain, 12);
}
