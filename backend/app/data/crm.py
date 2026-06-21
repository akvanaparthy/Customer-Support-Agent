import sqlite3
from datetime import date


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


def count_prior_refunds(conn, customer_id: int) -> int:
    """How many of this customer's orders have already been refunded (serial-return signal)."""
    row = conn.execute(
        "SELECT COUNT(*) AS c FROM orders WHERE customer_id = ? AND is_refunded = 1",
        (customer_id,),
    ).fetchone()
    return row["c"]


def log_claim(conn, order_id: int, customer_id: int, reason_category, decision: str, created_at: str) -> None:
    """Record a refund claim attempt (reason + outcome) — the per-order history that
    survives across chat sessions and powers reason-shopping detection (R11)."""
    conn.execute(
        "INSERT INTO claims (order_id, customer_id, reason_category, decision, created_at) VALUES (?, ?, ?, ?, ?)",
        (order_id, customer_id, reason_category, decision, created_at),
    )
    conn.commit()


def prior_denied_categories(conn, order_id: int) -> set[str]:
    """Reason categories this order was previously DENIED under (any session)."""
    rows = conn.execute(
        "SELECT DISTINCT reason_category FROM claims WHERE order_id = ? AND decision = 'denied' AND reason_category IS NOT NULL",
        (order_id,),
    ).fetchall()
    return {r["reason_category"] for r in rows}


def has_prior_activity(conn, customer_id: int, exclude_order_id: int) -> bool:
    """Has this customer been refunded before, or raised a ticket on a DIFFERENT order?
    Used to give unverifiable claims extra scrutiny (R12)."""
    if count_prior_refunds(conn, customer_id) > 0:
        return True
    row = conn.execute(
        "SELECT COUNT(DISTINCT order_id) AS c FROM claims WHERE customer_id = ? AND order_id != ?",
        (customer_id, exclude_order_id),
    ).fetchone()
    return row["c"] > 0


def get_customer_tickets(conn, customer_id: int, limit: int = 8) -> list[dict]:
    """Compact history for a customer: the latest claim outcome per order they've
    contacted support about. Injected (cheaply) into new chats instead of transcripts."""
    rows = conn.execute(
        """SELECT c.order_id, c.reason_category, c.decision, MAX(c.created_at) AS created_at, o.item_name
           FROM claims c JOIN orders o ON o.id = c.order_id
           WHERE c.customer_id = ?
           GROUP BY c.order_id
           ORDER BY created_at DESC
           LIMIT ?""",
        (customer_id, limit),
    ).fetchall()
    return [dict(r) for r in rows]


ALLOWED_ORDER_STATUSES = {"processing", "shipped", "delivered", "cancelled"}


def list_all_orders(conn) -> list[dict]:
    """All orders across customers, with the owning customer's name/email (admin view)."""
    rows = conn.execute(
        """SELECT o.*, c.name AS customer_name, c.email AS customer_email
           FROM orders o JOIN customers c ON c.id = o.customer_id
           ORDER BY o.id"""
    ).fetchall()
    return [dict(r) for r in rows]


def update_order(conn, order_id, status=None, is_refunded=None, is_final_sale=None) -> dict | None:
    """Admin manual edit of an order's status/flags. Returns the updated order, or None if not found."""
    if get_order(conn, order_id) is None:
        return None
    sets, params = [], []
    if status is not None:
        sets.append("status = ?")
        params.append(status)
    if is_refunded is not None:
        sets.append("is_refunded = ?")
        params.append(1 if is_refunded else 0)
        sets.append("refund_date = ?")
        params.append(date.today().isoformat() if is_refunded else None)
    if is_final_sale is not None:
        sets.append("is_final_sale = ?")
        params.append(1 if is_final_sale else 0)
    if sets:
        params.append(order_id)
        conn.execute(f"UPDATE orders SET {', '.join(sets)} WHERE id = ?", params)
        conn.commit()
    return get_order(conn, order_id)
