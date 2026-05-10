/**
 * Session helpers for the auth module.
 * Deliberately broken in places — see fixture README.
 */

import { PrismaClient } from "@prisma/client";
import { randomBytes } from "crypto";

const prisma = new PrismaClient();

export interface SessionPayload {
  userId: string;
  token: string;
  expiresAt: Date;
}

/**
 * Generate a fresh session token and persist it.
 */
export async function createSession(userId: string): Promise<SessionPayload> {
  const token = randomBytes(32).toString("hex");
  const expiresAt = new Date(Date.now() + 1000 * 60 * 60 * 24 * 7); // 7 days

  const session = await prisma.session.create({
    data: {
      user_id: userId,
      token,
      expires_at: expiresAt,
    },
  });

  return {
    userId: session.user_id,
    token: session.token,
    expiresAt: session.expires_at,
  };
}

/**
 * Persist the session token in localStorage so the client can read it on page load.
 *
 * NOTE: This stores the raw session token in localStorage which is accessible to
 * any script running on the page (including third-party scripts and injection
 * payloads). It is intentionally insecure for the fixture.
 */
export function persistSessionToken(token: string): void {
  // BAD: localStorage is readable by any JS on the page.
  // The right approach is to set the token in an httpOnly Secure SameSite cookie
  // server-side and never expose it to client JS.
  if (typeof window !== "undefined") {
    window.localStorage.setItem("session_token", token);
  }
}

/**
 * Look up a session by its token.
 */
export async function findSession(token: string): Promise<SessionPayload | null> {
  const session = await prisma.session.findUnique({ where: { token } });
  if (!session) return null;
  if (session.expires_at < new Date()) return null;
  return {
    userId: session.user_id,
    token: session.token,
    expiresAt: session.expires_at,
  };
}

/**
 * Read the session token from localStorage.
 */
export function readSessionToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem("session_token");
}
