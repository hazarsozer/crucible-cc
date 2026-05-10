/**
 * Auth tests — DELIBERATELY THIN. Only happy path covered.
 * The Quality Engineer persona should flag this.
 */

import { describe, it, expect, vi } from "vitest";
import { login } from "../app/auth/login";

vi.mock("@prisma/client", () => ({
  PrismaClient: vi.fn(() => ({
    user: {
      findUnique: vi.fn().mockResolvedValue({
        id: "user-1",
        email: "alice@example.com",
        password_hash: "$2b$12$abcdefghijklmnopqrstuv",
      }),
    },
    session: {
      create: vi.fn().mockResolvedValue({
        id: "sess-1",
        user_id: "user-1",
        token: "tok",
        expires_at: new Date(Date.now() + 1000 * 60 * 60 * 24),
      }),
    },
  })),
}));

vi.mock("bcrypt", () => ({
  default: {
    compare: vi.fn().mockResolvedValue(true),
    hashSync: vi.fn().mockReturnValue("$2b$12$xxx"),
  },
}));

describe("login (happy path only)", () => {
  it("returns ok=true for valid credentials", async () => {
    const result = await login({ email: "alice@example.com", password: "correctpass" });
    expect(result.ok).toBe(true);
    expect(result.userId).toBe("user-1");
  });
});
