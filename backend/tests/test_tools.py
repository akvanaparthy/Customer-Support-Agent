import json
from datetime import date

from app.agent.tools import execute_tool, ToolContext
from app.data import crm


def _ctx(conn, customer_id):
    return ToolContext(conn=conn, customer_id=customer_id, today=date.today())


def test_ask_user_returns_prompt(seeded_conn):
    res = execute_tool("ask_user", {"question": "Which order?", "options": ["#1001", "#1002"]}, _ctx(seeded_conn, 1))
    assert res.prompt == {"question": "Which order?", "options": ["#1001", "#1002"]}
    assert res.is_error is False


def test_request_evidence_returns_prompt(seeded_conn):
    res = execute_tool("request_evidence", {"message": "Upload a photo"}, _ctx(seeded_conn, 1))
    assert res.prompt == {"question": "Upload a photo", "photo": True}


def test_unverifiable_without_photo_escalates_via_tool(seeded_conn):
    # wrong_item, ctx has no evidence -> escalate (R13), nothing refunded
    res = execute_tool(
        "issue_refund",
        {"order_id": 1001, "reason": "got the wrong thing", "reason_category": "wrong_item"},
        _ctx(seeded_conn, 1),
    )
    payload = json.loads(res.content)
    assert payload["refunded"] is False
    assert "R13_evidence_required" in payload["matched_rules"]
    assert seeded_conn.execute("SELECT is_refunded FROM orders WHERE id=1001").fetchone()["is_refunded"] == 0


def test_unverifiable_with_photo_no_history_refunds_via_tool(seeded_conn):
    ctx = ToolContext(conn=seeded_conn, customer_id=1, today=date.today(), has_evidence=True)
    res = execute_tool(
        "issue_refund",
        {"order_id": 1001, "reason": "received wired instead of wireless", "reason_category": "wrong_item"},
        ctx,
    )
    assert json.loads(res.content)["refunded"] is True


def test_issue_refund_requires_reason(seeded_conn):
    # R7: no reason/category -> refused, nothing recorded
    res = execute_tool("issue_refund", {"order_id": 1001}, _ctx(seeded_conn, 1))
    assert res.is_error is True
    assert json.loads(res.content)["error"] == "reason_required"
    assert seeded_conn.execute("SELECT is_refunded FROM orders WHERE id=1001").fetchone()["is_refunded"] == 0


def test_issue_refund_blocks_final_sale(seeded_conn):
    res = execute_tool(
        "issue_refund", {"order_id": 1002, "reason": "stopped working", "reason_category": "defective"}, _ctx(seeded_conn, 1)
    )
    payload = json.loads(res.content)
    assert payload["refunded"] is False
    assert res.decision == "denied"
    assert seeded_conn.execute("SELECT is_refunded FROM orders WHERE id=1002").fetchone()["is_refunded"] == 0
    assert seeded_conn.execute("SELECT decision FROM refunds WHERE order_id=1002").fetchone()["decision"] == "denied"


def test_issue_refund_approves_clean(seeded_conn):
    # defective is unverifiable -> needs a photo; with evidence + clean order it approves
    ctx = ToolContext(conn=seeded_conn, customer_id=1, today=date.today(), has_evidence=True)
    res = execute_tool(
        "issue_refund", {"order_id": 1001, "reason": "earbuds dead on arrival", "reason_category": "defective"}, ctx
    )
    assert json.loads(res.content)["refunded"] is True
    assert res.decision == "approved"
    assert seeded_conn.execute("SELECT is_refunded FROM orders WHERE id=1001").fetchone()["is_refunded"] == 1
    assert seeded_conn.execute("SELECT reason FROM refunds WHERE order_id=1001").fetchone()["reason"].startswith("[defective]")


def test_issue_refund_escalates_over_threshold(seeded_conn):
    res = execute_tool(
        "issue_refund", {"order_id": 1003, "reason": "screen cracked", "reason_category": "damaged"}, _ctx(seeded_conn, 2)
    )
    assert json.loads(res.content)["refunded"] is False
    assert res.decision == "escalated"


def test_get_order_blocks_other_customer(seeded_conn):
    res = execute_tool("get_order", {"order_id": 1003}, _ctx(seeded_conn, 1))
    assert res.is_error is True


def test_escalate_to_human(seeded_conn):
    res = execute_tool("escalate_to_human", {"order_id": 1003, "reason": "over $500"}, _ctx(seeded_conn, 2))
    payload = json.loads(res.content)
    assert payload["escalated"] is True
    assert res.decision == "escalated"


def test_check_eligibility_denies_final_sale(seeded_conn):
    res = execute_tool("check_refund_eligibility", {"order_id": 1002}, _ctx(seeded_conn, 1))
    assert json.loads(res.content)["decision"] == "DENY"
    assert res.decision == "denied"


def test_unknown_order_is_error(seeded_conn):
    res = execute_tool("get_order", {"order_id": 999999}, _ctx(seeded_conn, 1))
    assert res.is_error is True


def test_reason_shopping_escalates_via_tool(seeded_conn):
    # 1001 is clean & in-window (defective would normally APPROVE), but it was denied
    # earlier under changed_mind -> the re-claim under a new reason must escalate (R11).
    crm.log_claim(seeded_conn, 1001, 1, "changed_mind", "denied", "2026-06-19T00:00:00Z")
    res = execute_tool("check_refund_eligibility", {"order_id": 1001, "reason_category": "defective"}, _ctx(seeded_conn, 1))
    payload = json.loads(res.content)
    assert payload["decision"] == "ESCALATE"
    assert "R11_reason_shopping" in payload["matched_rules"]
    assert res.decision == "escalated"
