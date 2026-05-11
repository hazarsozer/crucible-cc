# Crucible Review — full project — nextjs-auth fixture, all source files

_Review ID: 2026-05-11-1717-full-project-auth · Generated: 2026-05-11T17:32:00Z · Project: web-app_

## Final Verdict

**Score:** 2/10
**Verdict:** Blocked

Both leadership personas returned `block` with a score of 2, and the architect's synthesis traces every Stage 2 critical finding back to three structural ADRs that need to be revisited before any line-level fix lands. Four `critical` findings are on the merge path: the module-scope Prisma + native bcrypt foreclose the stated Edge runtime target (lead-senior-architect); `bcrypt.hashSync` at cost 12 makes the sub-200ms p95 SLO mathematically unachievable (team-performance-reviewer); `localStorage` session storage plus the raw token in the JSON body yields 7-day account takeover on any same-origin XSS (team-security-reviewer); and the auth flow ships with zero failure-path tests (peer-quality-engineer). The PM grades aim alignment 2/10 with all four stated success criteria regressed.

## Executive Summary

This is a full-project review of the Next.js + Prisma password auth rewrite (login, session handling, the `/auth` route, and supporting tests on Postgres/Neon, targeting Vercel Edge). The user's aims are explicit: secure (no client-readable tokens, no timing attacks, rate limited), fast (sub-200ms p95), graceful failure, and regression-protecting test coverage. OAuth, 2FA, and account recovery are explicit non-goals.

There is real substance to build on. The Prisma schema captures the right entities and the SQL peer's findings are corrective rather than structural. The architect's structural critique is precise enough to act on: three ADRs (runtime choice, session-storage ownership, per-handler cross-cutting concerns) explain why the Stage 2 findings cluster the way they do, giving the team a clean sequencing path rather than a scattered list.

The work cannot ship in its current form. Four of the seven personas returned `block` and both leadership reviewers graded the run at 2/10; the PM reports all four stated success criteria regressed. The decisive findings are not polish: `bcrypt.hashSync` at cost 12 alone makes the 200ms SLO unreachable, `localStorage` plus token-in-response-body is a same-origin XSS to 7-day account takeover, the route handler drops `login()`'s promise without `await`, and failure-path tests are absent. The PM's three-PR sequencing (security/shape, then runtime/perf, then tests) is the right shape for the rework; the 200ms SLO with bcrypt cost 12 may also need an aims-document revision before round two.

## What's Good

- Prisma schema captures the right entities; `peer-sql-reviewer`'s findings are corrective (missing index, naming, constraints) rather than structural rewrites.
- `lead-senior-architect`'s synthesis is precise — three ADRs explain why the Stage 2 findings cluster the way they do, giving the team a sequenced path rather than a scattered list.
- `lead-project-manager` confirms the work is on-scope: no out-of-aims drift into OAuth/2FA/recovery, so the rework can stay focused on the four stated success criteria.
- `peer-readability-engineer` returned the highest peer score (6/10) — code clarity is fixable inside the existing structure once the structural calls land.

## What's Concerning

- Runtime mismatch with stated deployment target: module-scope `PrismaClient` + native `bcrypt` + Node `crypto` foreclose Vercel Edge (`lead-senior-architect`, `team-performance-reviewer`).
- Session storage is a same-origin XSS to 7-day full account takeover: token written to `localStorage` (`app/auth/session.ts:29-33`) and returned raw in the JSON response body (`app/auth/route.ts:14-15`).
- Performance SLO is mathematically unreachable as written: `bcrypt.hashSync` at cost 12 and `bcrypt.compare` at the same cost each exceed the 200ms p95 budget on the request path.
- Route handler drops `login()` without `await` and force-casts `as unknown as Response` — unhandled rejection plus a lie to the type system at the API boundary (`app/auth/route.ts:10-21`).
- Failure-path test coverage is absent — `login()` ships with one happy-path test and five untested branches; `createSession`, `findSession`, and the route handler have zero coverage.
- No schema validation, no rate limiting, and all failures return HTTP 401 regardless of cause — the API boundary has no defensive layer (`team-security-reviewer`, `team-backend-reviewer`).

## Key Notes from the Committee

### lead-project-manager
> Aim alignment: 2/10. Scope: on-scope. All 4 stated success criteria regressed. Hold for rework.

### lead-senior-architect
> Decision: three structural choices (Node-runtime Prisma in module scope, fragmented session-storage boundary, per-handler cross-cutting concerns) are each incompatible with the aims. Block; rebuild boundaries first.

### team-performance-reviewer
> bcrypt.hashSync at cost 12 pins event loop ~250ms — stated sub-200ms p95 SLO is mathematically unachievable. Two PrismaClient instances will exhaust Neon connections.

### team-security-reviewer
> Session token written to localStorage (any same-origin XSS yields 7-day account takeover); token returned in JSON response body; no rate limiting; token stored plaintext in DB.

### peer-quality-engineer
> Auth flow ships with one happy-path test and zero failure-path coverage.

### peer-typescript-reviewer
> POST handler drops the login() Promise without await, then lies to the type system with `as unknown as Response`; LoginResult is a loose object instead of a discriminated union.

## Stage 0 — Profiler

### Project profile
- **Type:** web-app
- **Languages:** typescript, sql
- **Frameworks:** nextjs, prisma
- **Datastores:** postgres

