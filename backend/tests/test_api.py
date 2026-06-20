from fastapi.testclient import TestClient

import app.main as main
from app.agent.trace import TraceRecorder


def _client(tmp_path):
    main.settings.db_path = str(tmp_path / "crm.db")
    main.SESSIONS.clear()
    main.ensure_seeded(main.settings.db_path)
    return TestClient(main.app)


def test_health(tmp_path):
    assert _client(tmp_path).get("/api/health").json() == {"status": "ok"}


def test_policy_and_customers(tmp_path):
    c = _client(tmp_path)
    assert "Refund Policy" in c.get("/api/policy").json()["policy"]
    assert len(c.get("/api/customers").json()["customers"]) == 15


def test_chat_persists_trace(tmp_path, monkeypatch):
    def fake_run_turn(graph, client, conn, session_id, customer, history, message, tickets=(), image=None, has_evidence=False):
        rec = TraceRecorder(session_id, customer["id"], customer["name"], message)
        rec.add_step("llm_call", "claude", output="ok", tokens_in=100, tokens_out=20, latency_ms=10)
        return "Refund approved.", "approved", None, False, rec.finalize("approved"), history + [{"role": "user", "content": message}]

    monkeypatch.setattr(main, "run_turn", fake_run_turn)
    c = _client(tmp_path)
    r = c.post("/api/chat", json={"session_id": "s1", "customer_id": 1, "message": "refund 1001"}).json()
    assert r["decision"] == "approved" and r["reply"] == "Refund approved."
    tid = r["trace_id"]
    assert any(s["trace_id"] == tid for s in c.get("/api/traces").json()["traces"])
    assert c.get(f"/api/traces/{tid}").json()["step_count"] == 1


def test_chat_unknown_customer(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "run_turn", lambda *a, **k: ("", None, None, False, None, []))
    c = _client(tmp_path)
    assert c.post("/api/chat", json={"session_id": "s1", "customer_id": 999, "message": "hi"}).status_code == 404


def test_orders_list(tmp_path):
    c = _client(tmp_path)
    data = c.get("/api/orders").json()["orders"]
    assert len(data) == 30
    o = next(x for x in data if x["id"] == 1001)
    assert o["customer_name"] == "Alice Tan"


def test_update_order_status(tmp_path):
    c = _client(tmp_path)
    r = c.patch("/api/orders/1007", json={"status": "delivered"})
    assert r.status_code == 200 and r.json()["status"] == "delivered"
    o = next(x for x in c.get("/api/orders").json()["orders"] if x["id"] == 1007)
    assert o["status"] == "delivered"


def test_update_order_refunded_toggle(tmp_path):
    c = _client(tmp_path)
    r = c.patch("/api/orders/1001", json={"is_refunded": True})
    assert r.status_code == 200 and r.json()["is_refunded"] == 1


def test_update_order_invalid_status(tmp_path):
    c = _client(tmp_path)
    assert c.patch("/api/orders/1001", json={"status": "frozen"}).status_code == 400


def test_update_unknown_order(tmp_path):
    c = _client(tmp_path)
    assert c.patch("/api/orders/999999", json={"status": "delivered"}).status_code == 404
