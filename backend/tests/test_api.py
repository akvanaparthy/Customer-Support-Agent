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
    def fake_run_turn(graph, client, conn, session_id, customer, history, message):
        rec = TraceRecorder(session_id, customer["id"], customer["name"], message)
        rec.add_step("llm_call", "claude", output="ok", tokens_in=100, tokens_out=20, latency_ms=10)
        return "Refund approved.", "approved", rec.finalize("approved"), history + [{"role": "user", "content": message}]

    monkeypatch.setattr(main, "run_turn", fake_run_turn)
    c = _client(tmp_path)
    r = c.post("/api/chat", json={"session_id": "s1", "customer_id": 1, "message": "refund 1001"}).json()
    assert r["decision"] == "approved" and r["reply"] == "Refund approved."
    tid = r["trace_id"]
    assert any(s["trace_id"] == tid for s in c.get("/api/traces").json()["traces"])
    assert c.get(f"/api/traces/{tid}").json()["step_count"] == 1


def test_chat_unknown_customer(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "run_turn", lambda *a, **k: ("", None, None, []))
    c = _client(tmp_path)
    assert c.post("/api/chat", json={"session_id": "s1", "customer_id": 999, "message": "hi"}).status_code == 404
