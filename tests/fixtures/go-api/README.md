# go-api fixture

Synthetic Go HTTP service for Crucible E2E tests. **Deliberately contains issues.**

## Deliberate gaps

- `main.go` — no graceful shutdown handler
- `main.go` — goroutine leak (no context cancellation on shutdown)
- `main.go` — `http.ListenAndServe` without read/write/idle timeouts
- `handler/orders.go` — N+1 query pattern in order list
- `handler/orders.go` — `db.Query` error checked but `rows.Err()` not
- `handler/user.go` — uses `http.HandleFunc` (no timeouts on the server)
