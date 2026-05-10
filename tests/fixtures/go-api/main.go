// Package main starts the order management HTTP server.
// Deliberately broken in places — see fixture README.
package main

import (
	"database/sql"
	"log"
	"net/http"

	"github.com/hsozer00/crucible-fixtures/go-api/handler"
)

var db *sql.DB

func main() {
	// BAD: no graceful shutdown. SIGTERM will drop in-flight requests.
	// Production code should listen for signals and call srv.Shutdown(ctx).

	mux := http.NewServeMux()
	mux.HandleFunc("/orders", handler.OrdersHandler)
	mux.HandleFunc("/user", handler.UserHandler)

	// BAD: http.ListenAndServe directly. No ReadHeaderTimeout, no WriteTimeout,
	// no IdleTimeout. Slowloris is wide open.
	log.Println("listening on :8080")
	if err := http.ListenAndServe(":8080", mux); err != nil {
		log.Fatalf("server: %v", err)
	}
}

// startBackgroundWorker spawns a worker goroutine.
//
// BAD: the worker has no way to be told to stop. When the process exits
// it will just be killed; if the process keeps running the goroutine leaks.
func startBackgroundWorker() {
	go func() {
		for {
			// pretend work
			doSomething()
		}
	}()
}

func doSomething() {
	// no-op for the fixture
}
