# Crucible Review — full project review of Go order management API

_Review ID: 2026-05-11-1821-go-order-api-full · Generated: 2026-05-11T18:40:00Z · Project: api_

## Final Verdict

**Score:** 2.5/10
**Verdict:** Blocked

Every persona on the committee returned block and aim alignment from lead-project-manager is 2/10 — all four stated success criteria (sub-100ms p95, graceful shutdown, observability, no goroutine leaks) are either regressed or structurally absent. The decisive findings are mutually reinforcing: the package-level db var in handler/orders.go:21 is nil at runtime (every request panics), the N+1 query at handler/orders.go:55-70 makes the 100ms SLO mathematically unmeetable, http.ListenAndServe at main.go:15 has zero timeouts and no SIGTERM handling, and the startBackgroundWorker goroutine at main.go:32-41 leaks unbounded. The architect confirms: no operational boundary, no data-access layer, no observability seam.

## Executive Summary

This is a full project review of a Go HTTP order management API on net/http with a Postgres backend. The user's stated goal is production-ready operation with sub-100ms p95 latency, graceful shutdown on SIGTERM, structured logs plus RED metrics plus distributed traces, and no goroutine leaks.

The scope is foundationally aimed at the right problem and lead-project-manager confirms the intent matches the aims doc, but execution has not reached a state where any individual layer earned an approve. The only existing test is a struct-field smoke check with no behavioral value.

The concerning findings cluster around three structural failures: (1) the orders flow cannot succeed — db var is nil, N+1 with no LIMIT, ctx typed as interface{} so deadlines never reach the driver; (2) no operational boundary — zero HTTP timeouts, no graceful shutdown, no signal handling, background worker leaks; (3) all three observability criteria (structured logs, RED metrics, distributed traces) are entirely absent. This needs structural rework before it can be reconsidered for merge.

## What's Good

- The scope and intent match the aims doc — lead-project-manager confirms the PR is foundationally aimed at the right problem, even though execution falls short.
- The handler/main package split is a reasonable starting structure that can host the data-access layer and middleware seams the architect calls for.
- The N+1 root cause is concentrated in listOrdersWithItems — a single JOIN rewrite plus pagination resolves both the performance-reviewer and database-reviewer critical findings in one change.
- The Go peer reviewer findings (rows.Err omission, ctx typing, bare error returns) are individually small and mechanically addressable once the structural rework lands.

## What's Concerning

- `handler/orders.go:21` declares a package-level db that is never initialized — every /orders request will nil-panic at runtime, flagged as critical by both team-security-reviewer and team-backend-reviewer.
- The N+1 query pattern at `handler/orders.go:55-70` plus the missing LIMIT at line 46 make the sub-100ms p95 SLO mathematically unmeetable — team-performance-reviewer measures 200ms before any other overhead at 100 orders.
- `main.go:15` uses http.ListenAndServe with zero-value timeouts and no SIGTERM handling — directly contradicts the graceful-shutdown success criterion; startBackgroundWorker at `main.go:32-41` also leaks unbounded.
- All three observability criteria (structured logs, RED metrics, distributed traces) are entirely absent — no slog, no /healthz, no /metrics, no OpenTelemetry init — team-observability-reviewer calls this "zero on-call signal".
- Test coverage is effectively nil for production code paths — peer-quality-engineer returned block with score 2 because OrdersHandler, UserHandler, and every failure path are untested; the existing test asserts a struct field that can never fail.
- Aim alignment from lead-project-manager is 2/10 — all four stated success criteria are regressed or untouched; the architect confirms no structural home exists for any of them.

## Key Notes from the Committee

### lead-project-manager
> Aim alignment: 2/10. All four success criteria in aims.md (p95<100ms, graceful shutdown, observability, no goroutine leaks) are either regressed or entirely untouched. PR is foundationally aimed but execution is nowhere near production-ready.

### lead-senior-architect
> Service has no operational boundary (no lifecycle, no timeouts, no shutdown), no error-classification taxonomy, no shared data-access layer (db var declared per-package, never initialized), and no observability seam — every Stage 2 success criterion lacks a structural home.

### team-performance-reviewer
> N+1 at 100 orders = 200ms latency, 2x the 100ms SLO. No pagination. Context broken. SLO mathematically unmeetable as written.

