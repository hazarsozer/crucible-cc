# Crucible Review — production-ready order management API hardening

_Review ID: 2026-05-10-1700-orders-api-hardening · Generated: 2026-05-10T17:05:48Z · Project: api_

## Final Verdict

**Score:** 3.4/10
**Verdict:** blocked

The aims state four production-readiness criteria; this PR fails all four. Graceful shutdown, observability (logs/metrics/traces), goroutine lifecycle, and p95 latency are each individually addressable, but collectively they show the service hasn't been built with production in mind yet. The architecture is straightforward to fix — a middleware wrapper plus a Server struct plus shutdown plumbing — but until that lands, the "production-ready" label is aspirational. Block: this needs a follow-up phase, not a green stamp.

## Executive Summary

The Go order-management service in `tests/fixtures/go-api/` is a small, readable codebase that clearly communicates intent — and equally clearly demonstrates that production-readiness is a phase the team has not yet entered. The aims declare four success criteria for this hardening phase: sub-100ms p95 latency, graceful shutdown on SIGTERM, observability via structured logs + RED metrics + traces, and clean goroutine lifecycle. Across eight personas, the committee converges on the same finding from different altitudes: each criterion is unmet, and the gaps are structural rather than incidental. The work the team has done so far is foundationally pointed at the goal — the right files, the right handler shapes, the right kind of monolithic service for the scale described — but the criteria the user explicitly wrote down do not bend to "we'll add it later"; they are the bar against which the phase is graded.

The headline issues are foundational. `http.ListenAndServe` is called directly with zero-value timeouts (Slowloris-vulnerable, no per-request budget — a known production-vulnerable pattern documented in Go's net/http godoc). `startBackgroundWorker` spawns an infinite goroutine with no cancellation hook, no done channel, no `WaitGroup` — the textbook leak pattern, and one the aims explicitly named in success criterion #4. The `OrdersHandler` issues an N+1 query against the `items` table — one round trip per order — and returns the entire result set with no pagination, making the p95 < 100ms target unreachable on any non-trivial dataset (the team-performance-reviewer's capacity memo: ~200 ms at 100 orders, ~2 s at 1k). Errors collapse to bare 500s carrying internal diagnostic strings to the client (`fmt.Sprintf("listOrders: %v", err)`), leaking implementation details and providing zero operator-side trace. There is no structured logging anywhere — only `log.Println` and `log.Fatalf` — meaning production logs are unsearchable in any centralized aggregator (Loki, ELK, CloudWatch). There is no `/healthz` or `/readyz`, so Kubernetes (named in the aims as the deployment target) has nothing to probe; no `/metrics`, so RED counters are invisible; no error tracker integration, so unhandled errors disappear into stdout and bare 500s.

The architect's view consolidates these into a single observation: there is no operational boundary in this service. Every cross-cutting concern (timeouts, logging, metrics, tracing, shutdown coordination, error classification, request validation, response envelope consistency) is currently absent. If those concerns are not centralized at a single boundary now, they will land separately and inconsistently across future PRs — drift accumulates faster than it can be cleaned up, and the team will revisit each handler twice instead of once. Two specific structural patterns drive this verdict: (1) the package-level `var db *sql.DB` declared in two unrelated files (`main.go:13` and `handler/orders.go:25`) with the handler-side instance never assigned — a structural admission that there's no clean DB-access discipline yet; (2) `startBackgroundWorker` showing there's no shutdown coordination — the same pattern will recur for every future async worker, and graceful shutdown becomes increasingly expensive to retrofit as more workers accumulate.

The PM's alignment grade (3/10) confirms this from the aim-alignment lens: the work is on-scope (the right files, the right area), but the user's own success criteria — production-readiness, observability, graceful shutdown, no goroutine leaks — are not partially met. They are absent. By the user's stated definition of done, this phase is currently 0% complete; not because no work has been done, but because the work that has been done does not yet address any of the four criteria the user wrote down. The recommended path forward is the architect's: a 2-3 day refactor introducing a `Server` struct (lifecycle ownership, holds `*sql.DB` and the shutdown context), a `withMiddleware` wrapper (timeout, request-id, logging, metrics, tracing, panic-recovery, all chained), and a propagated `shutdownCtx` plumbed through `main` → workers → handlers (so `srv.Shutdown(shutdownCtx)` actually drains in-flight requests and the workers exit on the same signal). Once that boundary exists, the lower-stage findings (N+1, `rows.Err()`, pagination, error classification) each land cleanly inside the new structure rather than as scattered fixes; the cost of the refactor is amortized across every future handler. Until that lands, the production-ready label is aspirational, and the right verdict is `blocked` for follow-up phase work — not `concerns` with a request to patch four independent gaps in this PR.

## What's Good

- The codebase is small, well-commented, and reads cleanly — every gap is intentional and documented in fixture comments rather than hidden. Onboarding cost is currently low; a new contributor can read the entire service in one sitting.
- The handler boundary is clear: `main.go` constructs the mux and registers two handlers; `handler/orders.go` and `handler/user.go` each own their endpoint without bleeding into each other. There is no shared mutable state across handlers (other than the unintentional duplicated `var db *sql.DB` declaration, which is its own structural concern).
- Request context (`r.Context()`) is correctly forwarded into `listOrdersWithItems` from `OrdersHandler` (line 30) — the call site honors context propagation even if the receiving function then loses the type. This is recoverable without touching the call site, which is the cleaner end of the fix to inherit.
- `defer rows.Close()` is correctly applied in `listOrdersWithItems` (lines 49, 71) — resource lifecycle within a single function is honored. The fixture demonstrates the right pattern at the right altitude; the bug is one level up (rows.Err()), not in the cleanup discipline.
- The schema choices (`Order` and `Item` structs with appropriate JSON tags on lines 12-24 of orders.go) are idiomatic Go: exported field names, consistent JSON tag casing (snake_case), `int64` IDs, `float64` for monetary `Total`/`UnitCost`. The data shape itself would survive scrutiny; what's missing is the workload-aware index strategy and the `NUMERIC`/`DECIMAL` discussion (a perf-reviewer note rather than a peer-reviewer one — `float64` for money is acceptable in many internal services and questionable in a payment path).
- The package layout (`main` + `handler/`) is appropriately minimal for a service of this size — no over-architecting, no premature abstraction, no `internal/` hierarchy that would force the team to navigate three levels of indirection for two endpoints. The architect's recommended refactor introduces `internal/server/` *because the service is now graduating to production*, not as a baseline structure.
- The aims file is clear and specific — the user has done the work of capturing what success means, which is what makes the alignment grade possible. Many projects ship without articulating their criteria; this one's are pinned to four bullet points with measurable conditions, and the project type, tech stack, and constraints are all explicit.
- Non-goals are correctly respected throughout: no auth code in the handlers (delegated to upstream gateway as stated), no caching layer introduced prematurely, no multi-tenancy provisions complicating the data model. The team is reading the aims and respecting the boundaries the user drew.

## What's Concerning

