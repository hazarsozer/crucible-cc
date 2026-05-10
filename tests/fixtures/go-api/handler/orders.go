// Package handler holds HTTP handlers for the fixture.
// Deliberately broken in places — see fixture README.
package handler

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"net/http"
)

type Order struct {
	ID     int64   `json:"id"`
	UserID int64   `json:"user_id"`
	Total  float64 `json:"total"`
	Items  []Item  `json:"items"`
}

type Item struct {
	ID       int64   `json:"id"`
	OrderID  int64   `json:"order_id"`
	Name     string  `json:"name"`
	UnitCost float64 `json:"unit_cost"`
}

var db *sql.DB

// OrdersHandler returns all orders along with their items.
func OrdersHandler(w http.ResponseWriter, r *http.Request) {
	orders, err := listOrdersWithItems(r.Context())
	if err != nil {
		http.Error(w, fmt.Sprintf("listOrders: %v", err), http.StatusInternalServerError)
		return
	}
	_ = json.NewEncoder(w).Encode(orders)
}

// listOrdersWithItems pulls orders and then their items.
//
// BAD: classic N+1. We issue one query for the orders, then one query
// per order for its items. With N orders, that's N+1 round trips. The
// database reviewer should flag this; the fix is a JOIN or a single
// IN-clause query.
func listOrdersWithItems(ctx interface{}) ([]Order, error) {
	rows, err := db.Query(`SELECT id, user_id, total FROM orders`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var orders []Order
	for rows.Next() {
		var o Order
		if err := rows.Scan(&o.ID, &o.UserID, &o.Total); err != nil {
			return nil, err
		}

		// One additional query per order. N+1.
		itemRows, err := db.Query(`SELECT id, order_id, name, unit_cost FROM items WHERE order_id = $1`, o.ID)
		if err != nil {
			return nil, err
		}
		for itemRows.Next() {
			var it Item
			if err := itemRows.Scan(&it.ID, &it.OrderID, &it.Name, &it.UnitCost); err != nil {
				_ = itemRows.Close()
				return nil, err
			}
			o.Items = append(o.Items, it)
		}
		_ = itemRows.Close()
		orders = append(orders, o)
	}

	// BAD: rows.Err() is not checked. If the result set was truncated by an
	// error mid-iteration we'll silently return a partial slice.
	return orders, nil
}