### team-security-reviewer
> 500 error responses echo raw database error strings to callers; db is nil at runtime; uid query param flows to lookupUser with no sanitization; no rate limiting.

### team-network-reviewer
> http.ListenAndServe with zero-value timeouts; no graceful shutdown on SIGTERM; db.Query ignores context. All three are blockers for the stated production-ready Kubernetes goal.

### peer-quality-engineer
> The only test in scope is a struct field smoke test — neither handler has any test coverage. OrdersHandler, UserHandler, and all failure paths are completely untested.

## Stage 0 — Profiler

### Project profile
- **Type:** api
- **Languages:** go
- **Frameworks:** net/http
- **Datastores:** postgres

### Review scope
- **Kind:** full
- **Description:** full project review of Go order management API
- **Files:** main.go, handler/orders.go, handler/orders_test.go, handler/user.go, go.mod

### Casting reasoning
Pure Go stdlib API service with Postgres backend; no frontend, no ML, no IaC or CI files in scope, so frontend, accessibility, devops, privacy, and data-ML personas are skipped. peer-go-reviewer covers all .go source files; peer-quality-engineer covers source plus the one test file to assess coverage quality against the 80% minimum. team-security-reviewer casts by default and is especially relevant to the route handlers accepting untrusted input. team-backend-reviewer covers the HTTP route handlers and main server setup. team-network-reviewer is cast because the service exposes HTTP endpoints with graceful shutdown and timeout semantics — connection lifecycle is a first-class concern per the aims. team-database-reviewer covers the Postgres query code in the handlers. team-performance-reviewer is cast because the user's primary success criterion is sub-100ms p95 latency, making performance the most critical lens in the review. team-observability-reviewer is cast because the aims explicitly require structured logs, RED metrics, and distributed traces as success criteria. Both leadership personas receive all files per schema.

## Stage 1 — Peer Review

### peer-go-reviewer (claude-haiku-4-5-20251001)

**Verdict:** block · **Score:** 3/10

> rows.Err() unchecked after for rows.Next() returns partial result silently on error; ctx typed as interface{} instead of context.Context defeating propagation; startBackgroundWorker goroutine has no shutdown signal (unbounded leak); bare return err patterns lose context.

#### Findings

- **[high]** rows.Err() never checked after for rows.Next() loop; partial result returned silently on mid-iteration error — `handler/orders.go:73-77`
  - rows.Next() returns false on both end-of-results and mid-iteration errors. Without rows.Err(), a truncated result set is indistinguishable from a complete one — OrdersHandler encodes partial slice as 200 OK.
  - **Suggestion:** Insert rows.Err() check between closing brace of for loop and return. Wrap with fmt.Errorf.

- **[high]** startBackgroundWorker goroutine has no shutdown signal; unbounded leak when process runs — `main.go:32-41`
  - Function spawns goroutine that loops forever with no way to stop. Comment acknowledges the problem but goroutine stays in code.
  - **Suggestion:** Accept context.Context and check ctx.Done(), or delete entirely if unused.

- **[high]** listOrdersWithItems parameter typed as interface{} instead of context.Context, defeating type safety and propagation — `handler/orders.go:44`
  - Defeats type safety; function cannot call ctx.Done() or pass ctx to db.QueryContext. The ctx parameter exists but is unusable.
  - **Suggestion:** Change to context.Context and replace db.Query with db.QueryContext.

- **[medium]** Bare return err patterns lose context across the call stack — `handler/orders.go:47`
  - No error wrapping throughout. Caller sees only raw driver messages with no indication of which step failed.
  - **Suggestion:** Use fmt.Errorf with %w verb at each return site.

- **[medium]** json.NewEncoder(w).Encode error discarded — `handler/orders.go:40`
  - Encode failure returns 200 OK to the client with partial or malformed JSON body.
  - **Suggestion:** Check encode error and return 500 on failure.

- **[medium]** itemRows cleanup pattern is fragile; defer itemRows.Close() should be used instead — `handler/orders.go:67-70`
  - Multiple explicit Close() calls are fragile; adding an early return path risks a leak.
  - **Suggestion:** Use defer itemRows.Close() immediately after the error check on the itemRows.

#### Stage handoff notes
The N+1 query pattern is flagged for team-database-reviewer. HTTP server timeouts and graceful shutdown are out of scope here — team-network-reviewer owns those. Verdict is block due to rows.Err() miss (silent data loss), goroutine leak with no shutdown path, and ctx interface{} breaking context propagation entirely.

