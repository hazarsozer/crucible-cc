# Crucible Review — auth module rewrite

_Review ID: 2026-05-10-1430-auth-refactor · Generated: 2026-05-10T14:38:22Z · Project: web-app_

## Final Verdict

**Score:** 5.4/10
**Verdict:** conditional_approval

The auth module's structural choices are mostly right — clean SQL, well-bounded
auth boundary, on-scope phase, idiomatic crypto choices where they exist. Two
security gaps (localStorage tokens, no rate limiting) block "production-ready"
as stated in `aims.md`; both are 1-day fixes that don't require architectural
changes. Quality coverage is thin and needs a follow-up phase. The committee's
verdicts span `block` (security), `concerns` (backend, TS peer, quality, PM,
architect), `approve` (SQL peer, database) — the spread is consistent with
"structurally sound, operationally underbaked." Conditional approval — block
the merge until the localStorage and rate-limiting findings are addressed,
then ship.

## Executive Summary

This PR rewrites the password-based authentication module for a small SaaS web
app on Next.js + Prisma. The shape of the work is correct: a small, well-bounded
`app/auth/` module exposes `login`, `createSession`, and a route handler that
ties them together; the Prisma migration introduces `User` and `Session` tables
with a sensible foreign-key relationship; the language-level choices (bcrypt
for password hashing, `crypto.randomBytes` for tokens, Prisma's parameterized
API for queries) are within the playbook. Stage 1 found the expected file-level
rough edges — a forced `as unknown as Response` cast, a missing `await` on the
`login()` call, a happy-path-only test suite — but nothing structurally wrong
with how the module is composed.

The committee's headline concerns are operational rather than structural.
`team-security-reviewer` opens with a critical finding: the session token is
written to `window.localStorage` after a successful login, which means any
same-origin script (first-party, third-party, or an injected XSS payload)
reads it and gains a 7-day account takeover. The same persona flags two
`high`-severity gaps: `/login` has no rate limiting (credential stuffing is
wide open), and `bcrypt.hashSync` runs on the request path (an event-loop
blocker that doubles as a DoS amplifier). `team-backend-reviewer` notes that
the route handler returns `result.then(...)` without `await`, which means
rejected `login` promises surface as unhandled rejections rather than 500s
the framework can map. `peer-quality-engineer` flags the only-happy-path test
suite — a single assertion proving valid credentials succeed, with no coverage
of invalid creds, expired sessions, or edge-case password validation.

The leadership stage holds the work to its stated criterion.
`lead-senior-architect` records an ADR-style finding: the auth module's
surface is clean, but the localStorage decision forecloses options the next
phase will likely need (httpOnly-cookie-based SSR, CSRF-aware request
handling, Vercel Edge runtime compatibility). The recommendation is "approve
with revisions" rather than "block" — the structure is right, the storage is
wrong, and the storage is a 1-day fix. `lead-project-manager` grades the PR
at 5/10 against `aims.md`: phase scope is honored cleanly (no OAuth, no MFA,
no recovery flows), the SQL migration is solid, but the "Login is secure"
criterion is falsified by the security findings and "Login is fast — sub-200ms
p95" is at risk from the synchronous bcrypt. The PM's verdict is `hold` until
the security gaps close. The aggregator's net call is `conditional_approval` —
the fixes are scoped and the architecture is sound; the merge should not land
until the localStorage and rate-limiting findings are addressed.

## What's Good

- **SQL migrations are clean and reversible.** `peer-sql-reviewer` scores the
  migration 9/10 — correct types (`UUID`, `TIMESTAMPTZ`, `TEXT`), explicit
  `ON DELETE CASCADE` on the FK, `UNIQUE` constraints in the right places,
  and a clean structure that would survive a `DOWN` rewrite. The Prisma
  generator's PascalCase-table / snake_case-column convention is applied
  consistently. No destructive operations (`DROP COLUMN`, `RENAME`) so a
  rollback is a clean `DROP TABLE` away.
- **Auth module boundary is well-scoped.** Three files (`session.ts`,
  `login.ts`, `route.ts`) with a small public surface (`login`,
  `createSession`, `findSession`). `lead-senior-architect` calls this a
  "clean conceptual boundary" — adding OAuth or MFA later would slot into
  the same module without redesign. The boundary corresponds to a concept
  the team will reason about ("auth"), not a directory-tree convenience.
- **Backend API contract is consistent.** `team-backend-reviewer` notes that
  error and success responses use the same JSON envelope shape (`{ error }`
  for failures, `{ userId, token }` for success) and the same status-code
  conventions (200 for success, 401 for invalid creds); mainline cases are
  predictable for any client integrating with the endpoint.
- **Crypto choices are correct where they exist.** bcrypt at cost 12 for
  passwords (per `team-security-reviewer` concern #1: "the algorithm choice
  is correct"), `crypto.randomBytes(32)` for session tokens (CSPRNG, not
  `Math.random`), `bcrypt.compare` (constant-time) on the verify path. No
  hand-rolled crypto, no MD5 / SHA1 used as a security primitive.
- **PM scope discipline is intact.** The diff stays inside the phase's stated
  scope — no OAuth providers, no MFA, no account recovery. `lead-project-manager`
  flags zero non-goal violations. Adjacent improvements (refactoring the email
  service, touching analytics) that often creep into auth PRs are absent here.

## What's Concerning

- **Session tokens stored where client JS can read them** (security/critical).
  `persistSessionToken` writes the raw 32-byte token to `window.localStorage`.
  Any reflected/stored XSS on the same origin escalates to a 7-day account
  takeover with no client-side rotation. This single finding alone justifies
  a security `block` verdict.
- **No rate limiting on `/login`** (security/high). The fixture's own comment
  acknowledges the gap. Credential stuffing from leaked breach lists runs at
  line rate; bcrypt's ~250ms hash cost is the only constraint, which still
  allows ~4 attempts/second/connection and many in parallel.
- **`bcrypt.hashSync` on the request path** (security/high + perf adjacency).
  Each call blocks the Node event loop for 100-200ms at cost 12. Both an
  availability concern (parallel logins serialize behind the lock) and a DoS
  amplifier (a few attackers with parallel connections starve the loop for
  every other in-flight request).
- **Only happy-path test coverage** (quality/high). `tests/auth.test.ts` has
  one `it("returns ok=true for valid credentials")` block. Invalid credentials,
  expired sessions, unknown emails, password-validation edge cases — all
  uncovered. A regression in any failure path ships silently.