### Review scope
- **Kind:** full
- **Description:** full project — nextjs-auth fixture, all source files
- **Files:** app/auth/login.ts, app/auth/session.ts, app/auth/route.ts, app/api/route.ts, prisma/schema.prisma, prisma/migrations/20260301_add_users.sql, tests/auth.test.ts

### Casting reasoning
TypeScript-first Next.js + Prisma web-app with a focused auth module in full-project scope. The README explicitly documents six deliberate gaps spanning security (session token in localStorage, no rate limiting on /login, synchronous bcrypt.hashSync blocking the event loop), database (missing index on email column), and test quality (happy-path only coverage, unhandled Promise rejection in route.ts). Stage 1 casts peer-typescript-reviewer (5 .ts files in app/ and tests/), peer-sql-reviewer (schema.prisma + migration file), peer-quality-engineer (test-quality gaps explicitly noted in README), and peer-readability-engineer (deliberate structural issues including unhandled rejections and synchronous blocking calls warrant a readability pass despite scope being under 200 lines). Stage 2 casts team-security-reviewer (auth always casts; explicit localStorage token + no rate limit gaps), team-backend-reviewer (route handlers in app/auth/route.ts and app/api/route.ts, business logic in login.ts), team-database-reviewer (schema.prisma + migration with known missing email index), team-privacy-compliance-reviewer (user credentials, session token handling, PII in user schema), and team-performance-reviewer (sub-200ms p95 is a stated success criterion; blocking synchronous bcrypt is an explicit named gap). Skipped team-frontend-reviewer and team-accessibility-reviewer (no UI components, JSX, or CSS in scope — pure server-side auth logic), team-network-reviewer (no HTTP clients or external API integrations), team-devops-infra-reviewer (no CI configs, Dockerfile, or IaC), team-observability-reviewer (no logging/metrics SDK imports or server entrypoint), and team-data-ml-reviewer (no ML frameworks).

## Stage 1 — Peer Review

### peer-typescript-reviewer (claude-sonnet-4-6)

**Verdict:** block · **Score:** 3/10

> POST handler drops the login() Promise without await, then lies to the type system with `as unknown as Response`; LoginResult is a loose object instead of a discriminated union.

#### Findings

- **[high]** POST handler does not await login(); unhandled rejection + forced double-cast to silence types — `app/auth/route.ts:10-21`
  - `const result = login(body)` captures a `Promise<LoginResult>` without `await`. The subsequent `.then()` chain is returned — and then cast `as unknown as Response` to silence the compiler. Any rejection inside `login()` (e.g. a Prisma error) becomes an unhandled Promise rejection in this scope because there is no `.catch` and no `try/catch` wrapping the chain.
  - **Suggestion:** Change to: `const result = await login(body);` inside the `async` function, wrap in `try/catch`, then return the appropriate `Response` directly. The `as unknown as Response` cast disappears entirely.

- **[medium]** request.json() result is implicitly `any`; flows unvalidated into login() — `app/auth/route.ts:8`
  - `await request.json()` returns `Promise<any>` by default. The value flows directly into `login(body)` which expects `LoginInput`, meaning an attacker or a buggy client can send any JSON shape and the compiler will not object.
  - **Suggestion:** Annotate as `unknown` explicitly: `const body: unknown = await request.json()` and parse with a schema (e.g. `const parsed = LoginInputSchema.parse(body)`) before passing to `login()`.

- **[medium]** LoginResult is a loose object type instead of a discriminated union — `app/auth/login.ts:18-23`
  - `LoginResult` is `{ ok: boolean; userId?: string; token?: string; error?: string }`. The invariant — when `ok` is `true`, `userId` and `token` are always set; when `ok` is `false`, `error` is set — is not encoded in the type.
  - **Suggestion:** Model as a discriminated union: `type LoginResult = { ok: true; userId: string; token: string } | { ok: false; error: string }`.

- **[medium]** persistSessionToken() is called in server-side code path but only runs in browser — silent no-op on server — `app/auth/login.ts:74`
  - `persistSessionToken(session.token)` is not `async` — it returns `void` synchronously. The call silently no-ops on the server (the `typeof window !== 'undefined'` guard in session.ts means it only runs in a browser). In a Next.js SSR/edge context, `login()` is called server-side; `persistSessionToken` does nothing.
  - **Suggestion:** If session persistence is intentionally client-side, move `persistSessionToken` out of `login()` and into client code. If server-side (httpOnly cookie), the function should accept a `Response` or cookie-setter callback.

- **[low]** LoginInput and LoginResult should use `import type` for type-only imports — `app/auth/route.ts:3`
  - If the project uses `verbatimModuleSyntax` or `isolatedModules`, mixing value and type imports without `import type` can cause subtle emit issues.
  - **Suggestion:** Use `import type { LoginInput, LoginResult } from './login'` for type-only positions.

#### Stage handoff notes
session.ts: the `persistSessionToken` writing the raw token to `window.localStorage` is a security finding (XSS-readable token), not a TypeScript-lens issue — flagged for team-security-reviewer. login.ts: `bcrypt.hashSync` blocking the event loop at request time is a performance issue — flagged for team-performance-reviewer. tests/auth.test.ts: only the happy path is covered — flagged for peer-quality-engineer.

---