---

### peer-quality-engineer (claude-sonnet-4-6)

**Verdict:** block · **Score:** 2/10

> The only test in scope is a struct field smoke test — neither handler has any test coverage. OrdersHandler, UserHandler, and all failure paths are completely untested in a project explicitly targeting production readiness.

#### Findings

- **[critical]** OrdersHandler has zero test coverage; all branches and error paths are untested — `handler/orders.go:22-31`
  - OrdersHandler is the primary production endpoint and has no test whatsoever. At least three distinct exit paths exist; none are exercised.
  - **Suggestion:** Add httptest-driven tests: httptest.NewRecorder, mock db, assert status code and response body for success, DB error (500), and empty list (200 with empty array).

- **[high]** UserHandler has no test for any path — including the missing-id 400 branch and the lookup error 500 branch — `handler/user.go:13-29`
  - Both failure exits and the happy path are untested. The missing-id guard is the simplest validation test imaginable and is still absent.
  - **Suggestion:** Add three httptest sub-tests: no id param → 400, lookup error → 500, valid id → 200 with User JSON.

- **[high]** No test for rows.Err() omission — partial result sets silently return without coverage — `handler/orders.go:55-57`
  - No test drives a simulated mid-iteration DB error to confirm whether the function returns a partial slice or an error.
  - **Suggestion:** Add test that injects an iterator error; assert non-nil error returned (not a partial slice).

- **[medium]** Existing smoke test asserts a struct field with no behavioral or contract value — `handler/orders_test.go:5-10`
  - TestOrderStruct asserts that o.ID == 1, the value it just set. Can never fail unless Go struct literal syntax changes.
  - **Suggestion:** Replace with handler-level tests or at minimum a JSON serialization round-trip test.

- **[medium]** No integration test for the full request → handler → db → response flow — `main.go:14-22`
  - The mux wiring has no end-to-end test. Route registration bugs only surface in a real environment.
  - **Suggestion:** Add one integration test (build tag: integration) with httptest.NewServer and a test Postgres instance.

#### Stage handoff notes
N+1 and rows.Err() correctness bugs are owned by team-database-reviewer and peer-go-reviewer respectively. Graceful shutdown and server timeout gaps are for team-network-reviewer. The project has no coverage tooling configured — enforcing 80% minimum would require adding go test -cover to CI.

---

## Stage 2 — Cross-functional

### team-security-reviewer (claude-sonnet-4-6)

**Verdict:** block · **Score:** 3/10

> 500 error responses echo raw database error strings to callers (schema/internal-detail leak); db is nil at runtime (NilPointerDereference on every request); uid query param flows to lookupUser with no sanitization (future injection risk as stub is fleshed out); no rate limiting on either public endpoint.

#### Findings

- **[critical]** handler/orders.go db var is nil at runtime; every request panics and may expose stack trace to caller — `handler/orders.go:21`
  - Two independent var db *sql.DB declarations in different packages, neither initialized. Nil-pointer panic on every /orders request. Depending on Go version, the unrecovered panic may expose a stack trace with file paths and internal package names.
  - **Suggestion:** Remove duplicate var from handler/orders.go. Pass initialized *sql.DB from main.go via constructor (handler.NewOrdersHandler(db)). Add recovery middleware that logs panic server-side and returns a generic JSON error.

- **[high]** 500 responses echo raw db error strings and internal function names to HTTP callers — `handler/orders.go:27`
  - fmt.Sprintf("listOrders: %v", err) sends raw Postgres errors (e.g., "pq: column does not exist") and function names directly to callers. Schema info and service topology exposed.
  - **Suggestion:** Return generic JSON error body. Log full error with request ID server-side. Never include err.Error() in the HTTP response body.

- **[high]** uid query parameter passed to lookupUser with no type or format validation; injection surface when stub is replaced — `handler/user.go:14-20`
  - Current stub is safe but when replaced with a real DB lookup, raw string injection is possible. The parameter is never validated for format (integer, UUID, etc.).
  - **Suggestion:** Enforce expected shape at handler boundary: strconv.ParseInt or uuid.Parse before passing to business logic. Return 400 on failure.

