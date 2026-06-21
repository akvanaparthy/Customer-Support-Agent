from app.data.seed import ensure_seeded
from app.data.db import connect


def test_seed_counts_and_branches(tmp_path):
    db = str(tmp_path / "crm.db")
    ensure_seeded(db)
    conn = connect(db)
    customers = conn.execute("SELECT COUNT(*) AS c FROM customers").fetchone()["c"]
    assert customers == 15

    statuses = {r["status"] for r in conn.execute("SELECT DISTINCT status FROM orders")}
    assert {"delivered", "shipped", "processing", "cancelled"} <= statuses

    assert conn.execute("SELECT COUNT(*) AS c FROM orders WHERE is_final_sale=1").fetchone()["c"] >= 1
    assert conn.execute("SELECT COUNT(*) AS c FROM orders WHERE is_refunded=1").fetchone()["c"] >= 1
    assert conn.execute("SELECT COUNT(*) AS c FROM orders WHERE amount > 500").fetchone()["c"] >= 1


def test_seed_is_idempotent(tmp_path):
    db = str(tmp_path / "crm.db")
    ensure_seeded(db)
    ensure_seeded(db)
    conn = connect(db)
    assert conn.execute("SELECT COUNT(*) AS c FROM customers").fetchone()["c"] == 15


def test_claims_table_exists(tmp_path):
    db = str(tmp_path / "crm.db")
    ensure_seeded(db)
    conn = connect(db)
    conn.execute("SELECT COUNT(*) FROM claims")  # raises if the table is missing