### peer-sql-reviewer (claude-haiku-4-5-20251001)

**Verdict:** concerns · **Score:** 5/10

> Session.user_id FK has no index — every user-lookup query and User delete will table-scan Session. Add CREATE INDEX session_user_id_idx ON "Session"("user_id").

#### Findings

- **[high]** Foreign key Session.user_id has no index; user queries and User deletes will table-scan — `prisma/migrations/20260301_add_users.sql:24-26`
  - Session.user_id is declared as a foreign key with ON DELETE CASCADE, but no explicit index covers it. Postgres does not auto-index foreign keys. Every 'find sessions for user X' query will sequentially scan the entire Session table. Every User delete will cascade by scanning Session to find all matching rows.
  - **Suggestion:** Add `CREATE INDEX session_user_id_idx ON "Session"("user_id");` immediately after the Session table definition. Consider a composite index on (user_id, expires_at) instead, which covers both the lookup and the cascade-delete scan.

- **[high]** Foreign key on Session.user_id lacks explicit ON DELETE policy documentation — `prisma/migrations/20260301_add_users.sql:26`
  - The FK declares ON DELETE CASCADE but the migration contains no comment explaining why CASCADE is the right choice. The Prisma schema file shows no ON DELETE annotation either, creating drift risk.
  - **Suggestion:** Add a comment explaining the CASCADE intent. Add `@relation(..., onDelete: Cascade)` to the Session model in schema.prisma.

- **[medium]** Mixed naming convention: PascalCase tables, snake_case columns — `prisma/migrations/20260301_add_users.sql:4-26`
  - Table names are PascalCase ('User', 'Session') but columns use snake_case ('user_id', 'created_at', 'password_hash'). Mixing conventions slows readers who pattern-match on a single style.
  - **Suggestion:** Pick one convention and apply it consistently. Document the choice in a project CONVENTIONS.md.

- **[medium]** Migration lacks explicit DOWN (rollback) path — `prisma/migrations/20260301_add_users.sql:1-26`
  - The migration file contains only the UP section. If this raw SQL is ever used outside Prisma's tooling, the absence of a documented DOWN is a risk.
  - **Suggestion:** Add a comment explaining Prisma's reversibility handling or add a separate .down.sql file.

- **[medium]** Email column not constrained to non-empty; password_hash not constrained to minimum length — `prisma/migrations/20260301_add_users.sql:7-8`
  - The User.email and User.password_hash columns are NOT NULL but have no CHECK constraints to enforce minimum length or format.
  - **Suggestion:** Add CHECK constraints for basic email format validation and minimum password_hash length.

#### Stage handoff notes
Security-level findings (bcrypt blocking, token storage, rate limiting) are out-of-scope for this lens — those belong to team-security-reviewer and team-performance-reviewer. The migration is structurally sound and the schema is reasonable for an auth module.

---

### peer-quality-engineer (claude-sonnet-4-6)

**Verdict:** block · **Score:** 3/10

> Auth flow ships with one happy-path test and zero failure-path coverage. Five login branches, all session paths, and the entire route handler are untested.

#### Findings

- **[critical]** login() has no failure-path tests; five branches go untested in production auth code — `tests/auth.test.ts:38-43`
  - The only test asserts the happy path (valid credentials → ok: true). The production login() has five distinct failure exits — missing/invalid email, missing/invalid password, password too short, user not found, and password mismatch — none exercised by any test. The aims snapshot explicitly lists 'Test coverage protects against regression' as a success criterion.
  - **Suggestion:** Add four failure-path tests: (1) mock findUnique to resolve null → `{ ok: false, error: 'invalid credentials' }`; (2) mock bcrypt.compare to resolve false; (3) call login with empty email; (4) call login with short password.

- **[high]** Route handler (app/auth/route.ts) has zero test coverage; bugs at the HTTP seam are invisible — `app/auth/route.ts:1-16`
  - The POST handler wires login() into a Response but has no test of any kind. A unit test on login() alone cannot catch the route returning the wrong status code or an unhandled rejection from request.json() throwing.
  - **Suggestion:** Add an integration-style test constructing a Request, calling POST(request), and asserting Response.status and parsed JSON body for success and failure cases.

- **[high]** createSession() and findSession() in session.ts have no tests; session creation and expiry logic are unverified — `app/auth/session.ts:13-40`
  - The expiry comparison on line 32 is a real branch — an expired session returns null — and a clock-boundary bug here would silently accept expired tokens in production.
  - **Suggestion:** Add unit tests with vi.useFakeTimers() to pin Date.now() for deterministic expiry tests.

- **[medium]** Happy-path test under-asserts: result.token is never checked — `tests/auth.test.ts:40-43`
  - The single existing test asserts result.ok and result.userId but never asserts result.token. A regression that drops the token from the response passes this test.
  - **Suggestion:** Extend to: `expect(result).toEqual({ ok: true, userId: 'user-1', token: 'tok' })`.

- **[medium]** persistSessionToken writes to window.localStorage — no test verifies or isolates this side effect — `app/auth/session.ts:22-26`
  - In a jsdom test environment window is defined, so this side effect fires during the happy-path test without any assertion or cleanup. Future tests may silently inherit the leaked token.
  - **Suggestion:** Spy on window.localStorage.setItem and add `afterEach(() => window.localStorage.clear())`.