- **[medium]** Neither /orders nor /user has any rate limiting; both are enumerable at line rate — `main.go:11-13`
  - No per-IP or per-caller rate limiting. /user accepts a user ID via query string — enumerating sequential IDs is trivial.
  - **Suggestion:** Add golang.org/x/time/rate token-bucket middleware before the mux.

#### Stage handoff notes
The goroutine leak in startBackgroundWorker has a DoS security adjacency. The db nil-pointer is also the root cause of the peer-go-reviewer ctx-propagation finding — DI wiring resolves both. No hardcoded secrets visible. Recommend adding govulncheck to CI.

---

### team-backend-reviewer (claude-sonnet-4-6)

**Verdict:** block · **Score:** 3/10

> OrdersHandler returns the full orders table with no pagination, exposes raw error strings to clients, and conflates all error types into 500; UserHandler blindly trusts a caller-supplied id query param with no type validation; the db pool is declared but never initialized, making every handler a nil-pointer panic on first request.

#### Findings

- **[critical]** handler package db var declared but never initialized; every DB call will nil-pointer panic — `handler/orders.go:21`
  - var db *sql.DB in the handler package is never assigned. main.go's var db *sql.DB is a separate variable and is also never initialized. First request to /orders panics.
  - **Suggestion:** Remove handler-package db var. Pass *sql.DB as dependency via constructor. Initialize in main() with sql.Open + db.Ping and fail fast on error.

- **[high]** OrdersHandler returns the entire orders table with no pagination — `handler/orders.go:29-31`
  - SELECT with no LIMIT returns all rows. Unbounded result set grows with the table. Sub-100ms p95 is impossible at any meaningful table size.
  - **Suggestion:** Parse ?limit= (default 50, max 200) and ?cursor= from request. Add keyset pagination: WHERE id > $1 ORDER BY id ASC LIMIT $2.

- **[high]** Both handlers collapse all error types into 500 and leak internal error strings to clients — `handler/orders.go:32`
  - Every error becomes 500 with raw Go error message. sql.ErrNoRows (404) and transient driver errors (503) are both mapped to 500. Leaks internal detail.
  - **Suggestion:** Introduce sentinel errors (ErrNotFound, ErrUnavailable) and a respondError helper that maps to correct status codes and emits a consistent JSON envelope.

- **[high]** UserHandler accepts any string as id with no type or format validation — `handler/user.go:14-18`
  - Checks only non-empty. Latent injection surface once real DB code replaces the stub.
  - **Suggestion:** Parse id as integer or UUID at the handler boundary; return 400 on validation failure.

- **[medium]** Success and error response envelopes are inconsistent across handlers — `handler/orders.go:40`
  - /orders returns a bare JSON array; /user returns a bare JSON object; errors are plain text. Clients need different parsers per endpoint.
  - **Suggestion:** Define a single envelope type with respond(w, status, data) and respondError(w, err) helpers applied consistently.

#### Stage handoff notes
N+1 query belongs to team-database-reviewer. Missing server timeouts belong to team-network-reviewer. Absence of structured logging / RED metrics belongs to team-observability-reviewer.

---

### team-network-reviewer (claude-sonnet-4-6)

**Verdict:** block · **Score:** 2/10

> http.ListenAndServe used with zero-value server timeouts (Slowloris-vulnerable, no write budget); no graceful shutdown on SIGTERM (in-flight requests killed on rolling restart); db.Query ignores context so request deadlines never reach the driver. All three are blockers for the stated production-ready / Kubernetes goal.

#### Findings

- **[high]** http.ListenAndServe used directly; server has no ReadHeaderTimeout, WriteTimeout, or IdleTimeout — `main.go:15`
  - http.ListenAndServe sets all timeouts to zero. Slowloris attack can exhaust connections. Slow handlers hold connections open indefinitely, directly violating the sub-100ms p95 goal. Keep-alive connections are never reaped.
  - **Suggestion:** Replace with explicit *http.Server: ReadHeaderTimeout: 5s, ReadTimeout: 30s, WriteTimeout: 30s, IdleTimeout: 120s. Tune WriteTimeout to be slightly above the p95 budget plus marshalling overhead.