- **The HTTP server has no timeouts** (`ReadHeaderTimeout`, `WriteTimeout`, `IdleTimeout` all zero on `main.go:24`) — Slowloris attacks are wide open. A single slow client can hold a goroutine open with one byte per second; at scale the connection pool exhausts before any other failure mode triggers. team-network-reviewer flags this as `critical`.
- **No graceful shutdown** — `SIGTERM` drops in-flight requests immediately. Directly contradicts aims criterion #2 ("Graceful shutdown — in-flight requests complete on SIGTERM"). On Kubernetes (the named deployment target), every rolling restart truncates in-flight responses for the duration of the rollout.
- **`startBackgroundWorker` spawns a goroutine with no cancellation context** — textbook leak, and the same pattern will recur for every future async worker. Directly contradicts aims criterion #4 ("No goroutine leaks; long-running workers shut down cleanly"). The fixture comment on lines 33-34 even acknowledges the pattern.
- **N+1 query in `listOrdersWithItems`** — one query for orders (line 45), then one query per order for items (line 59). Latency scales linearly with order count. team-performance-reviewer's capacity memo: ~200 ms at 100 orders, ~2 s at 1k orders. Directly contradicts aims criterion #1 ("Sub-100ms p95 latency").
- **`rows.Err()` is never checked** after the `for rows.Next()` loop on line 73 — silent partial-result bug on a result-set error. The function returns `orders, nil` even if the iteration ended because of a network blip mid-scan; the OrdersHandler then encodes the partial slice as a 200 OK.
- **`ctx interface{}` typed parameter** on `listOrdersWithItems` (orders.go:44) defeats context propagation; cancellation can't reach the database driver, and even if it could, `db.Query` is used instead of `db.QueryContext` so the deadline never crosses the function boundary.
- **No structured logging anywhere** — `log.Println` and `log.Fatalf` only on `main.go:25-27`, no logger imported in handlers at all. Production logs are unsearchable in any centralized aggregator. Directly contradicts aims criterion #3 ("Observable — structured logs, RED metrics, distributed traces"). team-observability-reviewer flags this as `critical`.
- **No `/healthz`, no `/readyz`, no `/metrics` endpoints** — only `/orders` and `/user` are registered (`main.go:19-21`). Orchestrator probes have nothing to hit, RED metrics are unavailable, the p95 SLO has no observable counterpart. Directly contradicts aims criterion #3.
- **No error tracker integration** — unhandled errors disappear into stdout and bare 500 responses. New bug types accumulate without grouping or alerting; the operator finds out from customer complaints.
- **No request-body validation** at the handler boundary (`route.ts:9` has no schema parse before passing to business logic); **no authorization check on `OrdersHandler`** (returns all orders to any caller — though auth is delegated to upstream gateway per the non-goals, the handler still doesn't filter by authenticated user); **no pagination** (returns the full orders slice unconditionally — memory and bandwidth bomb at scale).
- **Error responses leak internal diagnostic strings** — `fmt.Sprintf("listOrders: %v", err)` in orders.go:32 and `fmt.Sprintf("lookup: %v", err)` in user.go:22 send the raw driver error message to the client. Internal hostnames, table names, stack-trace fragments — all flow to whatever is calling the API.
- **Package-level `var db *sql.DB` declared in two unrelated files** (`main.go:13` and `handler/orders.go:25`); the handler-side `db` is never assigned, which means the current code wouldn't even *run* against a real database. A structural admission that there's no clean DB-access pattern yet — the duplicate declaration is the symptom of the missing `Server` struct.
- **Test coverage is a single trivial constructor test** on `OrdersHandler`. `UserHandler`, `listOrdersWithItems`, the N+1 path, the `rows.Err()` gap, the goroutine in `startBackgroundWorker` — all untested. peer-quality-engineer flags this as `block` from their lens alone.
- **No request correlation IDs, no distributed tracing** — request lifecycle is uninspectable across handler boundaries. Even within a single service, "where did the time go for request X" has no answer; once the service fans out to the database (or any future downstream), tracing becomes the difference between minutes and hours of debugging time.
- **No connection pool tuning visible** — `database/sql` defaults (`MaxOpenConns: 0` unlimited, `MaxIdleConns: 2`) are conservative for production. Without explicit tuning, the service has no documented per-pod pool size; a fleet of 10 pods at default config can starve the database the moment traffic ramps.

## Key Notes from the Committee

### peer-go-reviewer
> rows.Err() is never checked after for rows.Next() so a truncated query silently returns partial orders as 200 OK. ctx parameter typed as interface{} instead of context.Context. Bare `return err` loses chain context, and startBackgroundWorker leaks a goroutine with no shutdown signal.

### peer-quality-engineer
> Test surface is one trivial constructor assertion against OrdersHandler. listOrdersWithItems, the N+1 path, the rows.Err() gap, UserHandler, and main.go's HTTP wiring are completely untested. Block: the production-readiness aim is incompatible with this coverage shape.

### team-backend-reviewer
> No graceful shutdown despite the aims explicitly requiring it; OrdersHandler accepts and serves any caller without an authorization check; every error collapses to 500 with internal diagnostic strings leaked to clients. The request lifecycle has no defensive boundary.

### team-network-reviewer
> http.ListenAndServe used with zero-value timeouts — Slowloris-vulnerable. db.Query used instead of db.QueryContext, so request deadlines never reach the driver. Both gaps are structural; once fixed, the missing graceful shutdown becomes addressable.

### team-database-reviewer
> Classic N+1 in listOrdersWithItems — one query for orders, then one per order for items. With N orders that's N+1 round trips. Compounded by package-level `var db *sql.DB` declared twice with the handler's instance never assigned — there's no clean DB-access discipline yet.

### team-observability-reviewer
> Service uses bare log.Println, registers no /healthz/readyz/metrics, and has no error tracker integration. On-call would be flying blind: failures show up only as opaque stdout strings or HTTP 500s with no operator-side trace.

### team-performance-reviewer
> N+1 in listOrdersWithItems adds ~200 ms at 100 orders / ~2 s at 1k. With the missing inbound timeouts and no connection pool tuning, the p95 < 100ms target is unreachable on any non-trivial dataset. The capacity math doesn't add up against the stated SLO.

### lead-senior-architect
> Decision: the service has no operational boundary — timeouts, shutdown coordination, error classification, observability, and worker lifecycle are each independently absent. Recommend extracting a Server struct + withMiddleware wrapper + propagated shutdownCtx before further handler work lands.

### lead-project-manager
> Aim alignment: 3/10. Scope: on-scope. Verdict: rescope. Phase scope is "production-ready order management API"; the PR stays in scope but does not deliver on any of the four stated success criteria. Three of four are not partially met — they're absent.

## Stage 0 — Profiler

### Project profile
- **Type:** api
- **Languages:** go
- **Frameworks:** net/http (stdlib)
- **Datastores:** postgres (via database/sql)

### Review scope
- **Kind:** production-readiness hardening
- **Description:** production-ready order management API hardening
- **Files:** tests/fixtures/go-api/main.go, tests/fixtures/go-api/handler/orders.go, tests/fixtures/go-api/handler/user.go, tests/fixtures/go-api/handler/orders_test.go, tests/fixtures/go-api/.review/aims.md

### Casting reasoning
The aims file declares four production-readiness criteria (sub-100ms p95 latency, graceful shutdown on SIGTERM, observability via structured logs + RED metrics + traces, no goroutine leaks) for a small Go HTTP service backed by Postgres via `database/sql`. The scope is entirely Go source plus one trivial test file. Stage 1 cast `peer-go-reviewer` (always when `*.go` files are in scope) and `peer-quality-engineer` (always when scope is non-trivial). Stage 2 expanded along the four criteria:

- **`team-backend-reviewer`** — server-side request lifecycle is the spine of a production API; if the request validation, error envelope, or response shape is wrong, the criteria around graceful operation and observability can't reach a clean state regardless of what the lower-stage personas catch.
- **`team-network-reviewer`** — the inbound timeout gap and outbound DB-call hygiene cross the production-readiness bar directly. Aims criterion #1 (p95 < 100ms) and #2 (graceful shutdown) both depend on this lens.
- **`team-database-reviewer`** — raw `database/sql` with visible N+1 and package-level `*sql.DB` patterns is exactly the workload-altitude lens this persona is for. Even without migration files in scope, the query topology and the connection-pool discipline are visible from the handler code.
- **`team-observability-reviewer`** — the aims explicitly call for structured logs + RED metrics + traces, naming all three. This is the persona that grades whether those are present, and the persona's verdict bar (`block` if a service ships operationally blind on a stated production criterion) lines up directly with the aims' criterion #3.
- **`team-performance-reviewer`** — the sub-100ms p95 SLO is explicit in the aims; capacity math against the N+1 and missing connection-pool tuning is the lens. Without this persona, the database-reviewer's N+1 finding stops at "round-trip count is bad" rather than "the SLO is unreachable at scale".

Stage 3 leadership is always cast: `lead-senior-architect` (synthesize structural patterns across the per-persona gaps; produce ADR-shaped findings the team can cite) and `lead-project-manager` (grade alignment to the four explicitly stated success criteria; the only persona with the user's own rubric as input).

Security review was deferred — auth is delegated to an upstream gateway per the aims' non-goals — and accessibility, frontend, and devops-infra are out-of-scope for a stdlib Go API. Privacy review was also skipped: no PII handling visible in scope, no compliance constraints stated. The casting deliberately under-fills rather than over-fills: every persona present has a direct line to a stated criterion or a peer-flagged pattern, and no persona is cast purely for completeness.

## Stage 1 — Peer Review

### peer-go-reviewer (claude-haiku-4-5-20251001)

**Verdict:** concerns · **Score:** 5/10

> rows.Err() is never checked after for rows.Next() so a truncated query silently returns partial orders as 200 OK. ctx parameter typed as interface{} instead of context.Context. Bare `return err` loses chain context, and startBackgroundWorker leaks a goroutine with no shutdown signal.

#### Findings

- **[high]** rows.Err() never checked after for rows.Next() loop returns partial results silently — `tests/fixtures/go-api/handler/orders.go:71-77`
  - The for rows.Next() loop ends and listOrdersWithItems returns orders, nil with no rows.Err() check. rows.Next() returns false on both end-of-results and mid-iteration errors (network blip, driver issue, server-side cancellation, statement timeout fired by the driver, replica failover mid-scan). Without rows.Err(), a truncated result set is indistinguishable from a complete one — the function returns whatever it managed to scan and the OrdersHandler encodes that partial slice as a successful 200 OK response. The bug is silent, intermittent, and load-correlated: it never fires under normal local development and starts firing in production exactly when the database is most stressed. The same pattern recurs on the inner `itemRows.Next()` loop (line 63-70) — a mid-iteration error there leaves an order with a partial item list, indistinguishable from an order that genuinely has fewer items.
  - **Suggestion:** Insert `if err := rows.Err(); err != nil { return nil, fmt.Errorf("iterate orders: %w", err) }` between the closing brace of the for loop on line 73 and the return on line 77. Apply the same fix to itemRows after the inner loop on line 70 — `if err := itemRows.Err(); err != nil { return nil, fmt.Errorf("iterate items for order %d: %w", o.ID, err) }`. Once the structured logger is in place (per team-observability-reviewer's recommendation), log the iteration error before returning so the operator sees the actual driver message in the structured log; the wrapped error returned to the caller becomes the API-facing 500.

- **[high]** Goroutine leak in startBackgroundWorker — no shutdown signal, no context cancellation — `tests/fixtures/go-api/main.go:35-42`
  - `startBackgroundWorker` spawns `go func() { for { doSomething() } }()` with no way to be told to stop. There is no context, no done channel, no WaitGroup. When the process is killed (SIGTERM, SIGKILL) the goroutine is terminated abruptly along with the process — but if the process keeps running and this function is called multiple times, the goroutines accumulate without bound. Even within a single process lifetime, the goroutine cannot be told "stop and clean up" — it just runs until the process dies, which is exactly the failure mode the aims criterion #4 names ("no goroutine leaks; long-running workers shut down cleanly"). The lifecycle ownership is also ambiguous: `main()` doesn't keep a handle to the goroutine, can't `wg.Wait()` for it, and has no way to confirm it stopped before the server shuts down. In a service with one worker this is mostly cosmetic, but the *pattern* will recur: the next worker (a queue consumer, a periodic refresher, a metrics flusher) will copy this shape and the team will retrofit shutdown coordination N+1 times.
  - **Suggestion:** Pass a `context.Context` into `startBackgroundWorker` and use `select { case <-ctx.Done(): return; case <-ticker.C: doSomething() }` inside the loop. Have `main()` create a context tied to a SIGTERM handler (`ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM); defer stop()`) and pass it in. The same context should drive `srv.Shutdown(ctx)` to coordinate worker and server shutdown — when SIGTERM fires, the worker exits its select on `<-ctx.Done()`, the server stops accepting new connections, and `srv.Shutdown` waits for in-flight requests to drain. Use a `sync.WaitGroup` so `main()` can wait for the worker to actually exit before the process returns.

- **[medium]** listOrdersWithItems uses ctx interface{} instead of context.Context — `tests/fixtures/go-api/handler/orders.go:44`
  - The function signature is `func listOrdersWithItems(ctx interface{}) ([]Order, error)`. Typing ctx as interface{} defeats the entire purpose of context propagation: the type system can no longer enforce that callers pass a real context, and the function cannot call ctx.Done() or pass ctx to db.QueryContext. The caller (OrdersHandler) is already passing r.Context() so a typed signature would work and is required for the function to actually thread cancellation/deadline through to the database driver.
  - **Suggestion:** Change the parameter to `ctx context.Context`. Then replace `db.Query(...)` on lines 45 and 59 with `db.QueryContext(ctx, ...)` so request cancellation and deadlines actually propagate to the database.

- **[medium]** json.NewEncoder errors discarded with `_ =` — failure mode is silently swallowed — `tests/fixtures/go-api/handler/orders.go:35`
  - `_ = json.NewEncoder(w).Encode(orders)` discards the encode error. The same pattern recurs in `handler/user.go:25`. Encode failures on a partially-written response body are recoverable (the handler can write a 500 if the response hasn't started, or log and abort) but are currently swallowed entirely. Combined with the absence of structured logging, an encoding failure leaves no trace at all.
  - **Suggestion:** Capture the error: `if err := json.NewEncoder(w).Encode(orders); err != nil { /* log and bail */ }`. Once a structured logger is in place (per team-observability-reviewer's findings) the log call becomes a one-liner. The fix is mechanical and applies to both handler files.

#### Stage handoff notes
The N+1 query pattern in listOrdersWithItems (lines 47-71) is visible but out-of-scope for me — flagged for team-database-reviewer and team-performance-reviewer at the cross-system altitude. The package-level `var db *sql.DB` at main.go:13 and orders.go:25 (declared twice, never assigned in the handler file) is a structural concern for lead-senior-architect. Missing graceful shutdown is borderline between idiom (mine) and operational concern (team-network-reviewer / lead-senior-architect); I've surfaced the goroutine-leak side under #5 and left the broader shutdown pattern to Stage 2/3. SQL injection on the raw query strings would be team-security-reviewer's lens, but auth and security are non-goals per the aims (delegated to upstream gateway).

### peer-quality-engineer (claude-sonnet-4-6)

**Verdict:** block · **Score:** 2/10

> Test surface is one trivial constructor assertion against OrdersHandler. listOrdersWithItems, the N+1 path, the rows.Err() gap, UserHandler, and main.go's HTTP wiring are completely untested. Block: the production-readiness aim is incompatible with this coverage shape.

#### Findings

- **[high]** orders_test.go is a trivial constructor test; OrdersHandler, listOrdersWithItems, and the N+1 path are untested — `tests/fixtures/go-api/handler/orders_test.go:1-end`
  - The single test in orders_test.go asserts that calling `OrdersHandler` with a basic `httptest.NewRecorder` and a `httptest.NewRequest` does not panic. That is the entire test surface for the orders endpoint. The actual contract — that `listOrdersWithItems` returns the right shape, that the inner loop handles per-order item joins correctly, that the function distinguishes "no rows" from "rows.Err() returned mid-iteration" (peer-go-reviewer's finding), that the handler renders 500 on backend failure, that the JSON shape matches `[]Order` with the expected fields — none of it is exercised. Aims criterion #4 ("no goroutine leaks; long-running workers shut down cleanly") implicitly requires regression coverage to keep the leak fix from regressing; that test does not exist either. For a service whose stated phase is "production-ready hardening", a one-test surface is incompatible with the bar. Worse: when the architect's recommended `Server` struct refactor lands, the existing test won't even continue to compile (the construction shape changes), which signals that there's nothing of value to preserve and the test surface has to be rebuilt from scratch. Better to do that rebuild deliberately as part of the refactor than to discover it incidentally when CI breaks.
  - **Suggestion:** Add table-driven tests against `listOrdersWithItems` using a `*sql.DB` backed by `sqlmock` (or `pgxmock` if migrating). Cover: (a) two orders with items each (success); (b) zero orders (empty slice); (c) inner item-query fails on the second iteration (error wrapping check — verifies `fmt.Errorf("query items: %w", err)` recommended by peer-go-reviewer); (d) `rows.Err()` returns a network-blip error after some rows have scanned (this is the silent-failure case peer-go-reviewer flagged — the regression test for the fix); (e) ctx cancellation mid-iteration verifies that `db.QueryContext` actually honors the deadline once the `ctx interface{}` typo is fixed; (f) once the N+1 is collapsed to a single batched query (per team-database-reviewer / team-performance-reviewer), a regression test for the IN-clause shape that catches future reintroduction of the loop. Each test runs in milliseconds and pins a real contract.

- **[high]** UserHandler has no test at all — `tests/fixtures/go-api/handler/user.go:13-26`
  - `handler/user.go` ships with zero test coverage. The `UserHandler` validates the `id` query parameter, calls `lookupUser`, and renders JSON. None of the three branches (missing id → 400, lookup error → 500, success → 200) is tested. `lookupUser` is currently a stub but the handler around it is not — an `id` of `?id=` should still return 400 today, and that contract is unverified. The same one-finding-per-code-path framing as the orders gap above: this is one finding, fix one test file.
  - **Suggestion:** Create `handler/user_test.go` with three table-driven tests against `UserHandler`: (a) `?id=` (empty) → 400 with the expected body; (b) `lookupUser` returns an error (inject via interface or test seam) → 500; (c) `?id=alice` → 200 with `{"id":"alice","email":"alice@example.com"}`. Use `httptest.NewRecorder` and `httptest.NewRequest`; keep each test under 10 lines.

- **[medium]** No integration test for the HTTP server itself — `tests/fixtures/go-api/main.go`
  - `main.go` constructs a mux, registers two handlers, and calls `http.ListenAndServe`. None of this is exercised by an integration test. Even with handler-level tests in place, a regression in the routing wiring (e.g., a typo in `/orders` vs `/order`, a forgotten `mux.HandleFunc` for a new route, a misconfiguration of timeouts once they're added per team-network-reviewer's recommendations) would not be caught. Aims criteria #2 (graceful shutdown) and #3 (RED metrics on each route) both implicitly demand integration coverage to verify the cross-cutting middleware actually applies to the registered routes.
  - **Suggestion:** Add `cmd/server/server_test.go` (or extract main.go's wiring into a `NewServer(...) *http.Server` factory and test that). The test stands up the server on `httptest.NewServer`, fires requests at `/orders` and `/user` with mocked-DB backing handlers, asserts response status and shape, and (once shutdown is added per the architect's recommendation) drives a SIGTERM-equivalent context cancellation and verifies in-flight requests complete cleanly.

#### Stage handoff notes
The fixture's existing `orders_test.go` is genuinely trivial — the gap is foundational, not a polish concern. peer-go-reviewer flagged the unchecked rows.Err() and the goroutine leak in startBackgroundWorker; both should land with regression tests when the fixes do. The aims explicitly demand production-readiness, so deferring tests "to the next phase" isn't on the table. Block verdict reflects the gap between "phase is hardening" and "test surface is one constructor assertion" — these two are incompatible regardless of code quality elsewhere.

## Stage 2 — Cross-functional

### team-backend-reviewer (claude-sonnet-4-6)

**Verdict:** concerns · **Score:** 4/10

> No graceful shutdown despite the aims explicitly requiring it; OrdersHandler accepts and serves any caller without an authorization check; every error collapses to 500 with internal diagnostic strings leaked to clients. The request lifecycle has no defensive boundary.

#### Findings

- **[high]** No graceful shutdown — SIGTERM drops in-flight requests despite explicit aims criterion — `tests/fixtures/go-api/main.go:23-28`
  - `http.ListenAndServe(":8080", mux)` is called directly with no signal handling, no `srv.Shutdown(ctx)` invocation, no in-flight-request draining. The aims file explicitly lists "Graceful shutdown — in-flight requests complete on SIGTERM" as success criterion #2. The current code does not partially meet this criterion; it does not address it at all. On Kubernetes (named in the aims as the deployment target), every rolling-restart drops in-flight requests for the duration of the rollout. Customer-facing impact compounds with traffic — at 50 req/s and a 5-minute rollout window, that's ~15,000 requests served by pods that are about to die, each one returning a connection-reset to the client. Observed-from-the-outside this looks like flakiness; observed from the operator side it's a missing feature.
  - **Suggestion:** Replace the direct `http.ListenAndServe` call with an explicit `*http.Server` value, install a SIGTERM handler via `signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)`, run `srv.ListenAndServe()` in a goroutine, and on context cancellation call `srv.Shutdown(shutdownCtx)` with a 30s grace period. Also pass the same context into `startBackgroundWorker` so workers exit on the same signal. Pair with a `/readyz` endpoint that returns 503 once shutdown begins (per team-observability-reviewer) so the load balancer drains traffic before the HTTP server stops accepting new connections.

- **[high]** No request-body or query-parameter validation on either handler — `tests/fixtures/go-api/handler/user.go:14-18`
  - `UserHandler` reads `r.URL.Query().Get("id")` and checks string emptiness, but does not validate format, length, or type. `OrdersHandler` does not validate anything — it accepts any caller and returns the entire orders slice. For a production-bound API, the boundary check should be a schema parse (or, for query params, a typed validator) that rejects malformed input with a structured 400 response before business logic is reached. The current shape lets very long IDs, adversarial input, and arbitrary query strings flow into business logic without a defensive layer. Even with auth handled by the upstream gateway (per the aims' non-goal), the gateway only validates *who* is calling — *what* they're sending is still the application's responsibility. A malformed `?id=` value with a 10MB query string would currently flow into business logic before being rejected; a typed length cap at the handler boundary catches it cheaply.
  - **Suggestion:** Introduce a small validation helper per handler (or a generic `validate.Struct` helper if introducing a validation library is in scope). For UserHandler, validate that `id` matches a UUID or the project's user-ID regex with a max length. For OrdersHandler, validate any future query parameters (limit, cursor, status filter) against typed schemas. Return a 400 with `{"error":{"code":"invalid_request","message":"..."}}` on failure. Once the architect's `withMiddleware` wrapper exists, the validation layer can be standardized as one middleware that takes a schema and applies it before the handler runs.

- **[medium]** Error responses leak internal diagnostic strings via fmt.Sprintf — `tests/fixtures/go-api/handler/orders.go:32`
  - `http.Error(w, fmt.Sprintf("listOrders: %v", err), http.StatusInternalServerError)` returns a 500 with the raw error message ("connection refused", "EOF", or whatever the driver produced) in the response body. The same pattern recurs in `handler/user.go:22`. Internal error messages are operator-only signal; clients should see a generic message ("internal error, request id abc-123") and the operator should see the detailed message in structured logs (which don't yet exist per team-observability-reviewer's findings). Leaking internal diagnostic strings to clients is also a privacy concern (database table names, internal hostnames, stack-trace fragments) that compounds with no logger to redirect them to.
  - **Suggestion:** Introduce a `respondError(w http.ResponseWriter, err error)` helper that writes a structured JSON envelope with a stable error code and a generic message: `{"error":{"code":"internal_error","message":"unexpected server error","request_id":"..."}}`. Log the actual error with structured fields server-side. Use the helper from both handlers (and any future ones).

#### Stage handoff notes
The Stage 1 peer-go-reviewer flagged the unchecked rows.Err(), the ctx interface{} typo, the goroutine leak in startBackgroundWorker, and the bare return err pattern — all of those are layer-below findings I've read as evidence and not duplicated. The N+1 query pattern in orders.go:47-71 is correctly team-database-reviewer's lens. Inbound timeout configuration on http.ListenAndServe (Slowloris) is team-network-reviewer's call. The structural pattern across all my findings (no validation boundary, no graceful shutdown, no error-classification helper, no consistent response envelope) is something lead-senior-architect should consider as an architectural-altitude concern: every cross-cutting concern is currently absent and, if not centralized, will land separately and inconsistently across future PRs.

### team-network-reviewer (claude-sonnet-4-6)

**Verdict:** concerns · **Score:** 4/10

> http.ListenAndServe used with zero-value timeouts — Slowloris-vulnerable. db.Query used instead of db.QueryContext, so request deadlines never reach the driver. Both gaps are structural; once fixed, the missing graceful shutdown becomes addressable.

#### Findings

- **[critical]** http.ListenAndServe used directly with zero-value timeouts; server is Slowloris-vulnerable — `tests/fixtures/go-api/main.go:24`
  - `http.ListenAndServe(":8080", mux)` constructs an `http.Server` with `ReadHeaderTimeout`, `ReadTimeout`, `WriteTimeout`, and `IdleTimeout` all at zero — meaning no timeout. A slow-client (Slowloris) attack can open thousands of connections, send one byte per second, and exhaust the server's connection pool indefinitely. There is no per-request budget, no header-read budget, and no idle-connection reaper. The aims declare "p95 < 100ms" as a success criterion (criterion #1) — a single slow client hogs a goroutine and request slot indefinitely, blowing any p95 budget regardless of how fast normal requests are. The comment on lines 23-24 of main.go even acknowledges this is deliberate fixture breakage; it is also a real production-vulnerable pattern documented in Go's net/http godoc.
  - **Suggestion:** Replace with an explicit `*http.Server`: `srv := &http.Server{Addr: ":8080", Handler: mux, ReadHeaderTimeout: 5*time.Second, ReadTimeout: 30*time.Second, WriteTimeout: 30*time.Second, IdleTimeout: 120*time.Second}; log.Fatal(srv.ListenAndServe())`. Tune values per traffic pattern, but never leave them at zero. Add a graceful-shutdown path with `srv.Shutdown(ctx)` on SIGTERM (also coordinates with team-backend-reviewer's finding on graceful shutdown).

- **[high]** No timeout context on db.Query calls; slow database hangs the handler — `tests/fixtures/go-api/handler/orders.go:45`
  - `listOrdersWithItems` calls `db.Query(...)` on lines 45 and 59. Even if the caller passed a real `context.Context` with a deadline (which today it does not — see peer-go-reviewer's finding on the `ctx interface{}` typing), `db.Query` ignores it. Cancellation and per-request deadlines do not propagate to the database driver. A slow database (or a query that's blocked behind a long-running migration, or an upstream connection pool exhaustion) can hang the handler past the (currently absent) HTTP server `WriteTimeout` when one is added. The aims target p95 < 100ms; a single slow query without timeout protection blows the budget by orders of magnitude.
  - **Suggestion:** Switch both calls to `db.QueryContext(ctx, ...)`. After peer-go-reviewer's fix retypes the parameter to `context.Context`, the two changes compose cleanly: a request-scoped timeout (set via `context.WithTimeout(r.Context(), 50*time.Millisecond)` at the handler boundary) will then bound the database round-trip, and SIGTERM-driven cancellation will abort in-flight queries on shutdown.

- **[medium]** No retry policy or circuit breaker on the database dependency — `tests/fixtures/go-api/handler/orders.go:45-77`
  - There is no retry-with-backoff helper around the database calls and no circuit breaker for the broader handler. When the database is flaky (transient connection drops, brief replication lag spikes, network partitions to the primary), the handler currently surfaces every transient error as a hard 500 to the client. A retry-aware caller (the gateway, the SDK, the user's browser) will retry on the 500 with no help from the server, contributing to a thundering herd if the underlying issue is connection saturation. A circuit breaker would let the handler fail fast during an outage, free up goroutines, and avoid stampeding the recovering database.
  - **Suggestion:** For retries: either let the gateway handle them with idempotency keys (a forward-compatible choice with the aims' non-goal of authentication-via-gateway), or introduce a small retry wrapper for transient errors (`errors.Is(err, sql.ErrConnDone)` etc.) with exponential backoff and jitter. For circuit breaker: `sony/gobreaker` or similar around the database client, with the breaker open for ~30s on consecutive failures. Both are forward-compatible with the architect's recommended `Server` struct refactor.

#### Stage handoff notes
The lack of graceful shutdown (no srv.Shutdown(ctx) on SIGTERM, main.go:16-17 comment) is partly mine (server-config side) and partly team-backend-reviewer's (request-lifecycle side); we've each surfaced our angle. The goroutine leak in startBackgroundWorker (main.go:35-42) is peer-go-reviewer's lane. The N+1 in orders.go:59 is peer-sql-reviewer's / team-database-reviewer's. SQL injection risk on the raw query strings is out-of-scope (auth and security are non-goals per the aims, delegated to upstream gateway). The critical-severity timeout finding combined with the high-severity context-cancellation gap is what drives the score down to 4/10 — the aims' p95 target is unreachable without these timeouts in place.

### team-database-reviewer (claude-sonnet-4-6)

**Verdict:** concerns · **Score:** 3/10

> Classic N+1 in listOrdersWithItems — one query for orders, then one per order for items. With N orders that's N+1 round trips. Compounded by package-level `var db *sql.DB` declared twice with the handler's instance never assigned — there's no clean DB-access discipline yet.

#### Findings

- **[high]** Classic N+1 query pattern in listOrdersWithItems — one round trip per order — `tests/fixtures/go-api/handler/orders.go:47-71`
  - The function issues one query for `orders` (line 45) and then, inside the `for rows.Next()` loop, issues one additional query for that order's `items` (line 59). With `N` orders the total round-trip count is `N+1`. At 100 orders and ~2 ms RTT per query, that's ~200 ms of pure round-trip overhead before any actual query work. At 1000 orders, ~2 s. The pattern is the textbook N+1 bug, and the comment in the source even acknowledges it. The aims target p95 < 100ms — this query pattern alone makes that target unreachable on any non-trivial dataset. The workload analysis: the typical query shape for a list-orders-with-items endpoint is "find this user's recent orders, joined to their line items"; the right index for the orders table is composite `(user_id, created_at DESC)`, and the right query shape is either a JOIN with `ORDER BY orders.created_at DESC LIMIT N` and group server-side, or a two-step batch (parents then `WHERE order_id = ANY($1)` for children).
  - **Suggestion:** Replace the inner per-order query with a single batched query. After collecting orders into a slice, run `SELECT id, order_id, name, unit_cost FROM items WHERE order_id = ANY($1)` (Postgres) with the order IDs collected into a `pq.Int64Array`, then group items by `order_id` in a Go map and assign them back to the parent orders. Two queries total, regardless of N. Alternative: a single `LEFT JOIN orders/items` query with `ORDER BY orders.created_at DESC, items.id ASC` and group items by `order_id` server-side. Either form is forward-compatible with the index recommendations (composite `(user_id, created_at)` once user-scoped filtering is added). When the migration files for this schema enter scope in a future review, expect the database-reviewer to also flag the index as a workload-aware shape.

- **[medium]** Package-level var db *sql.DB declared in two unrelated files; the handler's db is never assigned — `tests/fixtures/go-api/handler/orders.go:25`
  - `main.go:13` declares `var db *sql.DB` and `handler/orders.go:25` declares another `var db *sql.DB`. Neither is initialized in the visible code, but the handler's instance is the one used by `listOrdersWithItems` — and there is no path that assigns it. In the fixture this is deliberate breakage, but the structural pattern is real and recurs in production code that grew organically: package-level connection state declared near where it's used, with the wiring left implicit. The right pattern — a `Server` struct that holds the `*sql.DB` and is passed into handlers via constructor injection — eliminates the duplicate-declaration concern and gives the team a single place to configure pool size, max idle conns, and connection lifetime.
  - **Suggestion:** Introduce a `Server` struct (or a `Handlers` struct) in `handler/` that holds `db *sql.DB` and exposes methods like `(h *Handlers) Orders(w, r)` and `(h *Handlers) User(w, r)`. Wire it up in `main.go` by constructing the DB once, passing it into `NewHandlers(db)`, and registering the methods on the mux. The package-level `var db` declarations go away, the duplicate name is no longer a footgun, and pool tuning lives in one place.

#### Stage handoff notes
peer-go-reviewer's finding on the unchecked `rows.Err()` (orders.go:71-77) is correctly the language-level lens. My N+1 finding is the cross-system performance angle on the same function. team-performance-reviewer will overlap on the latency math; the database lens is the round-trip count and the structural pattern, theirs is the wall-clock budget. No index recommendations from me here — the schema isn't in scope (no migration files, no `CREATE TABLE` visible), so the workload-aware index discussion (composite `(user_id, created_at)` for the typical "this user's recent orders" query, partial index on a soft-delete column if introduced) is deferred to when migrations enter scope. Connection pool tuning is also deferred; the package-level-var finding subsumes it for now (once a `Server` struct exists, pool config has a home).

### team-observability-reviewer (claude-sonnet-4-6)

**Verdict:** block · **Score:** 2/10

> Service uses bare log.Println, registers no /healthz/readyz/metrics, and has no error tracker integration. On-call would be flying blind: failures show up only as opaque stdout strings or HTTP 500s with no operator-side trace.

#### Findings

- **[critical]** Service uses standard log package with bare strings; production logs are unsearchable — `tests/fixtures/go-api/main.go:25-27`
  - The service emits `log.Println("listening on :8080")` and `log.Fatalf("server: %v", err)` — bare strings with no level, no service identifier, no fields. Handlers in `handler/orders.go` and `handler/user.go` follow the same pattern (no logger imported at all; errors flow through `fmt.Sprintf` into `http.Error`). The aims file declares "Observable — structured logs, RED metrics, distributed traces" as success criterion #3. None of these three are present. When this service ships to a centralized log aggregator (Loki, ELK, CloudWatch), every line becomes opaque text. On-call cannot query "errors for user X" or "all 500s in the last hour"; they grep by timestamp and hope. Worse, when handler errors become `http.Error(w, fmt.Sprintf(...))` on line 32 of orders.go, the error message is sent to the client AND lost from the operator's view — a true "silent failure factory" pattern. The criticality is amplified by the absence of error tracking (no Sentry/Honeybadger SDK initialized): a new bug type can recur 10,000 times in stdout before anyone notices a pattern. With structured logging plus an error tracker, the same bug surfaces once and groups by signature.
  - **Suggestion:** Adopt `log/slog` (Go 1.21+) at startup: `logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: slog.LevelInfo})); slog.SetDefault(logger)`. Replace `log.Println` / `log.Fatalf` with `slog.Info` / `slog.Error` using key-value fields: `slog.Info("server listening", "addr", ":8080")`. In handlers, log the error with structured fields before `http.Error`: `slog.ErrorContext(r.Context(), "list orders failed", "err", err, "route", "/orders")`. Initialize an error tracker SDK alongside (Sentry, Honeybadger, Bugsnag, or vendor equivalent) with environment, release, and traces sample rate; wrap the mux with a panic-recovery middleware that forwards err with request context (route, method, request_id, user if available) to the tracker before responding 500.

- **[high]** No /healthz, /readyz, or /metrics endpoints registered — `tests/fixtures/go-api/main.go:19-21`
  - The mux only registers `/orders` and `/user`. For a long-running service deployed to Kubernetes (named in the aims), this means orchestrators have nothing to probe for liveness/readiness (they'll restart-loop or never route traffic) and metrics scrapers have nothing to scrape. RED metrics (rate, errors, duration) per route, plus pool/queue saturation, are invisible — perf regressions and saturation events go undetected. Aims criterion #3 ("RED metrics") is directly contradicted; aims criterion #2 (graceful shutdown) cannot be verified without `/readyz` returning false during shutdown to drain traffic before the HTTP server stops. Without `/healthz`, the Kubernetes liveness probe defaults to "if the process is up, it's alive" — which it can't determine without an endpoint, so it falls back to TCP-level checks that pass even if the application is wedged. Without `/metrics`, the team-performance-reviewer's p95 < 100ms target has no observable counterpart: even if the latency is fine, no one can verify it; even if it regresses, no one notices until customer reports trickle in.
  - **Suggestion:** Register three additional handlers alongside `/orders` and `/user`: `mux.HandleFunc("/healthz", ...)` returning 200 with `{status, version, commit, uptime_seconds}` (cheap — just a counter increment and a static string); `mux.HandleFunc("/readyz", ...)` returning 200 only when the DB ping succeeds (cached ~5s to avoid hammering the database) and 503 during shutdown to enable in-flight draining; `mux.Handle("/metrics", promhttp.Handler())` using `prometheus/client_golang`. Wrap user-facing handlers with a middleware that increments `http_requests_total{route, method, status}` and records `http_request_duration_seconds` (histogram). Once the `Server` struct exists per the architect's recommendation, the metrics registry, health-cache state, and shutdown signal all live there.

- **[high]** No distributed tracing — request lifecycle is uninspectable across handler boundaries — `tests/fixtures/go-api/main.go:19`
  - Aims criterion #3 explicitly lists "distributed traces" alongside structured logs and RED metrics. There is no tracing SDK initialized at startup, no `traceparent` propagation, no spans on the database calls, no request-scoped trace context. Even within a single service this matters — when the orders endpoint takes 2 seconds, "where did the time go?" has no answer without spans. With outbound calls (the database, future downstreams), the absence of trace context means any cross-service slowness is opaque. The criterion is in the aims; the implementation is at zero.
  - **Suggestion:** Initialize OpenTelemetry at startup with the service name and version: `otel.SetTracerProvider(...)`. Wrap the mux with `otelhttp.NewHandler(mux, "orders-api")` to auto-instrument inbound requests. Add explicit spans around `db.QueryContext` calls (`tracer.Start(ctx, "db.query.orders")` ... `span.End()`). Set the OTLP exporter to push to whatever observability backend the team uses; tail-sampling is a tuning knob for later.

#### Stage handoff notes
Deferred to handoff: error-tracker integration (Sentry/Honeybadger/Bugsnag) — the absence is real but folded into the structured-logging finding above (without a logger there's no error context to attach to a tracker either); audit logging — fixture is read-only and auth is a stated non-goal, so audit isn't urgent here; log retention and dashboards — those are infra-side and team-devops-infra-reviewer's lane once application-side instrumentation is in place. peer-go-reviewer's unchecked rows.Err() (orders.go:71-77), goroutine leak (main.go:35-42), and ctx interface{} typing (orders.go:44) become observability-relevant: without an error tracker and without metrics, those silent failures and the leaking goroutine stay silent in production. The leak would manifest only in growing memory metrics — which this service doesn't emit, reinforcing the operational-endpoints finding. Block verdict: aims criterion #3 declares observability as a success criterion; the current implementation has logs (bare), no metrics, no traces — 1/3 of the criterion present at lowest possible quality, 2/3 absent.

### team-performance-reviewer (claude-sonnet-4-6)

**Verdict:** concerns · **Score:** 5/10

> N+1 in listOrdersWithItems adds ~200 ms at 100 orders / ~2 s at 1k. With the missing inbound timeouts and no connection pool tuning, the p95 < 100ms target is unreachable on any non-trivial dataset. The capacity math doesn't add up against the stated SLO.

#### Findings

- **[high]** N+1 query latency dominates p95; aims target p95 < 100ms is unreachable on any non-trivial dataset — `tests/fixtures/go-api/handler/orders.go:51-72`
  - Capacity memo: at 100 orders and ~2 ms DB RTT each, the inner `db.Query` loop adds ~200 ms to p95; at 1k orders, ~2 s. Wall-clock time on this endpoint is dominated by round-trip count, not query work. The aims explicitly target p95 < 100ms as success criterion #1 — at any non-trivial order count the math doesn't add up. team-database-reviewer flagged the N+1 from the workload angle; my angle is the cross-system latency budget. Even after the N+1 is fixed (collapsing N+1 round trips to 2), the latency budget is tight: 50ms DB + JSON encode + response serialization + (currently absent) middleware overhead is plausibly under 100ms, but only with disciplined other choices. The N+1 is the headline bottleneck; it is also a clean, mechanical fix.
  - **Suggestion:** Replace the inner per-order query with a single batched query (`SELECT id, order_id, name, unit_cost FROM items WHERE order_id = ANY($1)`) keyed off the parent order IDs, then group items by `order_id` in a Go map and assign back to the parents. Two queries total, regardless of N. Pair with a `LIMIT` on the outer orders query to bound the result set (see capacity-planning concern below; pagination is also team-backend-reviewer's lens).

- **[medium]** No connection pool tuning visible; sql.DB defaults are conservative for production — `tests/fixtures/go-api/handler/orders.go:25`
  - Capacity memo: Go's `database/sql` defaults are `MaxOpenConns: 0` (unlimited), `MaxIdleConns: 2`, `ConnMaxIdleTime: 0`, `ConnMaxLifetime: 0`. Under sustained load the unlimited `MaxOpenConns` lets the application open more connections than Postgres's `max_connections` (default 100) can serve — once that ceiling is hit, queries block on connection acquisition and tail latency spikes. The package-level `var db *sql.DB` (currently uninitialized in handler/orders.go:25) is also where this configuration would live. Without explicit tuning, the service has no documented per-pod pool size, and a fleet of 10 pods at default config can starve the database the moment traffic ramps.
  - **Suggestion:** Once the DB instance is wired up via the architect's recommended `Server` struct, configure the pool explicitly: `db.SetMaxOpenConns(25)`, `db.SetMaxIdleConns(25)`, `db.SetConnMaxIdleTime(5 * time.Minute)`, `db.SetConnMaxLifetime(30 * time.Minute)`. Tune the per-pod `MaxOpenConns` by dividing the database's `max_connections` budget (minus headroom for other services) by the expected pod count. Document the choice in a comment at the configuration site.

#### Stage handoff notes
Stage 1 (peer-go-reviewer) flagged unchecked rows.Err(), bare return err, and ctx interface{} — those are correctly the language-level lens. The `ctx interface{}` issue has a perf implication: even with a request deadline upstream, `db.Query` (no context) won't be cancellable when the client disconnects — wasted DB work and goroutine. team-network-reviewer flagged the missing inbound timeouts; combined with my finding on the N+1, the perf picture is: even after N+1 is fixed, the missing inbound timeouts mean a single slow client can hold a goroutine indefinitely, blowing p95 regardless of how fast happy-path requests are. team-observability-reviewer flagged the missing metrics — without `http_request_duration_seconds`, the team can't actually verify the p95 SLO is met or violated. After the headline bottleneck (N+1) lands, recommend a `pprof` profile of `/orders` under representative load to localize the next-tier bottleneck before further optimization. Capacity math against the aims' p95 target: 50ms DB (after N+1 fix) + 5ms JSON encode + 5ms middleware = ~60ms p50, plausibly ~80ms p95 with disciplined other choices. The current 200ms+ at 100 orders is a clear miss; the 60-80ms post-fix path is plausibly within the SLO.

## Stage 3 — Leadership

### lead-senior-architect (claude-opus-4-7)

**Verdict:** concerns · **Score:** 4/10

> Decision: the service has no operational boundary — timeouts, shutdown coordination, error classification, observability, and worker lifecycle are each independently absent. Recommend extracting a Server struct + withMiddleware wrapper + propagated shutdownCtx before further handler work lands.

#### Findings

- **[high]** Service has no defined operational boundary; cross-cutting concerns will drift across future PRs unless centralized now — `tests/fixtures/go-api/main.go:13-29`

    **Context.** The aims declare four production-readiness criteria (sub-100ms p95 latency, graceful shutdown, observability, no goroutine leaks) for a small Go HTTP service deployed to Kubernetes with Postgres backing and no in-process auth (auth is delegated to the upstream gateway per the non-goals). The phase scope is "production-ready order management API hardening" — i.e., the next milestone is the readiness bar, not new features. The codebase is small and clearly written, with two handlers and a single background worker, but every cross-cutting concern called out in the aims (and several adjacent ones flagged by the lower-stage personas — request validation, error envelope consistency, response shape, pagination) is currently absent.

    **Decision (observed).** The PR ships a monolithic `main.go` that constructs a mux, registers two handlers, calls `http.ListenAndServe` with zero timeouts, and spawns `startBackgroundWorker` as a fire-and-forget goroutine. There is no `Server` struct, no middleware abstraction, no shutdown coordination, no logger setup, no metrics registry, no error-classification helper, no request-id propagation. Each handler hand-rolls its own version of "what to do when something goes wrong" (`http.Error` with `fmt.Sprintf("%v", err)`) with no shared envelope, no shared error mapping, and no shared logging. The package-level `var db *sql.DB` is declared twice — once in `main.go:13` and once in `handler/orders.go:25` — and the handler-side declaration is never assigned, which means the current code wouldn't even *run* against a real database; the fixture is correct that this is a structural admission, not just a bug.

    **Consequences (good).** The codebase is small and easy to read; the handler boundary is clear (each endpoint has its own file, no shared mutable state besides the unintentional `var db`); the package layout is appropriately minimal for a service of this size — no over-architecting, no premature abstraction. The aims are clear and specific, which means the path from "current state" to "production-ready" is well-defined rather than open-ended.

    **Consequences (bad).** Three structural gaps compound:

    1. **No middleware abstraction** means timeouts, logging, metrics, tracing, request validation, panic recovery, request-ID generation, and rate limiting all have to be added per-handler — the team will forget some on each new endpoint, and the ones that *do* get added will drift in implementation across handlers (one logs `route` as a field, another as `path`; one wraps errors with `fmt.Errorf("%w")`, another loses the chain with `%v`). The lower-stage findings on inconsistent error envelopes, leaked diagnostic strings, and missing validation are all symptoms of this same missing pattern.
    2. **Package-level `var db *sql.DB` is duplicated** across `main.go:13` and `handler/orders.go:25`, and one of the two is never assigned — that's not just a bug, it's a structural admission that there's no clean DB-access pattern. The next handler will reinvent it (probably another package-level var, probably named differently, probably also never assigned correctly the first time). Connection-pool configuration has no canonical home; `SetMaxOpenConns`, `SetMaxIdleConns`, `SetConnMaxIdleTime` all need to live somewhere, and the team-performance-reviewer's recommendation to tune them implicitly assumes a place where they can be set.
    3. **`startBackgroundWorker` shows there's no shutdown coordination** — the same pattern will recur for every future async worker (job runners, queue consumers, periodic refresh tasks), and graceful shutdown becomes increasingly expensive to retrofit as more workers accumulate. By the time there are five workers running, retrofitting shutdown means touching five files plus main.go plus tests; doing it now means touching one file plus the boilerplate.

    **Forecloses.** A clean middleware-based fix without rewriting the existing handlers; a single place to configure the database pool, timeouts, and logger; the path from "current code" to "production-ready" being a refactor instead of a from-scratch rewrite. Specifically forecloses "land production-ready in one PR" if too many features are added before the boundary lands.

    **Recommendation.** Block. The graceful-shutdown gap and the missing observability are direct success-criterion failures; the N+1 + missing timeouts are p95-blockers. The aggregate is foundational, not incidental — the lower-stage personas correctly flagged the individual symptoms, but the fix is one architectural change that resolves all of them, not 8-10 independent fixes. Add: a `withMiddleware` wrapper covering timeout/logging/metrics/tracing/panic-recovery/request-id/validation, a `Server` struct holding `*sql.DB` and the worker context, and a `shutdownCtx` plumbed through main → workers → handlers. Estimated 2-3 days of focused work; smaller and more leverage than rebuilding piece-by-piece per handler. Once the boundary exists, the lower-stage findings (N+1, rows.Err(), pagination, error classification, validation, response envelope consistency) each land cleanly inside the new structure rather than as scattered fixes — and crucially, every future handler inherits the cross-cutting solution rather than reinventing it.

  - **Suggestion:** Refactor in this order:
    1. Create `internal/server/server.go` with `type Server struct { db *sql.DB; logger *slog.Logger; mux *http.ServeMux; tracer trace.Tracer }` and a `NewServer(...) *Server` constructor wiring up DB pool config (`SetMaxOpenConns`, `SetMaxIdleConns`, `SetConnMaxIdleTime`, `SetConnMaxLifetime`), slog with JSON handler, OpenTelemetry tracer, and the mux.
    2. Add `internal/server/middleware.go` with `withMiddleware(handler http.Handler) http.Handler` chaining timeout (`http.TimeoutHandler` or context-based) / request-id (read or generate `X-Request-ID`) / logging (request-scoped slog child) / metrics (`http_requests_total`, `http_request_duration_seconds`) / tracing (`otelhttp.NewHandler` wrapper) / panic-recovery (forward to error tracker, log, return 500 with structured envelope).
    3. Add `internal/server/lifecycle.go` with `Run(ctx context.Context) error` that runs `srv.ListenAndServe()` in a goroutine and awaits `ctx.Done()` to call `srv.Shutdown(shutdownCtx)` with a 30s grace period.
    4. Update `main.go` to construct a `signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)`, pass it to `srv.Run(ctx)`, and similarly thread it into `startBackgroundWorker(ctx)` so workers exit on the same signal.
    5. Move handler methods onto `*Server` (or a `*Handlers` sub-struct constructed from the server) so they have access to `s.db` and `s.logger` without package-level state.

    The diff is sizable but each step is mechanical; existing handlers move into the new structure with minimal logic changes, and the lower-stage findings (N+1 fix, rows.Err(), pagination, error classification, validation) each land as small focused PRs after the boundary is in place.

#### Stage handoff notes
Synthesized across: peer-go-reviewer's findings (rows.Err, ctx interface{}, goroutine leak, bare return err), peer-quality-engineer's coverage gaps, team-backend-reviewer's missing graceful shutdown + missing validation + error envelope leakage, team-network-reviewer's Slowloris-vulnerable timeouts and missing context-bound queries, team-database-reviewer's N+1 and duplicate package-level db, team-observability-reviewer's missing logs/metrics/traces, team-performance-reviewer's p95 math. Each of those findings stands at its own altitude; my altitude is that they collectively demonstrate one missing structural pattern: an operational boundary that owns lifecycle, cross-cutting concerns, and shared state. For the PM (lead-project-manager): the architect's recommendation (Server struct + middleware + shutdownCtx) is the right rescope. The PR's current work is foundationally aimed correctly — the issue is execution against the production-ready bar. The 2-3 day estimate makes this a single follow-up PR; alternatively a rescope of this PR if the team wants to land the readiness criteria in one go. For the Aggregator: the headline ADR (no operational boundary) consolidates 6 of the 8 personas' high-severity findings into one structural recommendation — quote it preferentially over the individual lower-stage findings.

### lead-project-manager (claude-opus-4-7)

**Verdict:** block · **Score:** 3/10

> Aim alignment: 3/10. Scope: on-scope. Verdict: rescope. Phase scope is "production-ready order management API"; the PR stays in scope but does not deliver on any of the four stated success criteria. Three of four are not partially met — they're absent.

#### Findings

- **[high]** PR is on-scope for the production-readiness phase but delivers against zero of the four stated success criteria — `tests/fixtures/go-api/.review/aims.md:11-14`

    **Aim alignment: 3/10. Scope: on-scope. Verdict: rescope.**

    **Memo.** The phase scope is "production-ready order management API". The PR stays in scope but does not deliver against any of the four stated success criteria:

    - **"Sub-100ms p95 latency"** — N+1 query (team-database-reviewer / team-performance-reviewer: ~200 ms at 100 orders / ~2 s at 1k orders) + no timeouts (team-network-reviewer: Slowloris keeps a single connection holding a goroutine indefinitely) make this implausible at any production load. Even the fast path is plausibly within budget only after the N+1 collapses and middleware overhead is bounded; the current path overshoots p95 by 100% or more on any real dataset.
    - **"Graceful shutdown — in-flight requests complete on SIGTERM"** — entirely absent. main.go calls `http.ListenAndServe` directly with no signal handler, no `srv.Shutdown`, no in-flight draining (team-backend-reviewer). On Kubernetes (the named deployment target), every rolling restart truncates in-flight requests; at 50 req/s and a 5-minute rollout that's ~15,000 requests served by pods that get killed mid-response.
    - **"Observable — structured logs, RED metrics, distributed traces"** — 0/3. Bare `log.Println` only (logs are unsearchable in any centralized aggregator), no `/metrics` endpoint registered (RED counters invisible, the p95 SLO has no observable counterpart), no tracing SDK initialized (cross-handler request flow is opaque). team-observability-reviewer's verdict is `block` from their lens alone, before any other persona's input.
    - **"No goroutine leaks; long-running workers shut down cleanly"** — `startBackgroundWorker` is a textbook leak: `go func() { for { doSomething() } }()` with no context, no done channel, no shutdown signal (peer-go-reviewer). The criterion was clearly written *for* this exact pattern, and the pattern is what got shipped.

    Three of four criteria are not partially met — they're absent. The architect's recommendation (a 2-3 day middleware + Server struct + shutdown context refactor) is the right rescope. The work the PR has done so far isn't wasted — it's foundationally correct in shape, just incomplete against the bar — but merging it as "production-ready" would set a precedent that disagrees with the user's own captured aims. The non-goals (multi-tenancy, authentication, caching) are correctly respected throughout, which is real signal that the team is reading the aims; the gap is execution against the success criteria, not direction.

    Recommend rescope: do the architect's refactor as the next phase before declaring "production-ready" anywhere. The current PR could merge as "foundation laid for production-readiness work, hardening continues in follow-up" if the user wants to track work-in-progress at a coarser grain than the success-criteria; otherwise, hold for the rescope.

    **Definition of done by the user's stated criteria.**

    - 0% currently — none of the four criteria addressed.
    - ~70% after the architect's refactor — criteria #2 (graceful shutdown), #3 (observability via middleware), #4 (worker lifecycle) substantially addressed.
    - 100% after the N+1 fix + LIMIT pagination + slog wiring + metrics middleware land in subsequent PRs.

    Realistic timeline: ~3 weeks of focused work to deliver the full phase honestly.

  - **Suggestion:** Two paths the user can choose between:

    **Path (a): Rescope this PR** to include the architect's recommendation (Server struct + middleware + shutdownCtx) — adds 2-3 days but makes the PR genuinely deliverable against the aims, and the per-criteria fixes (N+1 collapse, structured logging, /metrics endpoint, signal-driven shutdown) all land cleanly inside the new structure. The diff stays large but each piece is mechanical and the team gets a single shippable milestone.

    **Path (b): Merge this PR as "foundation for production-readiness"** with an updated `aims.md` clarifying that this is phase 1 of N, then file a follow-up PR for the architect's refactor and the per-criteria fixes.

    Either is honest; (a) is cleaner from a definition-of-done perspective and aligns with the originally captured aims, (b) is more incremental and lets the team ship working-but-not-production-ready code while the readiness work lands in parallel. Both require updating the aims if the team wants to ship before the criteria are met — currently `aims.md` says "production-ready" and this PR is not. The PM's recommendation: path (a) if 2-3 days fits the schedule; path (b) if the team has external pressure to ship something now and is willing to rewrite the production-ready label honestly.

#### Stage handoff notes
The architect (lead-senior-architect) consolidated the structural picture into one ADR (no operational boundary); their recommendation is the right rescope path and I'm endorsing it from the alignment lens. Aims are explicit and well-captured for this fixture (the user clearly stated the four production-readiness criteria); no aims-revision recommended unless the user is choosing path (b) above. The non-goals are correctly respected throughout — auth and security findings would be out-of-scope for alignment grading even if they were raised, because the aims explicitly delegate those to the upstream gateway. Definition of done for this phase, by the user's stated criteria, is currently 0% — none of the four criteria is even partially addressed. The architect's recommended refactor brings it to ~70% (criteria #2, #3, #4 substantially addressed; criterion #1 needs the N+1 fix on top); a follow-up PR addressing N+1 + LIMIT + structured logging finishes the phase. Three weeks of focused work, one PR per criterion-cluster, gets to the aims as written.

## Aims Snapshot

# Project Aims
_Generated by Crucible on 2026-05-10._

## What this project is
A Go HTTP service exposing order management endpoints. Currently a small monolith with the goal of being production-ready for a single team's internal use.

## Goal
Production-ready order management API with sub-100ms p95 and graceful operations.

## Success criteria
- Sub-100ms p95 latency for `/orders` and `/user`.
- Graceful shutdown — in-flight requests complete on SIGTERM.
- Observable — structured logs, RED metrics, distributed traces.
- No goroutine leaks; long-running workers shut down cleanly.

## Non-goals / out of scope
- Multi-tenancy (single team for now)
- Authentication (handled by upstream gateway)
- Caching layer (defer until measured need)

## Tech stack (detected)
- **Languages:** go
- **Frameworks:** net/http (stdlib)
- **Datastores:** postgres (via database/sql)
- **Deployment:** kubernetes

## Project type
api

## Constraints
- Must run as a single binary
- Must support container-orchestrated rolling restarts
- p95 < 100ms

---
_Last refreshed: 2026-05-10T14:30:00Z_

## Run Metadata

- **Plugin version:** 0.1.0
- **Wall-clock:** 348s (5m 48s)
- **Models used:** claude-sonnet-4-6, claude-haiku-4-5-20251001, claude-opus-4-7
- **Estimated cost:** $0.81
