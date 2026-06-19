import sqlite3


def _row(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row is not None else None


def get_customer(conn, customer_id: int) -> dict | None:
    return _row(conn.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone())


def get_customer_by_email(conn, email: str) -> dict | None:
    return _row(conn.execute("SELECT * FROM customers WHERE email = ?", (email,)).fetchone())


def get_order(conn, order_id: int) -> dict | None:
    return _row(conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone())


def list_orders(conn, customer_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM orders WHERE customer_id = ? ORDER BY id", (customer_id,)
    ).fetchall()
    return [dict(r) for r in rows]


def list_customers_with_orders(conn) -> list[dict]:
    customers = [dict(r) for r in conn.execute("SELECT * FROM customers ORDER BY id")]
    for c in customers:
        c["orders"] = list_orders(conn, c["id"])
    return customers


def mark_order_refunded(conn, order_id: int, refund_date: str) -> None:
    conn.execute(
        "UPDATE orders SET is_refunded = 1, refund_date = ? WHERE id = ?",
        (refund_date, order_id),
    )
    conn.commit()


def record_refund(conn, order_id: int, amount: float, decision: str, reason: str, created_at: str) -> None:
    conn.execute(
        "INSERT INTO refunds (order_id, amount, decision, reason, created_at) VALUES (?, ?, ?, ?, ?)",
        (order_id, amount, decision, reason, created_at),
    )
    conn.commit()