#### Stage handoff notes
The localStorage token write is both a test-isolation finding (mine) and a security finding (client-readable token). The missing await on login() in route.ts is a TypeScript correctness issue for peer-typescript-reviewer. bcrypt.hashSync blocking call is a performance concern for team-performance-reviewer.

---

### peer-readability-engineer (claude-haiku-4-5-20251001)

**Verdict:** concerns · **Score:** 6/10

> Magic-number session TTL arithmetic (1000 * 60 * 60 * 24 * 7) appears twice in different files; extract SESSION_TTL_MS. Two unrelated utility functions share a module — split or extract hashPasswordSync.

#### Findings

- **[medium]** Magic-number time arithmetic for session TTL; extract named constant — `app/auth/session.ts:15`
  - createSession computes expiresAt as `new Date(Date.now() + 1000 * 60 * 60 * 24 * 7)` — inline time arithmetic that readers must decode. The same literal appears again in tests/auth.test.ts.
  - **Suggestion:** Add `const SESSION_TTL_MS = 7 * 24 * 60 * 60 * 1000;` at module level, export it, and use it in both createSession and tests.

- **[medium]** Two unrelated login utilities in one module; split or extract hashPasswordSync — `app/auth/login.ts:43-45`
  - app/auth/login.ts exports two unrelated functions: login (the main feature) and rehashPasswordOnLogin (password-hashing utility). The latter is a one-liner that duplicates hashPasswordSync and has no call site in scope.
  - **Suggestion:** Either delete rehashPasswordOnLogin if unused, or extract both hash utilities to a separate app/auth/crypto.ts file.

- **[medium]** Test file covers only happy path; structure signals incomplete test coverage — `tests/auth.test.ts:24-30`
  - The test file has a single test case labeled 'login (happy path only)' in the describe block title itself.
  - **Suggestion:** Add test cases for user not found, password mismatch, missing/invalid email, and short password.

- **[medium]** Placeholder names 'err' and 'ok' reduce clarity — `app/auth/login.ts:32, 34, 48, 50, 53`
  - The login function uses short placeholder names: 'err' for validation error messages, and 'ok' for success/failure boolean. These names are generic and force context lookups.
  - **Suggestion:** Rename 'err' to 'validationError'; consider 'success' or 'isAuthenticated' instead of 'ok' in LoginResult.

- **[low]** Helper function 'findUser' is generic; clarify intent with domain-specific name — `app/auth/login.ts:35-37`
  - The name 'findUser' is generic and doesn't signal that it's specifically a login-time lookup by email.
  - **Suggestion:** Rename to `findUserByEmail(email: string)` or `findUserForLogin(email: string)`.

- **[low]** Function verifyPassword has asymmetric naming compared to persistSessionToken pattern — `app/auth/login.ts:39-41`
  - The module mixes action-based names (verifyPassword, persistSessionToken) and noun-based utility names (findUser, validateInput).
  - **Suggestion:** Align to a single naming pattern consistently across the auth module.

- **[low]** persistSessionToken is async-unsafe for client-side use; comment or refactor — `app/auth/session.ts:32-36`
  - persistSessionToken is a synchronous function called during a server-side flow with no comment explaining why this is safe.
  - **Suggestion:** Add a comment: `// Browser-only: call only from client-side event handlers. Do not invoke from server routes.`

#### Stage handoff notes
app/auth/route.ts line 13 has unhandled promise rejection (correctness issue for peer-typescript-reviewer). Security issues around token storage in localStorage are out of scope for readability but flag for team-security-reviewer.

---

## Stage 2 — Cross-functional

### team-security-reviewer (claude-sonnet-4-6)

**Verdict:** block · **Score:** 2/10

> Session token written to localStorage (any same-origin XSS yields 7-day account takeover); token returned in JSON response body (bearer in memory is exfil-able); no rate limiting on /auth (credential stuffing at line rate); token stored plaintext in DB (dump yields live sessions).

#### Findings

- **[critical]** Session token written to localStorage; readable by any same-origin script — XSS to full account takeover — `app/auth/session.ts:29-33`
  - persistSessionToken() writes the raw 64-hex-char session token to window.localStorage. localStorage is synchronously readable by every script running on the origin: first-party code, third-party analytics, ad scripts, and any XSS payload. The token grants full account access for its 7-day TTL. The project aims document explicitly calls out 'no client-readable tokens' as a success criterion; this directly violates it.
  - **Suggestion:** Remove persistSessionToken() and readSessionToken() entirely. Set the token server-side as an httpOnly + Secure + SameSite=Lax cookie using Next.js's `cookies().set(...)` helper from `next/headers`. Subsequent requests authenticate by reading `cookies().get('session')` on the server — client JS never touches the token.

- **[critical]** Raw session token returned in JSON response body; client JS can read and exfiltrate it from any script context — `app/auth/route.ts:14-15`
  - The POST handler returns `{ userId, token }` as the JSON response body. Any script that can call fetch() or read the XHR response can read and exfiltrate the token. Combined with the localStorage write, the token is exposed via two independent paths.
  - **Suggestion:** Do not return the token in the response body at all. Set it as an httpOnly cookie. The response body after a successful login should contain only: `{ ok: true, userId: r.userId }`.