- **Unhandled Promise rejection in the route handler** (backend/high).
  `route.ts:13` calls `login(body)` without `await`; the resulting Promise is
  consumed by `.then(...)` and force-cast to `Response`. Rejected promises
  bypass the handler's normal error envelope and surface as raw 500s with no
  context.

## Key Notes from the Committee

### team-security-reviewer
> Move session storage to httpOnly cookies before merge — current localStorage
> exposes tokens to any script on the page.

### team-security-reviewer
> Add rate limiting on /login at the edge — credential stuffing is wide open.

### team-backend-reviewer
> The route handler doesn't await login(); errors will surface as unhandled
> Promise rejections.

### lead-senior-architect
> Auth boundary is right; storage decision is a 1-day fix that unblocks the
> production-ready criterion.

### lead-project-manager
> Phase aim achieved structurally; two security gaps block 'production-ready'.

### peer-quality-engineer
> Tests cover the happy path and nothing else — invalid creds, expired
> sessions, edge inputs all uncovered.

## Stage 0 — Profiler

### Project profile
- **Type:** web-app
- **Languages:** typescript, sql
- **Frameworks:** nextjs, prisma
- **Datastores:** postgres

### Review scope
- **Kind:** uncommitted-diff
- **Description:** auth module rewrite
- **Files:** `app/auth/session.ts`, `app/auth/login.ts`, `app/auth/route.ts`,
  `prisma/migrations/20260301_add_users.sql`, `tests/auth.test.ts`

### Casting reasoning

TypeScript-first project with Prisma SQL migrations. Auth module is
security-sensitive — Security cast as Stage 2 default plus Backend (server
logic) and Database (migrations + queries). Stage 1: TypeScript reviewer
(primary language), SQL reviewer (migrations), Quality engineer (test gap
visible from the file tree).

Skipped: peer-readability-engineer (scope under 200 lines after stripping
migrations), team-frontend-reviewer (no UI files in scope),
team-accessibility-reviewer (no JSX components rendered to user),
team-network-reviewer (no outbound HTTP calls), team-performance-reviewer
(perf concerns surface naturally inside security and backend lenses for a
scope this size), team-observability-reviewer (no logging or tracing code in
scope), team-privacy-compliance-reviewer (no PII retention or consent flow
in this phase), team-data-ml-reviewer (no ML), team-devops-infra-reviewer
(no infra changes), peer-go-reviewer / peer-python-reviewer / peer-rust-reviewer
/ peer-c-cpp-reviewer / peer-java-kotlin-reviewer / peer-swift-reviewer (no
files in those languages).

Final cast roster: 3 Stage 1 peers (TypeScript, SQL, Quality) + 3 Stage 2
team reviewers (Security, Backend, Database) + 2 Stage 3 leadership
(Architect, PM) = 8 personas. Within budget for an "uncommitted-diff" review
of this scope.

## Stage 1 — Peer Review

### peer-typescript-reviewer (claude-sonnet-4-6)

**Verdict:** concerns · **Score:** 6/10

> The double-cast in route.ts and the missing await on login(body) are the
> two real correctness bugs — both compile but mis-shape the runtime behavior;
> the rest are hardening nudges.

#### Findings

- **[high]** Missing `await` on `login(body)` and forced `as unknown as Response` cast — `tests/fixtures/nextjs-auth/app/auth/route.ts:13-25`
  - The handler at `route.ts:13` calls `login(body)` and assigns the
    unawaited Promise to `result`, then chains `result.then((r) => ...)`
    and force-casts the resulting Promise to `Response` via
    `as unknown as Response`. The double-cast is a tell that the source
    type (`Promise<Response>`) and target type (`Response`) are unrelated —
    TypeScript correctly rejects the assignment, and the cast silences it
    instead of fixing it. At runtime the framework receives a Promise
    object, not a Response; this works in some Next.js versions because
    the runtime coerces it, but it's accidental. Worse, any rejection from
    `login` becomes an unhandled rejection in this scope rather than a
    caught error the handler can map to a 4xx/5xx response.
  - **Suggestion:** Replace the `.then` chain with `await`:
    `const r = await login(body); if (!r.ok) return new Response(JSON.stringify({ error: r.error }), { status: 401 }); return new Response(JSON.stringify({ userId: r.userId, token: r.token }), { status: 200 });`.
    Wrap the body in a try/catch to convert exceptions into a typed error
    envelope. Drop the `as unknown as Response` cast — it's no longer
    needed once the function returns the right type.

- **[medium]** `LoginResult` should be a discriminated union, not an object with optional fields — `tests/fixtures/nextjs-auth/app/auth/login.ts:17-22`
  - The current shape `{ ok: boolean; userId?: string; token?: string; error?: string }`
    carries an unrepresented invariant: `userId` and `token` are present
    iff `ok === true`, `error` is present iff `ok === false`. The compiler
    cannot enforce this — code that destructures `{ ok, token }` after a
    falsy `ok` check still passes. A discriminated union
    (`{ ok: true; userId: string; token: string } | { ok: false; error: string }`)
    lets `if (result.ok)` narrow `result.token` to a defined value.
  - **Suggestion:** `type LoginResult = { ok: true; userId: string; token: string } | { ok: false; error: string };`.
    The call sites in `route.ts` already check `r.ok` first, so this is
    purely additive — no logic changes, just shape.

- **[medium]** Bare `await prisma.session.create` with no error handling — `tests/fixtures/nextjs-auth/app/auth/session.ts:24-30`
  - `createSession` awaits a Prisma write that can fail for a handful of
    reasons (connection lost, unique-constraint violation if `token`
    collides — extremely rare with 32 bytes of randomness but not
    impossible, transient pool exhaustion). The thrown error propagates up
    to `login`, which in turn lets it propagate to the route handler,
    where the missing `await` (above) means it surfaces as an unhandled
    rejection. The persona-level concern is that the function has no
    `try/catch` and no error-classification — every Prisma failure looks
    identical to the caller.
  - **Suggestion:** Wrap the Prisma call:
    `try { const session = await prisma.session.create({ ... }); ... } catch (err: unknown) { if (err instanceof Error && err.message.includes('Unique constraint')) { /* retry once with a fresh token */ } throw err; }`.
    Or push the classification into a typed error returned to `login`,
    which then encodes it into the `LoginResult` union.

