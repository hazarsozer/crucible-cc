package handler

import "testing"

// Trivial smoke test. Quality engineer should flag the absence of meaningful coverage.
func TestOrderStruct(t *testing.T) {
	o := Order{ID: 1, UserID: 2, Total: 9.99}
	if o.ID != 1 {
		t.Fatalf("expected ID=1, got %d", o.ID)
	}
}