- **[high]** POST /auth/route has no rate limiting; credential stuffing and brute-force are unbounded — `app/auth/route.ts:4-21`
  - There is no per-IP or per-account rate limit anywhere on the login route. bcrypt at cost 12 adds ~250ms per attempt but does not throttle parallelism. The project aims name 'rate limited' as an explicit success criterion; this is unmet.
  - **Suggestion:** Add per-IP and per-account rate limiting using `@upstash/ratelimit` with Redis backend for Vercel Edge. Apply a sliding-window limit of 5 attempts/60s per IP and 10 attempts/hour per email. Return 429 with `Retry-After` header on breach.

- **[high]** request.json() flows unvalidated into login(); no schema parse at the API boundary — `app/auth/route.ts:8-10`
  - The POST handler passes the raw JSON body directly to login(body) with no schema validation. The type is implicitly `any`.
  - **Suggestion:** Parse with zod: `const parsed = LoginSchema.safeParse(body); if (!parsed.success) return new Response(JSON.stringify({ error: 'invalid_input' }), { status: 400 });` where LoginSchema is `z.object({ email: z.string().email().max(254), password: z.string().min(8).max(128) })`.

- **[medium]** Session token stored as plaintext in database; a database compromise yields immediately usable live sessions — `app/auth/session.ts:16-20`
  - createSession() stores the raw 64-hex token in the Session.token column. If the Neon Postgres instance is compromised, every active session token is immediately usable. Standard practice is to store SHA-256(token) in the database.
  - **Suggestion:** Hash the token before persisting: `const tokenHash = createHash('sha256').update(token).digest('hex');`. In findSession(), look up by the hash. The cookie still carries the plaintext token.

- **[medium]** Unhandled promise rejection in route handler can leak internal error details to the client — `app/auth/route.ts:8-21`
  - The route handler has no try/catch. An unhandled rejection may surface Prisma error messages that leak schema details.
  - **Suggestion:** Wrap the entire handler body in try/catch; return a generic `{ error: 'internal_error' }` with status 500, logging the full error server-side with a correlation ID.

- **[medium]** No logout / session revocation endpoint; tokens remain valid for 7 days after a user logs out or password changes — `app/auth/session.ts:1-45`
  - The session module provides createSession() and findSession() but no deleteSession() or revokeAllUserSessions(). An attacker who phished a token before a password change retains access for up to 7 days.
  - **Suggestion:** Add `deleteSession(token: string)` and `revokeAllUserSessions(userId: string)`. Expose a DELETE /auth/session route. Call revokeAllUserSessions() on password change.

#### Stage handoff notes
bcrypt.hashSync() is correct cryptographically (cost 12) but synchronous — performance concern for team-performance-reviewer. The missing await on login() in route.ts is the TS peer's finding. No hardcoded secrets visible in scope. Timing oracle (fast return on user-not-found vs bcrypt-delay) is a low-severity username-enumeration channel — dropped in favor of higher-priority findings.

---

### team-backend-reviewer (claude-sonnet-4-6)

**Verdict:** block · **Score:** 3/10

> POST /auth has no schema validation at the boundary; all failures return 401 regardless of cause; the success and error response envelopes are inconsistent shapes; and persistSessionToken is called without awaiting, silently dropping errors.

#### Findings

- **[high]** POST /auth handler passes raw request.json() body into login() with no schema validation at the boundary — `app/auth/route.ts:8-10`
  - const body = await request.json() produces an untyped value that flows directly into login(body). A caller can send `{email: 123, password: [null]}`, extra prototype-polluting fields, or a completely malformed structure — none is rejected at the edge.
  - **Suggestion:** Add a Zod schema: `const parsed = LoginSchema.safeParse(body); if (!parsed.success) return new Response(JSON.stringify({ error: { code: 'invalid_request', message: parsed.error.message } }), { status: 400 });`

- **[high]** Every login failure returns HTTP 401 regardless of failure cause, masking validation errors as authentication failures — `app/auth/route.ts:12-14`
  - The handler returns status 401 for any !r.ok result, including 'email required' / 'password too short' (which are 400 Bad Request — the client sent a malformed payload, not an unauthenticated one).
  - **Suggestion:** Distinguish error codes in LoginResult and map them to correct status codes: 'invalid_credentials' → 401, 'invalid_request' → 400.

- **[high]** Success and error response envelopes have inconsistent shapes across the same endpoint — `app/auth/route.ts:13-17`
  - The 401 response body is `{ error: r.error }` and the 200 response body is `{ userId: r.userId, token: r.token }`. A client SDK must special-case the success branch because the success object is not nested under a `data` key.
  - **Suggestion:** Use a consistent envelope: success returns `{ data: { userId, token } }`; failure returns `{ error: { code: string, message: string } }`.

- **[medium]** persistSessionToken() is called without await and its failure is silently swallowed — `app/auth/login.ts:42`
  - persistSessionToken(session.token) is fire-and-forget. If it is async, its rejection is unhandled and the login() function returns ok: true with a token that was never durably stored.
  - **Suggestion:** Await the call: `await persistSessionToken(session.token);` and ensure the surrounding login() function propagates any thrown error up to the handler.

#### Stage handoff notes
hashPasswordSync and rehashPasswordOnLogin both call bcrypt.hashSync on what is likely a request path — team-performance-reviewer should verify blocking the event loop at cost=12. PrismaClient instantiated at module scope is incompatible with the Vercel Edge runtime constraint — lead-senior-architect should verify.

