package handler

import (
	"encoding/json"
	"fmt"
	"net/http"
)

// UserHandler returns the current user.
//
// BAD: registered via http.HandleFunc on the default ServeMux without
// per-handler timeouts. A slow client can hold the connection open.
func UserHandler(w http.ResponseWriter, r *http.Request) {
	uid := r.URL.Query().Get("id")
	if uid == "" {
		http.Error(w, "id required", http.StatusBadRequest)
		return
	}

	user, err := lookupUser(uid)
	if err != nil {
		http.Error(w, fmt.Sprintf("lookup: %v", err), http.StatusInternalServerError)
		return
	}
	_ = json.NewEncoder(w).Encode(user)
}

type User struct {
	ID    string `json:"id"`
	Email string `json:"email"`
}

// lookupUser is a stub for the fixture.
func lookupUser(id string) (*User, error) {
	return &User{ID: id, Email: id + "@example.com"}, nil
}