- **[high]** No graceful shutdown on SIGTERM; Kubernetes rolling restarts kill in-flight requests — `main.go:12-19`
  - The aims explicitly require "graceful shutdown — in-flight requests complete on SIGTERM". Kubernetes sends SIGTERM before SIGKILL. The current code has no signal handler — SIGTERM kills the process immediately, aborting in-flight requests and producing a burst of 500s every deploy.
  - **Suggestion:** Use signal.NotifyContext to capture SIGTERM, then call srv.Shutdown(ctx) with a 30s deadline. Example: ctx, cancel := signal.NotifyContext(context.Background(), syscall.SIGTERM); go srv.ListenAndServe(); <-ctx.Done(); srv.Shutdown(shutCtx).

- **[medium]** db.Query used instead of db.QueryContext; request deadlines never reach the database driver — `handler/orders.go:45`
  - Even after fixing ctx type to context.Context and adding WriteTimeout, the DB round-trips are invisible to request deadlines and SIGTERM cancellation. Disconnecting clients leave queries running, consuming connection pool slots.
  - **Suggestion:** Switch to db.QueryContext(ctx, ...) for both queries after the ctx type fix lands.

#### Stage handoff notes
The goroutine leak in startBackgroundWorker composes with the graceful shutdown path — the worker's context should derive from the same signal context. N+1 pattern is database-reviewer's lane. ctx interface{} typing is peer-go-reviewer's lane; finding #3 layers on top of it.

---

### team-database-reviewer (claude-sonnet-4-6)

**Verdict:** block · **Score:** 2/10

> The orders handler fires one DB query per order row — a classic N+1 that turns a 100-order result into 101 round trips. Combined with no LIMIT on the base query and no context propagation to db.Query calls, this handler cannot meet the sub-100ms p95 target and will degrade linearly with table size.

#### Findings

- **[critical]** N+1 query pattern: one db.Query per order in a loop with no upper bound — `handler/orders.go:55-70`
  - listOrdersWithItems fetches all orders then issues a separate SELECT for items for each order. With N orders, the handler makes N+1 round trips. At 1,000 orders: 1,001 sequential queries. At 2ms RTT each, 100 orders = 200ms — 2x the 100ms SLO.
  - **Suggestion:** Replace with a single JOIN: SELECT o.id, o.user_id, o.total, i.id, i.order_id, i.name, i.unit_cost FROM orders o LEFT JOIN items i ON i.order_id = o.id ORDER BY o.id. Scan into a map[int64]*Order accumulating items per order.

- **[high]** No LIMIT on the orders base query; full table scan on every request — `handler/orders.go:46`
  - SELECT id, user_id, total FROM orders returns all rows. As the table grows this holds an open cursor for the full scan, consumes increasing memory, and returns a payload that grows without bound.
  - **Suggestion:** Add keyset pagination: SELECT id, user_id, total FROM orders WHERE id > $1 ORDER BY id LIMIT $2. Expose cursor and limit as query parameters with default 100 and hard cap 500.

- **[high]** db.Query called without context; queries cannot be cancelled on client disconnect or timeout — `handler/orders.go:46`
  - Non-context variant of db.Query used. If the HTTP client disconnects mid-request, Postgres queries continue running, holding locks and consuming connection pool slots. Under Kubernetes rolling deploys, orphaned queries accumulate.
  - **Suggestion:** Change listOrdersWithItems(ctx interface{}) to listOrdersWithItems(ctx context.Context) and replace db.Query with db.QueryContext(ctx, ...) for both queries.

#### Stage handoff notes
Connection pool configuration not visible in scope. If sql.Open uses defaults (MaxOpenConns=0 = unlimited), Postgres max_connections can be exhausted under load. The user.go handler is a stub with no actual DB query — no database findings apply there.

---

### team-performance-reviewer (claude-sonnet-4-6)

**Verdict:** block · **Score:** 2/10

> N+1 query in listOrdersWithItems is the headline blocker: 100 orders at 2ms RTT each = 200ms added latency, 2x the stated 100ms p95 SLO before any other work. No LIMIT on the outer query means latency grows linearly with row count. Context propagation is broken so DB queries cannot be cancelled. SLO is mathematically unmeetable as written.

#### Findings

- **[critical]** listOrdersWithItems issues one DB query per order for items — N+1 makes the 100ms p95 SLO mathematically unmeetable — `handler/orders.go:51-72`
  - Capacity memo: 100 orders × 2ms RTT = 200ms — 2x the SLO before accounting for the outer query, network stack, or JSON serialization. At 50 orders the math is still 100ms+ on the DB path alone with zero headroom. Wall-clock time is dominated entirely by round-trip count, not execution cost.
  - **Suggestion:** Two-query batched pattern: (1) SELECT id, user_id, total FROM orders LIMIT $1 OFFSET $2, (2) SELECT id, order_id, name, unit_cost FROM items WHERE order_id = ANY($1). Group items by order_id in a Go map. Total: 2 DB round trips regardless of N.