---

### team-database-reviewer (claude-sonnet-4-6)

**Verdict:** concerns · **Score:** 6/10

> The missing Session.user_id index needs to be a composite (user_id, expires_at) for the auth workload's hot path; and Vercel Edge's per-request connection model will exhaust Neon's connection cap without a pooler.

#### Findings

- **[high]** Session lookup needs composite (user_id, expires_at), not a single-column user_id index — `prisma/migrations/20260301_add_users.sql:14-27`
  - The auth workload's dominant query is 'find this user's active sessions' — WHERE user_id = ? AND expires_at > NOW(). With only a single-column index on user_id, the planner must filter the full lifetime history of that user's sessions row-by-row.
  - **Suggestion:** `CREATE INDEX session_user_id_expires_at_idx ON "Session"("user_id", "expires_at");` Also add `CREATE INDEX session_expires_at_idx ON "Session"("expires_at");` for the GC path.

- **[high]** Vercel Edge deploys without a connection pooler — Neon's connection cap will be exhausted — `prisma/schema.prisma:1-4`
  - Vercel Edge functions open a new database connection per cold start. Neon's starter tier caps at 100 connections. At 50 concurrent cold-start requests, the connection count can hit the Neon cap causing 'too many connections' errors — auth failures, not degraded performance.
  - **Suggestion:** Switch the Prisma datasource URL to Neon's pooled connection string (?pgbouncer=true endpoint) and add ?connection_limit=1 to DATABASE_URL for Edge functions. Evaluate the Prisma Accelerate or neon/serverless HTTP-over-WebSocket driver.

- **[medium]** No index on Session.expires_at; periodic GC will full-scan the table — `prisma/migrations/20260301_add_users.sql:14-27`
  - A GC job deleting expired sessions performs a sequential scan. The composite (user_id, expires_at) cannot support an expires_at-only range scan because the leading column is user_id.
  - **Suggestion:** Add `CREATE INDEX session_expires_at_idx ON "Session"("expires_at");` as a second standalone index.

- **[medium]** Session has no upper bound on active sessions per user; ON DELETE CASCADE radius is unbounded — `prisma/migrations/20260301_add_users.sql:14-27`
  - Without a cap or GC, a user with years of login history will accumulate an arbitrarily large session set. When a user is removed, ON DELETE CASCADE will delete an unbounded number of Session rows in a single transaction — holding locks on both tables.
  - **Suggestion:** Add application-layer enforcement capping active sessions per user, or ensure the GC job runs frequently. Consider a batched delete strategy for user removal.

#### Stage handoff notes
Connection pool exhaustion is the finding most likely to cause a hard production outage. The DevOps reviewer should confirm DATABASE_URL is set to the pooled Neon endpoint in Vercel project settings.

---

### team-privacy-compliance-reviewer (claude-sonnet-4-6)

**Verdict:** concerns · **Score:** 5/10

> Session rows accumulate indefinitely; no user erasure path exists; session token returned verbatim in the login response body creates a PII-in-response leak; schema holds PII fields with no lawful-basis annotation.

#### Findings

- **[high]** No erasure path for User or associated Sessions; right to deletion cannot be honored — `prisma/schema.prisma:7-16`
  - The User model stores email (PII) and the Session model stores user_id linked to a real user. There is no deleteUser function and no endpoint that removes user records or their associated sessions. GDPR Article 17 compliance requires this.
  - **Suggestion:** Add a deleteUser(userId: string) function that deletes all Session rows then the User row, and emits an audit-log event. Add `onDelete: Cascade` to the Session.user_id relation in schema.prisma.

- **[high]** Session table has no retention rule; expired sessions accumulate indefinitely — `prisma/schema.prisma:18-24`
  - Every login creates a new session row that persists forever. Because session rows include user_id (a re-linkable identifier), they constitute personal data under GDPR Article 4 and are subject to the storage-limitation principle (Article 5(1)(e)).
  - **Suggestion:** Add a scheduled job that deletes Session rows where expires_at < now() - INTERVAL '7 days'. Document the chosen retention window in a comment above the Session model.

- **[medium]** Raw session token returned verbatim in LoginResult and passed to client storage — `app/auth/login.ts:40`
  - The raw token in the HTTP response body means any logging middleware, error-reporting SDK (e.g., Sentry), or proxy that captures response bodies will record this token verbatim.
  - **Suggestion:** Remove token from the LoginResult type. Set the session token as an HttpOnly, Secure, SameSite=Strict cookie in the HTTP response handler.

- **[low]** PII fields carry no lawful-basis annotation; schema is not self-documenting for compliance purposes — `prisma/schema.prisma:7-11`
  - The User model collects email (personal data under GDPR Article 4) with no comment stating the lawful basis for processing, retention policy, or PII tag.
  - **Suggestion:** Add a Prisma comment block: `/// @pii email: contract basis (authentication); password_hash: derived secret, never logged. Retention: retained for account lifetime; purged on user deletion.`

#### Stage handoff notes
The security-side localStorage concern is owned by team-security-reviewer. My finding #3 addresses the privacy-specific angle: the raw token in the JSON response body will appear in error-reporting SDK logs. No third-party processors are imported in scope.

---