- **[low]** `findUser` lacks an explicit `Promise<User | null>` return type — `tests/fixtures/nextjs-auth/app/auth/login.ts:50-52`
  - `async function findUser(email: string)` lets TypeScript infer the
    return type from `prisma.user.findUnique`. Inference works, but the
    inferred type leaks Prisma internals into the call site
    (model-extension types, lazy relation flags, etc.), which makes the
    signature brittle to Prisma schema changes. An explicit return type
    both documents the contract and decouples this layer from the ORM's
    internal generic shapes.
  - **Suggestion:** Define a local `User` type (or import the Prisma type
    explicitly via `import type { User } from '@prisma/client'`) and
    annotate: `async function findUser(email: string): Promise<User | null>`.
    Public APIs of the module should always carry explicit return types —
    this is the closest thing to a public API the file has.

- **[low]** `hashPasswordSync` and `rehashPasswordOnLogin` both call `bcrypt.hashSync` — duplication suggests the abstraction wants to live somewhere else — `tests/fixtures/nextjs-auth/app/auth/login.ts:61-63, 100-102`
  - Two functions with identical bodies (`return bcrypt.hashSync(plain, 12)`)
    at the bottom of `login.ts`. The TypeScript-level concern is
    duplication; the deeper concern (sync hash on the request path) is
    performance/security territory and lives with those personas. From the
    language lens: if both functions exist for legitimately different
    reasons, name them clearly; if not, collapse them. The current naming
    (`rehashPasswordOnLogin`) suggests a feature that isn't wired up.
  - **Suggestion:** If `rehashPasswordOnLogin` is genuinely dead code,
    delete it. If it's a planned feature, add a `// TODO(#issue)` comment
    explaining when it'll be called and which hash-strength upgrade
    triggers it. The duplication is a smell either way.

#### Stage handoff notes

The two real bugs in this file are the missing `await` (route.ts) and the
discriminated-union opportunity (login.ts). The rest are hardening nudges
that wouldn't normally rise to a finding for a small PR — surfaced because
the file is a few hundred lines and the patterns are visible.