- **[high]** No LIMIT on outer orders query — endpoint latency grows unbounded with row count — `handler/orders.go:44`
  - 10k-row orders table at 0.1ms per row = 1s — 10x the SLO. Even with N+1 fixed, the full table scan is a silent time-bomb that passes load tests on a clean DB and fails in production.
  - **Suggestion:** Keyset pagination with cursor and page_size params. Default page_size 50, hard cap 200.

- **[high]** ctx interface{} parameter prevents DB query cancellation — wasted DB work on client disconnect cannot be reclaimed — `handler/orders.go:44`
  - At 1k req/s with 200ms queries, ~200 in-flight queries are alive at any instant. 10% client disconnect rate = 20 goroutines accumulating per second without reclaim → connection pool exhaustion → latency cliff.
  - **Suggestion:** Change to context.Context, use db.QueryContext. Pair with context.WithTimeout at the handler level (e.g., 80ms budget for DB work, leaving 20ms headroom).

- **[medium]** No DB connection pool configuration visible — default pool settings will bottleneck throughput — `main.go:1-20`
  - MaxOpenConns=0 (unlimited) exhausts Postgres. MaxIdleConns=2 spawns new connections per request under bursts (5-20ms TCP+auth overhead per new connection — enough to violate the 100ms SLO alone).
  - **Suggestion:** db.SetMaxOpenConns(25), db.SetMaxIdleConns(25), db.SetConnMaxLifetime(5*time.Minute). Tune to Postgres max_connections and pod replica count.

#### Stage handoff notes
Once N+1 and pagination are fixed, recommend running pprof CPU+heap profile under representative load to surface the next latency tier, particularly JSON serialization cost for large order lists.

---

### team-observability-reviewer (claude-sonnet-4-6)

**Verdict:** block · **Score:** 2/10

> The aims explicitly require structured logs, RED metrics, and distributed traces — none exist. Every log line is a bare string, no /healthz or /readyz, no /metrics, no error tracker. On-call would have zero signal: failures appear only as opaque stdout or HTTP 500s with no operator-side trace.

#### Findings

- **[high]** Service uses standard log package with bare strings throughout; production logs are unsearchable — `main.go:13`
  - log.Println and log.Fatalf — bare strings with no level, no service name, no fields. Neither orders.go nor user.go imports any logger; errors flow through fmt.Sprintf into http.Error and are never logged server-side. The aims list "structured logs" as an explicit success criterion.
  - **Suggestion:** Adopt log/slog with JSON handler. Replace log.Println/Fatalf with slog.Info/Error using key-value fields. In each handler, log errors with structured fields (err, route, method) before calling http.Error.

- **[high]** No /healthz, /readyz, or /metrics endpoints registered; Kubernetes has nothing to probe and scrapers have nothing to scrape — `main.go:9-16`
  - Liveness probes have no endpoint; readiness probes have no endpoint; Prometheus scrapers have no /metrics endpoint. Without a latency histogram on /orders and /user, the sub-100ms p95 SLO cannot be measured, let alone alerted on.
  - **Suggestion:** Register /healthz (200 JSON), /readyz (200 when DB ping succeeds), /metrics (promhttp.Handler). Wrap /orders and /user with middleware incrementing http_requests_total and recording http_request_duration_seconds histogram.

- **[high]** No error tracker integration; unhandled errors and panics disappear into stdout with no grouping or alerting — `handler/orders.go:6-11`
  - Errors from listOrdersWithItems have nothing forwarded to an error tracker. Combined with the rows.Err() gap, a silent partial-result bug produces 200 OK with zero operator-side signal. On-call will learn about DB failures from customer complaints, not alerts.
  - **Suggestion:** Initialize an error tracker SDK at startup (Sentry, Bugsnag, etc.) with environment and release. Wrap mux with recovery middleware that captures panics and forwards with request context.