### team-performance-reviewer (claude-sonnet-4-6)

**Verdict:** block · **Score:** 2/10

> bcrypt.hashSync at cost 12 pins the event loop ~250 ms per login — the stated sub-200 ms p95 SLO is mathematically unachievable before any I/O. PrismaClient instantiation per module will exhaust Neon connection limits on Vercel Edge cold starts.

#### Findings

- **[critical]** bcrypt.hashSync at cost factor 12 blocks the event loop ~250 ms per call; sub-200 ms p95 SLO is mathematically unachievable — `app/auth/login.ts:28`
  - bcrypt.hashSync at cost factor 12 takes ~200-300 ms of pure CPU on a modern server; on a Vercel Edge worker (constrained single-threaded V8 isolate) this is the entire allowed p95 budget before any DB work. At 10 concurrent login attempts, the effective throughput ceiling is ~4 req/s per isolate.
  - **Suggestion:** Replace bcrypt.hashSync with `await bcrypt.hash(plain, 12)` everywhere. For Vercel Edge, evaluate whether bcrypt is even supported. If not, migrate to `@node-rs/bcrypt` (WebAssembly build) or Argon2 via `@node-rs/argon2` wasm build.

- **[high]** Two PrismaClient instantiations at module scope will exhaust Neon's connection limit under Vercel Edge cold starts — `app/auth/login.ts:4`
  - Neon's free/starter tier caps at 10-100 connections. Each cold-started isolate runs `new PrismaClient()` in both login.ts and session.ts, opening 2 connections per isolate instance. At 50 concurrent cold-start requests, that is 100 connections instantiated simultaneously.
  - **Suggestion:** Extract a single shared PrismaClient singleton into `lib/prisma.ts` using the globalThis pattern. Evaluate Prisma's Edge-compatible driver (prisma/adapter-neon with @neondatabase/serverless) which uses HTTP-over-WebSocket and avoids persistent TCP connections.

- **[high]** Login path executes two sequential DB round trips (~20-40 ms combined) consuming 10-20% of the p95 budget — `app/auth/login.ts:32-37`
  - At cost factor 12: bcrypt.compare (~250 ms) + findUser (~10 ms) + createSession (~10 ms) = ~270 ms p50 — still over the 200 ms SLO.
  - **Suggestion:** After fixing hashSync, validate the bcrypt cost factor. At cost factor 10: ~60 ms + 20 ms = ~80 ms p50. Document the chosen trade-off between cost factor and SLO explicitly.

- **[medium]** Stated sub-200 ms p95 SLO with bcrypt at cost 12 is mathematically unachievable even after fixing hashSync to async — `app/auth/login.ts:21`
  - bcrypt.compare at cost factor 12 runs ~200-300 ms CPU-bound regardless of the async/sync API surface. The SLO (sub-200 ms p95) and the security parameter are in direct conflict and neither the code nor any documented decision acknowledges it.
  - **Suggestion:** Document the bcrypt cost factor vs latency trade-off explicitly. At cost 10 the p95 SLO is achievable; at cost 12 it is not. If cost 12 is a security requirement, revise the SLO to sub-400 ms p95.

#### Stage handoff notes
peer-sql-reviewer correctly flagged the missing index on Session.user_id — latency impact on session invalidation is real but secondary to bcrypt and connection-pool issues dominating the login path. Once findings #1 and #2 are resolved, run a Vercel Edge-compatible load test at 50 concurrent logins to validate p95 SLO.

---

## Stage 3 — Leadership

### lead-senior-architect (claude-opus-4-7)

**Verdict:** block · **Score:** 2/10

> Decision: the auth module is built on three structural choices (Node-runtime Prisma in module scope, fragmented session-storage boundary, per-handler cross-cutting concerns) that are each incompatible with the aims' Vercel Edge + sub-200ms p95 + security constraints. Block; rebuild the boundaries before reattempting the feature.

#### Findings

- **[critical]** Module-scope PrismaClient + bcrypt + Node crypto foreclose the aims-mandated Vercel Edge runtime — `app/auth/login.ts:1-5, app/auth/session.ts:1-3`
  - Two module-scope `new PrismaClient()` instances are instantiated at import time, bcrypt (a native binding) is used directly, Node's `crypto.randomBytes` is called from session.ts, and session-token persistence reaches for `window.localStorage`. None of these survive an Edge runtime swap. There is no 'runtime adapter' boundary that owns 'how does auth reach external services', so each call site picks Node-runtime APIs by default.
  - **Suggestion:** Decide the runtime first. If Edge: replace `@prisma/client` with `@prisma/client/edge` + Neon serverless driver, replace `bcrypt` with `@node-rs/argon2` (WASM build), replace `crypto.randomBytes` with `crypto.getRandomValues(new Uint8Array(32))`, delete `persistSessionToken`/`readSessionToken` entirely. Either choice gets a 1-page ADR at `app/auth/ADR-001-runtime.md` before any other change lands.

