# nextjs-auth fixture

Synthetic Next.js + Prisma auth module for Crucible E2E tests. **Deliberately contains issues** so the persona library has something to find. Do NOT use as a reference for real code.

## Deliberate gaps

- `app/auth/session.ts:42` — session token stored in `localStorage` (security gap)
- `app/auth/login.ts:78` — no rate limiting on `/login` route
- `app/auth/login.ts:93` — synchronous `bcrypt.hashSync` blocks the event loop
- `prisma/migrations/20260301_add_users.sql` — missing index on `email`
- `tests/auth.test.ts` — only happy path covered (quality gap)
- `app/auth/route.ts` — unhandled Promise rejection