- **[high]** No tracing SDK initialized; the aims explicitly require distributed traces and the sub-100ms p95 SLO cannot be decomposed without spans — `main.go:9-16`
  - The aims list "distributed traces" as an explicit success criterion. Without a DB span on the Postgres calls, on-call cannot answer "is the latency in the handler or in the query?" when the SLO is breached.
  - **Suggestion:** Initialize OpenTelemetry SDK with service name 'go-api'. Register otelhttp.NewHandler as middleware. Inside listOrdersWithItems, wrap db.Query with a child span. Propagate W3C traceparent on outbound calls.

- **[medium]** No request-ID middleware; log lines from a single failing request cannot be reconstructed — `main.go:9`
  - No X-Request-ID generated or propagated; no request-scoped child logger. When /orders fails, on-call sees at most one log line. Concurrent request logs are interleaved with no identifier.
  - **Suggestion:** Add middleware that reads X-Request-ID or generates a UUID, stores in ctx, injects into slog child logger. Emit a single INFO line on request completion with route, method, status, duration_ms, request_id.

#### Stage handoff notes
Verdict is block because all three observability success criteria are absent. The peer-go-reviewer ctx interface{} fix is a prerequisite for the OTel tracing fix — trace spans cannot flow into listOrdersWithItems until the interface{} type is corrected.

---

## Stage 3 — Leadership

### lead-senior-architect (claude-opus-4-7)

**Verdict:** block · **Score:** 2/10

> Service has no operational boundary (no lifecycle, no timeouts, no shutdown), no error-classification taxonomy, no shared data-access layer (db var declared per-package, never initialized), and no observability seam — every Stage 2 success criterion lacks a structural home. Recommend block until a Server lifecycle owner, a shared DB layer, and a middleware chain exist before any handler hardening lands.

#### Findings

- **[critical]** Service has no owning lifecycle: timeouts, signal handling, shutdown, and background-worker cancellation are all structurally absent — `main.go:11-29`
  - main.go calls http.ListenAndServe directly with no *http.Server value owning the listener, no timeout fields, no signal.NotifyContext, no srv.Shutdown(ctx), and a startBackgroundWorker goroutine with no context or cancellation. There is no concept of "the service is starting" or "the service is stopping" — main() is a flat sequence with no lifecycle owner. Every operational concern the aims demand (graceful shutdown, slowloris protection, in-flight draining, worker cancellation, readiness probes) currently has no structural home.
  - **Suggestion:** Create app/server.go with type Server struct { http *http.Server; workers []Runner } where Runner is interface { Run(ctx context.Context) error }. Server.Run uses errgroup with one goroutine per worker plus a shutdown goroutine that waits on ctx.Done() then calls srv.Shutdown. Set ReadHeaderTimeout=5s, WriteTimeout=15s, IdleTimeout=60s.

- **[critical]** Database access has no owning module: db is a per-package var declared but never wired, and queries go through it directly from handlers — `handler/orders.go:21`
  - main.go and handler/orders.go each declare var db *sql.DB as independent globals — a future sql.Open in main.go would not populate handler.db at all. There is no Store/Repository module. Every Stage 2 database finding (nil panic, no QueryContext, no LIMIT, N+1, no pool tuning, no test seam) is currently homeless — there is no module to fix them in.
  - **Suggestion:** Create store/store.go with type Store struct { db *sql.DB } and func NewStore(dsn string) (*Store, error). Move listOrdersWithItems into store as ListOrders(ctx context.Context, limit, offset int). Convert handlers to struct form injecting *Store. Remove both package-level db vars.

- **[high]** Every cross-cutting concern (logging, tracing, metrics, request-ID, rate limit, error envelope) has no boundary — `main.go:14-16`
  - main.go registers two HandleFunc calls with no middleware chain. Each handler hand-rolls its own response shaping. No structured logging, no otel span, no prometheus histogram, no X-Request-ID, no panic recovery. The observability success criteria cannot be addressed because there is no boundary to attach them to.
  - **Suggestion:** Create app/middleware.go with Chain(mw ...Middleware) Middleware and implement RecoverPanic, RequestID, StructuredLog, Trace, Meter. Add app/httpx/respond.go with WriteJSON and WriteError. Apply middleware once when registering handlers.

- **[high]** No error taxonomy: every error path collapses to 500 with the raw error string echoed to the client — `handler/orders.go:27`
  - Every error from any source maps to 500 with the raw Go error string in the body. No sentinel errors, no respondError helper, no errors.Is/As discipline. Every layer either swallows error context or leaks it raw because there is no classifier.
  - **Suggestion:** Create errx/errors.go with ErrNotFound, ErrInvalid, ErrUnavailable sentinels. Route every handler response through httpx.WriteError which maps known sentinels to status codes and logs full error chain server-side.

