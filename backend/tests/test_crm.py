from app.data import crm


def test_get_customer_and_orders(seeded_conn):
    c = crm.get_customer(seeded_conn, 1)
    assert c["name"] == "Alice Tan"
    orders = crm.list_orders(seeded_conn, 1)
    assert {o["id"] for o in orders} == {1001, 1002}


def test_get_order_returns_dict(seeded_conn):
    o = crm.get_order(seeded_conn, 1003)
    assert o["customer_id"] == 2
    assert o["amount"] == 899.00
    assert crm.get_order(seeded_conn, 999999) is None


def test_record_refund_and_mark(seeded_conn):
    crm.mark_order_refunded(seeded_conn, 1001, "2026-06-18")
    crm.record_refund(seeded_conn, 1001, 79.99, "approved", "within policy", "2026-06-18T00:00:00Z")
    o = crm.get_order(seeded_conn, 1001)
    assert o["is_refunded"] == 1
    rows = seeded_conn.execute("SELECT * FROM refunds WHERE order_id=1001").fetchall()
    assert len(rows) == 1 and rows[0]["decision"] == "approved"


def test_list_customers_with_orders(seeded_conn):
    rows = crm.list_customers_with_orders(seeded_conn)
    assert len(rows) == 15
    alice = next(r for r in rows if r["id"] == 1)
    assert len(alice["orders"]) == 2


def test_claim_log_and_prior_denied(seeded_conn):
    crm.log_claim(seeded_conn, 1002, 1, "changed_mind", "denied", "2026-06-19T00:00:00Z")
    crm.log_claim(seeded_conn, 1002, 1, "defective", "escalated", "2026-06-19T00:01:00Z")
    # only DENIED categories count toward reason-shopping
    assert crm.prior_denied_categories(seeded_conn, 1002) == {"changed_mind"}


def test_customer_tickets(seeded_conn):
    crm.log_claim(seeded_conn, 1002, 1, "changed_mind", "denied", "2026-06-15T00:00:00Z")
    crm.log_claim(seeded_conn, 1001, 1, "defective", "approved", "2026-06-16T00:00:00Z")
    tickets = crm.get_customer_tickets(seeded_conn, 1)
    assert [t["order_id"] for t in tickets] == [1001, 1002]  # one per order, latest first
    t1001 = next(t for t in tickets if t["order_id"] == 1001)
    assert t1001["decision"] == "approved" and t1001["item_name"] == "Wireless Earbuds"