Adjacent observations: the `bcrypt.hashSync` duplication is principally a
perf concern (event-loop blocker — `team-performance-reviewer`'s lane
normally, but they weren't cast for this scope); the `localStorage` write
at `session.ts:46-53` is a security finding (`team-security-reviewer`) that
I deliberately did not surface from this lens — the TS-level pattern
(`if (typeof window !== "undefined")`) is the SSR-safety idiom, which is
correct in TypeScript terms; the security implication is the next reviewer's.
The missing schema parse on `route.ts:9` (`request.json()` flowing into
`login(body)` with no validation) is principally `team-backend-reviewer`'s
concern #1.

### peer-sql-reviewer (claude-haiku-4-5-20251001)

**Verdict:** approve · **Score:** 9/10

> Migration is structurally sound — types, constraints, and FK behavior are
> all explicit and correct. Single nit: the FK on Session.user_id has no
> index, which will cost on lookup-by-user queries.

#### Findings

- **[medium]** Missing index on `Session.user_id` despite the FK — `tests/fixtures/nextjs-auth/prisma/migrations/20260301_add_users.sql:14-24`
  - The `Session` table declares `Session_user_id_fkey FOREIGN KEY ("user_id") REFERENCES "User"("id") ON DELETE CASCADE`,
    which is correct as a constraint. Postgres does **not** auto-index
    foreign-key columns on the child side — only the parent's PK is
    indexed automatically. Any query that reads sessions by user
    (`SELECT * FROM "Session" WHERE user_id = $1`) does a sequential scan;
    any cascade delete on a User does the same. At low row counts this is
    invisible; at 100k+ rows it's a multi-second scan per request. The
    fixture's own comment at line 27 acknowledges this: "NO index on
    Session.user_id despite the FK — common gap, queries by user_id will
    scan." Note: the `User.email` UNIQUE constraint creates an implicit
    index, so email lookups are fine.
  - **Suggestion:** Add `CREATE INDEX "Session_user_id_idx" ON "Session"("user_id");`
    to the migration. If the workload also filters by `expires_at` to
    find unexpired sessions for a user (likely, given `findSession`
    filters at `session.ts:61`), consider a composite:
    `CREATE INDEX "Session_user_id_expires_at_idx" ON "Session"("user_id", "expires_at" DESC);`.
    The composite supports `WHERE user_id = ? AND expires_at > NOW()`
    with an index range scan and is the index `team-database-reviewer`
    will probably recommend explicitly.

#### Stage handoff notes

Migration is otherwise textbook: `UUID` PKs with `gen_random_uuid()`
defaults, `TIMESTAMPTZ` for timestamps, explicit `ON DELETE CASCADE` on
the FK (the team chose; the default would have been `RESTRICT` and would
have surprised them). Naming is consistent (Prisma-default PascalCase
tables, snake_case columns — that's idiomatic for Prisma's generator).
No `DROP COLUMN`, no `RENAME`, no destructive operations. The migration
is reversible — a `DOWN` would simply `DROP TABLE` both.

Tone-down: I didn't flag the absence of `IF NOT EXISTS` on the
`CREATE TABLE` statements because Prisma's migrate runner already
handles partial-run idempotency at the generator level; that would be a
generic SQL-style nit rather than a Prisma-aware one. The composite-index
rationale is `team-database-reviewer`'s lens, not mine — flagging the gap
is enough from this stage.

### peer-quality-engineer (claude-sonnet-4-6)

**Verdict:** concerns · **Score:** 4/10

> tests/auth.test.ts has exactly one happy-path assertion. Invalid creds,
> expired sessions, unknown emails, validation edge cases — all uncovered.
> A regression in any failure path ships silently.

#### Findings

- **[high]** Only happy-path test in scope — failure paths entirely uncovered — `tests/fixtures/nextjs-auth/tests/auth.test.ts:36-42`
  - The test suite has a single `describe("login (happy path only)")`
    block with one assertion: `expect(result.ok).toBe(true)`. The
    production code in `login.ts` has at least four failure paths the
    test does not exercise: (1) `validateInput` returns "email required"
    / "password required" / "password too short" — the test never sends
    invalid input; (2) `findUser` returns `null` for unknown emails — the
    test never queries an unknown email; (3) `verifyPassword` returns
    `false` for wrong passwords — the test always returns `true` from
    the bcrypt mock; (4) the route handler maps `r.ok === false` to a
    401 with `{ error }` — that response shape has zero coverage. A
    regression in any of these paths would compile, pass the test
    suite, and ship silently. The persona-level note in the test file's
    docstring ("DELIBERATELY THIN. Only happy path covered. The Quality
    Engineer persona should flag this.") confirms the gap is recognized —
    the finding is not "you missed something" but "you marked the gap and
    need to close it."
  - **Suggestion:** Add per-failure-path tests, one per branch in the
    source: `it("returns ok=false with 'email required' for missing email")`,
    `it("returns ok=false with 'password too short' for password.length < 8")`,
    `it("returns ok=false with 'invalid credentials' for unknown email")`,
    `it("returns ok=false with 'invalid credentials' for wrong password")`.
    Use `vi.mocked(bcrypt.compare).mockResolvedValueOnce(false)` to flip
    the verify result per test. Add an assertion that the `error` field
    is set on each `ok: false` path. Total cost: ~40 lines of test code,
    closes the largest single quality gap in the diff.

- **[medium]** No edge-case tests for `validateInput` — empty strings, unicode, very long passwords — `tests/fixtures/nextjs-auth/app/auth/login.ts:27-38, tests/auth.test.ts (absent)`
  - `validateInput` does shape-and-length checks: type-of-string,
    non-empty, password ≥ 8 chars. The boundary cases — `password === ""`
    (empty string, falsy under `!input.password`), `password === "1234567"`
    (7 chars, exactly at the boundary), `password === "12345678"` (8
    chars, exactly passes), unicode passwords (emoji, multi-byte chars
    where `.length` is byte-count, not codepoint-count), pathologically
    long passwords (10MB string — does bcrypt handle it? does the
    upstream parser cap body size?) — none have a corresponding test.
    The boundaries are where bugs live: `> 8` vs `>= 8` is a one-character
    edit that flips production behavior, and the test suite would not
    notice.
  - **Suggestion:** Add a parametrized test:
    `it.each([['', 'password required'], ['1234567', 'password too short'], ['12345678', null], ['😀😀😀😀', 'password too short']])("validates password '%s' as '%s'", ...)`.
    The unicode case is particularly important if the password ever flows
    through bcrypt — bcrypt truncates at 72 bytes, and a unicode-heavy
    password near that boundary is a known footgun.

- **[medium]** Test mocks Prisma at the module level, coupling test order to import order — `tests/fixtures/nextjs-auth/tests/auth.test.ts:9-27`
  - `vi.mock("@prisma/client", ...)` at the file's top level intercepts
    the Prisma import for the entire test file. The mock is a fixed
    function that returns the same hard-coded data on every call. Two
    consequences: (1) tests that need *different* mocked data have to
    either reset the mock per-test (`vi.mocked(...).mockResolvedValueOnce(...)`)
    or share the same fixture, which couples them; (2) the mock factory
    runs before the source module, so any source-side Prisma client
    construction with side effects (constructing a connection) wouldn't
    be exercised. For a single happy-path test this is fine; for the
    failure-path tests recommended above, the team will hit this
    constraint immediately.
  - **Suggestion:** Restructure the mock to expose handles for per-test
    overrides:
    `const mockFindUnique = vi.fn(); const mockSessionCreate = vi.fn(); vi.mock("@prisma/client", () => ({ PrismaClient: vi.fn(() => ({ user: { findUnique: mockFindUnique }, session: { create: mockSessionCreate } })) }));`.
    Then each test does `mockFindUnique.mockResolvedValueOnce({...})` for
    its own scenario. Alternatively, dependency-inject the Prisma client
    into `login` (architecturally cleaner — `lead-senior-architect`'s
    lens, not mine — but worth flagging the testability constraint here).

- **[medium]** No integration test exercising the actual route handler — `tests/fixtures/nextjs-auth/app/auth/route.ts (no corresponding test file)`
  - The unit test calls `login()` directly. The production code path is
    `request → POST handler → login() → response`, and the handler at
    `route.ts` has its own bugs (the missing `await`, the cast). A unit
    test of `login` proves the business logic; an integration test of
    `POST` proves the wiring. The two are not redundant — the bugs the
    peer-typescript reviewer flagged in the route handler would not
    surface in the current test suite because no test ever exercises the
    handler.
  - **Suggestion:** Add `tests/auth.route.test.ts` with
    `it("returns 200 + token for valid credentials", async () => { const req = new Request("http://localhost/auth", { method: "POST", body: JSON.stringify({ email, password }) }); const res = await POST(req); expect(res.status).toBe(200); ... })`.
    Add a parallel test for the 401 path. This is where the missing-await
    bug manifests — the unhandled rejection becomes a test failure, which
    is the right outcome.

#### Stage handoff notes

The single biggest gap in this PR is the test-coverage shape — one
happy-path test for a handful of failure paths and a route handler with
non-trivial wiring. Adjacent observations: the `bcrypt.hashSync` perf
concern lives with the security/backend reviewers; the localStorage
finding is security's; the route-handler bugs are TS peer's. I'd note that
the test file's own docstring acknowledges the gap ("DELIBERATELY THIN") —
the team knows. The finding here is the recommendation to close it, not a
callout that nobody noticed.

What I deliberately did not flag: the test framework choice (Vitest) is
fine and standard for the stack; the mock factory pattern is conventional;
the `describe`/`it` naming is clear. The single missing piece is breadth.

## Stage 2 — Cross-functional

### team-security-reviewer (claude-sonnet-4-6)

**Verdict:** block · **Score:** 3/10

> Session token is written to localStorage (any same-origin XSS reads it;
> 7-day account takeover); /auth has no rate limit (credential stuffing at
> line rate); bcrypt.hashSync on the request path is a DoS amplifier.
> Critical finding alone blocks merge.

#### Findings

- **[critical]** Session token written to `localStorage`; readable by any same-origin script (XSS-to-account-takeover) — `tests/fixtures/nextjs-auth/app/auth/session.ts:46-53`
  - `persistSessionToken` stores the raw 32-byte session token in
    `window.localStorage`, which is readable by any script running on
    the page (first-party code, third-party analytics or ad scripts, or
    an injected XSS payload). Any reflected/stored XSS on this origin
    escalates to full account takeover because the token grants the same
    access as the user's password until expiry (7 days per `session.ts:22`).
    Threat model — Asset: user session token; Threat: token theft via
    XSS or third-party script reads `localStorage`; Impact: account
    takeover, persistent for up to 7 days, with no client-side rotation;
    Likelihood: medium-to-high for any production app that ever renders
    user-generated content (which is most auth-gated apps once they grow
    past landing pages).
  - **Suggestion:** Stop writing the token to `localStorage`. Set the
    token server-side as an `httpOnly + Secure + SameSite=Lax` cookie in
    the response (`Set-Cookie: session=...; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=604800`)
    so client JS cannot read it. Update `route.ts` to set the cookie via
    Next.js's `cookies().set('session', token, { httpOnly: true, secure: true, sameSite: 'lax', maxAge: 60 * 60 * 24 * 7 })`
    helper, and remove `persistSessionToken` and `readSessionToken` from
    `session.ts`. The server reads the cookie via `cookies().get('session')`
    on subsequent requests; client code never touches the token directly.

- **[high]** POST /login has no rate limiting; credential stuffing and brute force are unbounded — `tests/fixtures/nextjs-auth/app/auth/login.ts:72-94`
  - The `login` function has no per-IP or per-account rate limit. The
    fixture's own comment at `login.ts:68-70` acknowledges this ("This
    route has NO rate limiting"). An attacker can submit credentials
    from leaked breach lists at the request rate of the platform; the
    only constraint is bcrypt's hash cost (~250ms at cost 12), which
    still allows ~4 attempts/sec/connection and many in parallel. Threat
    model — Asset: user account population; Threat: credential stuffing
    with breach-list passwords; Impact: mass account takeover at line
    rate, especially against users who reuse passwords; Likelihood: high
    (every public login endpoint without a limit gets credential-stuffed
    within days of being indexed).
  - **Suggestion:** Add per-IP and per-account rate limiting on the
    `/login` route. For Next.js on Vercel, use `@upstash/ratelimit` with
    Vercel KV or Upstash Redis (works on Edge runtime — see `aims.md`
    constraint). Apply a per-IP cap of 5 attempts / 60s and a
    per-account cap of 10 attempts / hour, returning 429 with
    `Retry-After` once exceeded. Combine with progressive delay
    (exponential backoff per account) and CAPTCHA after threshold. Also
    consider account-lockout after 20 consecutive failures with a
    documented unlock procedure (email-based reset).

- **[high]** `bcrypt.hashSync` on the request path blocks the event loop and is a DoS amplifier — `tests/fixtures/nextjs-auth/app/auth/login.ts:61-63, 100-102`
  - `hashPasswordSync` and `rehashPasswordOnLogin` both call
    `bcrypt.hashSync(plain, 12)`, which blocks the Node event loop for
    100-200ms per call at cost 12. The crypto choice itself is correct
    (bcrypt at cost 12 satisfies concern #1). The bug is the synchronous
    variant on the request path — under any concurrent load, every other
    request waiting for the loop is starved for the duration of each
    hash. The security framing: this is a DoS amplifier. An attacker who
    cannot brute-force credentials (because of rate limiting, once
    added) can still degrade the service by sending parallel login
    attempts and starving the loop. Threat model — Asset: service
    availability; Threat: low-rate parallel logins exhausting the event
    loop; Impact: tail latency spike for all unrelated requests on the
    same worker; Likelihood: medium for a single-instance deploy, lower
    for autoscaled deploys but still material.
  - **Suggestion:** Use `await bcrypt.hash(plain, 12)` (the async
    variant) or, better, drop `hashPasswordSync` and
    `rehashPasswordOnLogin` from the request path entirely — password
    hashing should happen at signup or password-change time, not at
    login. The current usage at lines 61 and 100 looks like dead code or
    a planned re-hash on legacy-cost-factor users; in either case, the
    call should be `await bcrypt.hash(...)` and should be gated to only
    run when the existing hash uses an old cost factor (e.g.,
    `if (user.hash_cost < 12)`). On the verify side (`login.ts:81`),
    `bcrypt.compare` is already async — that's correct.

#### Stage handoff notes

Adjacent observations the lens saw but didn't flag: the missing schema
parse on `route.ts:9` is principally `team-backend-reviewer`'s lane
(concern #1 of theirs) with security adjacency (input-shape uncertainty) —
leaving the headline finding to backend to avoid duplication. The
plaintext storage of session tokens in the database (`session.ts:24-30`
writes `token` verbatim into `Session.token`) is a `medium`-severity
hardening gap (#14): a DB leak yields immediately-usable sessions.
Standard mitigation is to store `sha256(token)` and only ever expose
plaintext to the cookie; dropped from findings to keep the slot count to
three real exploits, but worth a follow-up.

TLS/HSTS/Secure-cookie enforcement is platform-level here (Next.js +
Vercel — the deploy target enforces HTTPS, HSTS); verify the deployment
target sets the right defaults. No SCA tooling visible in the repo (no
Dependabot, no `npm audit` in CI) — recommend adding one regardless of
this review's scope. The username-enumeration timing channel
(`login.ts:78` returns fast on user-not-found, slow after bcrypt on
user-found) is `low` severity and dropped from findings in favor of the
three above.

### team-backend-reviewer (claude-sonnet-4-6)

**Verdict:** concerns · **Score:** 6/10

> Route handler doesn't await login() so rejected promises become unhandled
> rejections; no schema parse at the boundary so any JSON body is accepted;
> error path has subtle enumeration potential. Three solid concerns; not a
> block.

#### Findings

- **[high]** Unhandled Promise rejection in route handler — `tests/fixtures/nextjs-auth/app/auth/route.ts:9-25`
  - `POST` calls `login(body)` without `await` and assigns the resulting
    Promise to `result`, then returns `result.then((r) => ...) as unknown as Response`.
    The TS peer raised the cast (lane: type safety); from the
    backend-correctness lens, the bug is what happens when `login`
    *rejects* — the rejection propagates out of the `.then` chain into
    the handler scope and surfaces as an unhandled Promise rejection.
    Next.js's runtime maps unhandled rejections to a 500 with no body
    and no logged context; the framework's own error envelope is
    bypassed entirely. Every external dependency `login` touches
    (Prisma, bcrypt) has a failure mode that triggers this path. The
    persona-level concern: the request lifecycle is not error-classified
    end-to-end. A handler that handles its own success path but defers
    failure handling to the runtime is not a complete handler.
  - **Suggestion:** Replace the `.then` chain with
    `try { const r = await login(body); ... } catch (err: unknown) { logger.error('login failed', { err, requestId }); return new Response(JSON.stringify({ error: 'internal_error', requestId }), { status: 500 }); }`.
    Inside the `try`, branch on `r.ok` to produce the 200 or 401
    response. The error envelope on the 500 path should match the shape
    of the 401 envelope — clients deserve a consistent error shape
    regardless of which layer threw.

- **[medium]** No schema validation at the request boundary — `tests/fixtures/nextjs-auth/app/auth/route.ts:9`
  - `const body = await request.json()` gives the handler an `any`-typed
    value, which is then passed straight to `login(body)`. The `login`
    function expects `LoginInput = { email: string; password: string }`,
    but TypeScript can't enforce that against a runtime JSON parse — and
    the function's `validateInput` only checks `email`/`password`
    field-level shape, not the overall shape (extra fields, nested
    objects, prototype-pollution payloads). The defense in depth that
    backend handlers should provide is a schema parse at the boundary
    that rejects any body the rest of the system isn't expecting.
  - **Suggestion:** Define
    `const LoginBodySchema = z.object({ email: z.string().email(), password: z.string().min(1) }).strict();`
    (the `.strict()` rejects unknown keys). Replace the body read with
    `const parse = LoginBodySchema.safeParse(await request.json()); if (!parse.success) return new Response(JSON.stringify({ error: 'invalid_request', details: parse.error.format() }), { status: 400 }); const body = parse.data;`.
    Now `body` is a typed `{ email: string; password: string }` and the
    handler has a defensive 400 response for any malformed input. Note:
    this also addresses the `team-security-reviewer` adjacency on input
    validation.

- **[low]** Error responses partially leak validation phase — `tests/fixtures/nextjs-auth/app/auth/login.ts:73-74, 77-78, 82-83`
  - `validateInput` returns specific error strings ("email required",
    "password required", "password too short") that flow through to the
    response body via `r.error`. These are clear and useful for
    legitimate clients, but they also distinguish "no email field" from
    "email field but wrong password" from "email field, password field,
    password too short" — three different states an attacker can probe
    to learn about your validation logic. The user-not-found and
    wrong-password paths correctly use the same `"invalid credentials"`
    message (good — no enumeration); the validation paths break that
    pattern. Minor concern, not a block — but worth flagging.
  - **Suggestion:** Generalize the validation responses: return
    `{ error: "invalid_request", code: "VALIDATION_FAILED" }` with no
    field-level detail in the response body. Keep the field-level detail
    in the server-side log (linked by `requestId`). The legitimate
    client knows the request was bad; the attacker doesn't get a free
    probe of the validator's branch shape.

#### Stage handoff notes

Adjacent observations: the response envelope is consistent within this
small surface (success: `{ userId, token }`, error: `{ error: string }`),
but the proposed 500 path I suggested introduces a new shape
(`{ error, requestId }`) that should align with the project's broader
error convention if one exists — not visible in this scope. The
connection-pool sizing concern (concern #10 of my lens) doesn't apply to
this scope: the Prisma client is constructed at module level in both
`session.ts` and `login.ts`, which is a different smell (two clients
instead of one) — flagging as a stage handoff for `lead-senior-architect`
because the architectural concern is "where should the Prisma client live
and who owns its lifecycle." The retry/idempotency concern (#3) doesn't
apply here: `login` is naturally idempotent (the same valid creds always
produce a session, the same invalid creds always fail). The pagination
concern (#5) doesn't apply: no list endpoints in scope.

### team-database-reviewer (claude-sonnet-4-6)

**Verdict:** approve · **Score:** 8/10

> Schema is sound, types are right, FK behavior is explicit. The one
> workload concern is the missing index on Session.user_id — peer-sql
> already flagged it; my contribution is the composite recommendation
> tied to the implied query shape.

#### Findings

- **[medium]** Composite index needed on `Session(user_id, expires_at)` for the actual query workload — `tests/fixtures/nextjs-auth/prisma/migrations/20260301_add_users.sql:14-24, app/auth/session.ts:58-67`
  - `peer-sql-reviewer` flagged the missing FK index at `Session.user_id`
    at the file level. The workload-level finding extends that: the
    implied query shape from `findSession` (`session.ts:58-67`) is a
    lookup by token, but the realistic query patterns for any auth
    system are *also* "find unexpired sessions for a user" (dashboard
    "your active devices" view, "sign out everywhere" feature,
    session-cleanup background job). All three filter on `user_id` AND
    `expires_at`. A single-column index on `user_id` supports the
    user-only filter but degrades to a scan-and-filter once `expires_at`
    is added; a composite `(user_id, expires_at DESC)` supports both
    efficiently with the same disk cost. Workload note: at 100k sessions
    and 10k users, an unindexed `WHERE user_id = ? AND expires_at > NOW()`
    query does a 10k-row scan per request (the average user's sessions);
    an indexed version is an O(log n) seek. The cost matters when the
    auth app grows past the demo-ready phase.
  - **Suggestion:** Replace the bare FK index recommended by
    `peer-sql-reviewer` with
    `CREATE INDEX "Session_user_id_expires_at_idx" ON "Session"("user_id", "expires_at" DESC);`.
    The leading column (`user_id`) handles the FK-cascade case (Postgres
    uses the leading column of a multi-column index for FK lookups). The
    `expires_at DESC` ordering supports "most recent unexpired session
    first" patterns. Optionally consider a partial index
    (`WHERE expires_at > NOW()`), but partial indexes with `NOW()` as a
    predicate are tricky in Postgres — the index doesn't update as time
    moves, so you'd need to rebuild it periodically. For a
    100k-session-scale app, the composite index is enough; the
    partial-index optimization can come if it's measurably justified
    later.

#### Stage handoff notes

Schema is otherwise clean — the workload-level concern is the index shape
(above), not anything fundamental. Adjacent observations not flagged as
findings: (1) the `Session.token` column is a `TEXT` type with a `UNIQUE`
constraint, which means Postgres maintains a B-tree index on the full
token string — fine for 64-character hex tokens, expensive if the team
ever switches to longer tokens or signed JWT-shaped strings; (2) the
migration has no `created_by` / `updated_by` audit columns, but for a
session table that's correct (sessions don't have an "actor who modified
them"); on the `User` table the absence is a `low`-severity audit-trail
nudge, dropped here. (3) no soft-delete strategy on either table — for
`User` and `Session` the standard pattern is hard-delete with cascade,
which is what the FK already does, so this is right. (4) connection-pool
sizing isn't visible in this scope; in a Vercel deployment Prisma
typically runs through Prisma Data Proxy or direct Postgres with each
function getting its own connection — that's the deploy concern
(`team-devops-infra-reviewer`'s lane normally), not mine. (5) no
pagination concern in this scope — no list endpoints reading sessions
yet; flag for the next phase if a "your active sessions" UI lands.

## Stage 3 — Leadership

### lead-senior-architect (claude-opus-4-7)

**Verdict:** concerns · **Score:** 6/10

> The auth module's surface is small and well-bounded — that's the right
> structural choice. The session-storage decision (localStorage)
> forecloses options the next phase will need; it's a 1-day fix that
> unblocks the production-ready criterion. Approve with revisions.

#### Findings

- **[high]** ADR-style: session storage decision forecloses production-ready and Edge-runtime options — `tests/fixtures/nextjs-auth/app/auth/session.ts:46-53, app/auth/route.ts:21-23`
  - **Context.** This PR establishes the auth module as a first-class
    boundary in the codebase. The decisions made here propagate forward —
    every future auth feature (logout, "remember this device", SSO, MFA,
    CSRF protection on cookie-mounted state changes, session revocation
    on password change) will inherit the storage choice made now. The
    session-storage decision is the highest-leverage architectural
    choice in the diff because it's the one that's hardest to walk back
    later: rotating a token is easy, switching the *transport* the token
    rides on touches every consumer.
  - **Decision (observed).** Session tokens are written to `localStorage`
    by `persistSessionToken` (`session.ts:46-53`). The route handler
    returns the token in the JSON response body (`route.ts:21-23`)
    rather than setting a cookie. The implicit architectural decision
    is: tokens are bearer-token-shaped (carried by the client, sent in
    headers or query params), client-readable, and managed by client JS.
  - **Consequences.**
    - *(good)* The auth module's surface is small (`login`,
      `createSession`, `findSession`, `persistSessionToken`,
      `readSessionToken`) and well-bounded. A new contributor could
      draw the box around `app/auth/` and label it correctly without
      ambiguity. The conceptual boundary corresponds to the module
      boundary — that's what concern #1 of my lens calls "real" rather
      than "nominal." Adding OAuth or MFA later slots into this module
      without redesign.
    - *(good)* The Prisma + bcrypt + crypto choices are within the
      playbook — no exotic libraries, no hand-rolled crypto, no
      architectural detours. The team is paying the standard
      auth-stack cost, not a vanity cost.
    - *(bad)* `localStorage` commits the system to a client-readable
      token model. This is incompatible with the "production-ready"
      success criterion as stated in `aims.md` (`team-security-reviewer`
      flagged the gap as `critical`). It also forecloses a list of
      future features: server-rendered pages that need to know the
      user's session can't read `localStorage` (it's a client-only
      API); CSRF protection becomes harder because the token isn't
      carried on the cookie; SSO and external auth flows that expect
      cookie-based handoff don't compose cleanly.
    - *(bad)* The Prisma client is instantiated at module level in
      *two* places (`session.ts:9` and `login.ts:10`), creating two
      clients per import. This forecloses the Vercel Edge runtime
      explicitly stated as a constraint in `aims.md` ("Must work on
      Vercel Edge runtime") because Prisma's standard client isn't
      Edge-compatible — the Edge path requires Prisma Data Proxy or
      `@prisma/adapter-neon`. Two clients also doubles the
      connection-pool footprint per cold start.
  - **Recommendation.** Approve with revisions. Move to httpOnly cookies
    before merge — it's a 1-day fix and the only one needed to unblock
    the security-reviewer's `critical`. Specifically: (a) replace
    `persistSessionToken` and `readSessionToken` with the framework's
    cookie helpers; (b) update `route.ts` to set the cookie via
    `cookies().set(...)` and stop returning the token in the JSON body;
    (c) update any client code that calls `readSessionToken` to instead
    rely on the server reading the cookie. Audit the
    Prisma-on-server-import pattern against the Vercel Edge constraint
    stated in `aims.md` — either explicitly opt out of Edge for this
    module (and document it in a comment), or migrate to the
    Edge-compatible Prisma adapter before the constraint becomes a
    deploy blocker. Both fixes are scoped, do not require redesign of
    the module's public surface, and leave the rest of the team's work
    intact.
  - **Alternatives considered.** A heavier rewrite (Auth0, Clerk,
    NextAuth.js) would address all of the above by outsourcing the auth
    boundary entirely, but it's outside the scope the PM stated — and
    the team has expressed the intent to own the auth flow. The lighter
    fix (cookies + Edge-compatible Prisma) is the minimum change that
    closes the structural gap.
  - **Suggestion:** See Recommendation above. The code-level changes
    are: drop `persistSessionToken` / `readSessionToken` from
    `session.ts`; in `route.ts`, replace the JSON `{ userId, token }`
    response body with
    `cookies().set('session', token, { httpOnly: true, secure: true, sameSite: 'lax', maxAge: 60 * 60 * 24 * 7 })`
    plus a JSON body of `{ userId }` only; on subsequent requests, read
    the cookie via `cookies().get('session')` and pass to `findSession`.
    For the Prisma-Edge audit, run a smoke test against the Edge runtime
    locally (`next build && vercel build`) and observe whether the auth
    route fails — if it does, migrate to `@prisma/adapter-neon`
    (compatible with the project's Neon Postgres datastore per
    `aims.md`).

#### Stage handoff notes

What I deliberately did not flag as architectural findings, even though
they are visible: (a) the Prisma double-instantiation (`session.ts:9` and
`login.ts:10`) is a small, contained smell — extracting a `lib/db.ts`
that exports a singleton client is the conventional fix and a 5-line
change; not enough to justify a separate ADR but worth pointing out
(above). (b) The `LoginResult` discriminated-union concern (raised by TS
peer) has an architectural shadow — modeling success and failure as a
tagged union makes the contract explicit and changes the shape of every
future auth feature that adds a new failure mode (account locked, MFA
required, password expired); the TS peer's finding is sufficient, no
separate architectural finding needed. (c) The test-architecture concern
(concern #11 of my lens — "is the system *built* such that good tests
can be written") is partially relevant: the module-level Prisma client
construction in `login.ts` makes mocking awkward and forces the test to
mock at the import-resolution layer; dependency injection at the `login`
function would let tests pass a stub client. The peer-quality-engineer
flagged the *symptom* (test mocks Prisma at module level); I'm noting
the root cause (no DI seam) for the next phase to weigh. None of these
rises to a finding for this PR's scope.

The architectural picture is clean once the storage decision is fixed.
The next phase should add: (1) a `lib/db.ts` Prisma singleton, (2) a
`Hasher` interface for bcrypt that both production code and tests can
substitute, (3) a documented deployment target (Edge or Node) so the
Prisma adapter choice is unambiguous. None of those are blocking for
this phase.

### lead-project-manager (claude-opus-4-7)

**Verdict:** concerns · **Score:** 5/10

> Phase scope is correctly narrow; on-aim work is solid. "Production-ready"
> criterion is falsified by the localStorage and rate-limiting gaps;
> "fast — sub-200ms p95" is at risk from sync bcrypt. Hold until the
> security gaps close.

#### Findings

- **[high]** Aim alignment grade: 5/10 — phase scope intact, two of four success criteria not yet met — `tests/fixtures/nextjs-auth/.review/aims.md, full diff`
  - **Aim alignment: 5/10**
  - **Scope: on-scope**
  - **Verdict: hold**
  - **Memo:** The phase scope is correctly narrow — auth-module rewrite,
    no OAuth, no MFA, no recovery flows. The PR stays inside scope (zero
    non-goal violations) and the SQL migration is solid. The aims state
    four success criteria; here is the per-criterion accounting after
    this PR:
    - **"Login is secure (no client-readable tokens, no timing attacks,
      rate limited)"** → **regressed.** Falsified twice —
      `team-security-reviewer` flagged a `critical` localStorage write
      (client-readable tokens, the explicit anti-pattern in the
      criterion's own wording) and a `high` missing rate limit (the
      third clause in the criterion's own wording). Timing-attack
      defense is partially in place (`bcrypt.compare` is constant-time,
      identical "invalid credentials" message for user-not-found and
      wrong-password); but the username-enumeration timing channel
      (`login.ts:78` fast path on user-not-found vs slow path after
      bcrypt on user-found) is `low`-severity and noted by security in
      stage handoff. The criterion is **two of three clauses red, one
      of three partial**.
    - **"Login is fast (sub-200ms p95)"** → **at risk, not measured.**
      `bcrypt.hashSync` on the request path (`login.ts:62, 101`) blocks
      the event loop for 100-200ms per call at cost 12; under any
      meaningful concurrency the p95 will be far above target. No
      load-test evidence in scope, so I can't confirm the target is met
      or missed — but the architectural shape suggests it'll be missed
      once concurrency arrives. Flag as `at-risk`, not `regressed`.
    - **"Failures fall back gracefully (clear UX, no broken state)"** →
      **partial.** The error envelope on the success-and-401 paths is
      consistent (`{ error: string }` for failures,
      `{ userId, token }` for success). The 500 path has no envelope at
      all because `team-backend-reviewer` flagged the unhandled
      rejection — that's a graceful-fallback gap. Once the route
      handler is fixed (see backend's recommendation), this criterion
      goes green.
    - **"Test coverage protects against regression"** → **regressed.**
      `peer-quality-engineer` flagged the only-happy-path test suite. A
      failure-path regression in `login` would compile, pass the test
      suite, and ship silently. Closing this criterion needs the test
      suite expanded (peer-quality's #1 recommendation).
  - **Phase completion estimate: ~50%.** Two of four criteria have a
    clear path to green within this PR's scope (security gaps via
    cookies + rate limiter; backend fix on the unhandled rejection);
    two need follow-up work (the test suite expansion is a small
    follow-up; "sub-200ms p95" needs a load test). On the structural
    side, `lead-senior-architect`'s "approve with revisions" supports
    landing this phase once the security fixes are in.
  - **Recommendation:** Hold the merge. Do not ship the auth flow with
    client-readable tokens — it explicitly violates a stated criterion
    the user wrote in their own words. The security fixes are a 1-2 day
    scope (cookies + rate limiter); the backend fix on the unhandled
    rejection is a half-day. After those land, the phase is green on
    three of four criteria with a clear path to the fourth via a small
    test-coverage follow-up. The structural choices (boundary, module
    shape, SQL migration) are the right ones to keep.
  - **Suggestion:** Sequence: (1) close the `team-security-reviewer`
    critical and high findings (cookies, rate limiter); (2) close the
    `team-backend-reviewer` high finding on unhandled rejection (await
    + try/catch in `route.ts`); (3) merge; (4) follow-up PR for test
    expansion (peer-quality-engineer's #1) and the perf concern (async
    bcrypt or move hashing off the request path) before closing the
    phase. Do not bundle (4) into this PR — that would expand scope and
    the sequencing of "close critical security gaps first" is correct.

#### Stage handoff notes

What I deliberately did not surface as findings, staying in the
aim-alignment lane: (a) the test-coverage gap is a real concern but its
alignment weight is captured in the per-criterion accounting above;
expanding it into a separate finding would duplicate
`peer-quality-engineer`. (b) the `lead-senior-architect`'s structural
concerns (Prisma double-instantiation, Edge-runtime audit) are real but
the aim alignment is at the "did this PR deliver the stated goal" level,
not the "is this the perfect architecture" level — the architect owns
that critique. (c) the user's `aims.md` deployment constraint ("Must
work on Vercel Edge runtime") is not yet falsified by this PR but is at
risk per the architect's note; flagging as a stage handoff because it
bears on the next phase's go/no-go. (d) prioritization concern: the team
is doing exactly the right phase order (auth before OAuth before MFA
before recovery); no prioritization finding. (e) reversibility: the
migration is forward-and-back-compatible (no `DROP COLUMN`, no
destructive operation), so if the schema turns out wrong, rolling back
is clean. Risk-tolerance is appropriate for the phase.

Communication note: when the security-fix PR lands, the user should
update `aims.md` with the actual cookie-based design decision (since
`localStorage` is now retired) so the next reviewer doesn't have to
re-derive context. The aims file is itself a living document; keeping
it in sync with the architecture saves future review cycles.

## Aims Snapshot

# Project Aims
_Generated by Crucible on 2026-05-10._

## What this project is
A Next.js + Prisma auth module rewrite, currently mid-development. The user
is rebuilding password-based authentication for a small SaaS app with the
goal of shipping production-ready code.

## Goal
Ship a secure, performant password auth flow for production users.

## Success criteria
- Login is secure (no client-readable tokens, no timing attacks, rate limited).
- Login is fast (sub-200ms p95).
- Failures fall back gracefully — clear UX, no broken state.
- Test coverage protects against regression.

## Non-goals / out of scope
- OAuth providers (separate phase)
- 2FA / MFA (separate phase)
- Account recovery flows (separate phase)

## Tech stack (detected)
- **Languages:** typescript, sql
- **Frameworks:** nextjs, prisma
- **Datastores:** postgres
- **Deployment:** vercel (assumed)

## Project type
web-app

## Constraints
- Must work on Vercel Edge runtime
- Database is Postgres (managed Neon)

---
_Last refreshed: 2026-05-10T14:30:00Z_

## Run Metadata

- **Plugin version:** 0.1.0
- **Wall-clock:** 312s (5m 12s)
- **Models used:** claude-sonnet-4-6, claude-haiku-4-5-20251001, claude-opus-4-7
- **Estimated cost:** $0.74