- **[high]** No seams for testing: handlers depend on package-level globals, so the only test that can be written is a struct-field smoke test — `handler/orders.go:21-31`
  - OrdersHandler is a package function reading from a package-level var db *sql.DB. There is no Querier interface, no constructor, no DI. The Stage 1 quality finding "zero handler coverage" cannot be addressed by "write tests" — the tests cannot be written cleanly until handlers receive dependencies via constructors.
  - **Suggestion:** Define type OrderStore interface { ListOrders(ctx context.Context, limit, offset int) ([]Order, error) } in the handler package. Convert func OrdersHandler to type OrdersHandler struct { store OrderStore; logger *slog.Logger } with ServeHTTP. Tests use a fakeStore with httptest.NewRecorder.

#### Stage handoff notes
Dependency order: store package (finding 2) → test seams (finding 5) → error taxonomy (finding 4) → middleware chain (finding 3) → Server lifecycle (finding 1). The team should not attempt Stage 2 fixes in isolation — fixing N+1 without extracting the store package will entrench the global-db pattern.

---

### lead-project-manager (claude-opus-4-7)

**Verdict:** block · **Score:** 2/10

> Aim alignment: 2/10. Scope: on-scope. Verdict: rescope. All four success criteria in aims.md (p95<100ms, graceful shutdown, observability, no goroutine leaks) are either regressed or entirely untouched. PR is foundationally aimed but execution is nowhere near 'production-ready'.

#### Findings

- **[critical]** PR claims production-ready order API but fails every stated success criterion — `.review/aims.md:11-15`
  - Per-criterion accounting: (1) Sub-100ms p95 — REGRESSED: N+1 query makes SLO mathematically impossible; (2) Graceful shutdown — UNTOUCHED: no signal handling; (3) Observable — UNTOUCHED: log.Println, zero metrics, zero traces; (4) No goroutine leaks — REGRESSED: startBackgroundWorker spawns unconditional for-loop. Four of four success criteria unmet. Scope is on-target but execution is roughly 5-10% of production-ready.
  - **Suggestion:** Rescope path A (recommended): split into four sequenced PRs — (1) shutdown: Server struct + signal handling + srv.Shutdown; (2) perf: N+1 collapse via JOIN + LIMIT + QueryContext; (3) observability: slog + RED metrics + OTel traces; (4) worker: ctx-aware background worker. Rescope path B: update aims.md to acknowledge this as a foundation PR.

- **[high]** Highest-leverage next work is the N+1 fix and shutdown wiring, not handler test coverage — `handler/orders.go:23`
  - aims.md does not list test coverage as a success criterion. The highest-leverage follow-up: (a) N+1 collapse in handler/orders.go:23 (closes p95 criterion); (b) graceful shutdown in main.go (~30 lines); (c) ctx-aware background worker (~10 lines). Tests should follow once the surface stabilizes.
  - **Suggestion:** Sequence: (1) perf PR (N+1 + LIMIT + QueryContext); (2) shutdown PR; (3) observability PR. Handler tests after surface stabilizes.

- **[high]** Code-quality findings outside aims (nil db panic, error leak, no pagination) are real but not alignment-decisive — `handler/orders.go:13`
  - The nil-panic is a correctness blocker but doesn't map to a stated success criterion. Authentication concerns raised by team-backend-reviewer are explicitly out-of-scope per aims.md non-goals.
  - **Suggestion:** Treat nil-db panic as a separate correctness gate (must fix before any traffic). Auth finding is out-of-scope per aims.md. Note pagination for the perf PR backlog.

#### Stage handoff notes
Recommended path: either rescope PR framing as "foundation only" or hold for N+1 + shutdown fixes before claiming production-ready.

---

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

## Run Metadata

- **Plugin version:** 0.1.0
- **Models used:** claude-haiku-4-5-20251001, claude-sonnet-4-6, claude-opus-4-7

_Wall-clock time and API cost are not displayed here. Claude Code already reports both at the end of every session (and via `/status` on demand) using its own measurements, which are more accurate than anything a plugin skill can compute from inside the run. Crucible does not duplicate them._