- **[high]** Session-storage decisions are split across server-side DB write and client-side localStorage write with no owning module — `app/auth/session.ts:13-30, app/auth/login.ts:29-31`
  - `createSession` writes the token to Postgres; `persistSessionToken` writes the same token to `window.localStorage`; `login` invokes both in sequence; `route.ts` also returns the token in the JSON response body. Three writers, three readers, no contract. The team-security-reviewer's critical findings are individual exploits of the same structural fact — there is no `SessionStore` boundary.
  - **Suggestion:** Define `SessionStore` in `app/auth/session-store.ts` with `set(token, response)`, `get(request)`, `clear(response)`, and `revoke(userId)` methods. Implement using `cookies()` from `next/headers`. Update `login.ts` to call `SessionStore.set()`. Update `route.ts` to return `{userId}` only. Delete `persistSessionToken` and `readSessionToken`.

- **[high]** Validation, error envelope, rate limiting, and error classification are hand-rolled per handler instead of centralized — `app/auth/route.ts:3-12, app/auth/login.ts:7-12`
  - Each call site reinvents the wheel: no schema validation at boundary, all failures return 401, response envelopes are inconsistent, no rate limiting, no try/catch. There is no `withAuthRoute(schema, handler)` wrapper.
  - **Suggestion:** Create `app/lib/with-route.ts` exporting `withRoute({schema, rateLimit, handler})` that: (a) parses via Zod schema.safeParse, returns 400 on failure; (b) applies per-IP rate limit; (c) wraps handler in try/catch, maps error classes to status codes; (d) emits structured logs. Make this the only correct way to add a route.

#### Stage handoff notes
Synthesis map: ADR-1 (runtime incompatibility) generates team-performance's bcrypt-blocking, two-PrismaClient, and Neon-connection findings. ADR-2 (session-storage boundary) generates team-security's localStorage-ATO and token-in-body criticals, team-privacy's PII-in-logging finding. ADR-3 (cross-cutting concerns) generates team-backend's no-schema-validation, all-failures-401, and inconsistent-envelope findings, plus team-security's no-rate-limiting and no-try-catch findings. The quality-engineer's 'zero failure-path coverage' finding is partially downstream of ADR-3 — there are no seams to test in isolation. Recommend writing a 1-page runtime ADR before reopening this PR; the rebuild after that decision is 1-2 days of focused work.

---

### lead-project-manager (claude-opus-4-7)

**Verdict:** block · **Score:** 2/10

> Aim alignment: 2/10. Scope: on-scope. Verdict: hold. PR aimed at the right goal but regresses every one of the 4 stated success criteria — security x2, perf, graceful failure, tests. Hold for rework.

#### Findings

- **[critical]** PR regresses all four stated success criteria despite being aimed at the correct goal — `.review/aims.md:3-5`
  - Criterion (a) 'Login is secure': raw session token in localStorage (CRITICAL XSS-to-ATO), token in JSON response body, zero rate limiting. Criterion (b) 'Login is fast (sub-200ms p95)': structurally impossible — bcrypt at cost 12 alone exceeds the 200ms budget, plus hashSync + two PrismaClient instances. Criterion (c) 'Failures fall back gracefully': every failure returns 401, inconsistent envelopes, route handler doesn't await login(). Criterion (d) 'Test coverage': one happy-path test, zero failure-path coverage.
  - **Suggestion:** Hold for rework. Sequence: (1) Security & shape PR — move tokens to httpOnly cookies, add schema validation, await login(), unify response envelopes, add rate limiting. Closes criteria (a) and most of (c). (2) Performance & runtime PR — single PrismaClient, configure Neon pooler, move bcrypt off the request path. Closes criterion (b). (3) Test PR — add failure-path coverage. Closes criterion (d).

- **[high]** Constraint 'Vercel Edge runtime' is technically respected but practically violated by bcrypt-on-request-path — `.review/aims.md:6`
  - The PR's imports are Edge-compatible, but bcrypt.hashSync on the request path blocks the single-threaded Edge worker and two PrismaClient instances will exhaust Neon's connection cap without a pooler.
  - **Suggestion:** Decide explicitly: keep Edge (refactor to async bcrypt + Neon pooler + single PrismaClient) or carve out auth to a Node runtime function (update aims.md to reflect). Do not ship without making the call.

- **[medium]** Highest-leverage next step is the security/shape fixes, not perf or tests — `.review/aims.md:3-5`
  - Three of the four criteria sit on findings with small, bounded fixes: cookie-based sessions + schema validation + await + rate limiting + unified envelope is roughly 80-150 lines of change.
  - **Suggestion:** Plan three follow-up PRs: security/shape (closes a + c), runtime/perf (closes b, may require aims.md revision), tests (closes d).

#### Stage handoff notes
Aims are well-captured for this fixture. No rescoping recommended at the aims level. Open question: the 200ms p95 SLO with bcrypt cost factor 12 on Vercel Edge may be physically unachievable — aims.md should be revised before the next review if so.

---

## Aims Snapshot

A Next.js + Prisma auth module rewrite. Goal: Ship a secure, performant password auth flow for production users. Success criteria: Login is secure (no client-readable tokens, no timing attacks, rate limited). Login is fast (sub-200ms p95). Failures fall back gracefully. Test coverage protects against regression. Non-goals: OAuth, 2FA, account recovery. Constraints: Must work on Vercel Edge runtime; Postgres on Neon.

## Run Metadata

- **Plugin version:** 0.1.0
- **Wall-clock:** 900s (~15 min)
- **Models used:** claude-sonnet-4-6, claude-haiku-4-5-20251001, claude-opus-4-7
- **Estimated cost:** $0 (internal run)
