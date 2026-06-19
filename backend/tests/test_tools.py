import json
from datetime import date

from app.agent.tools import execute_tool, ToolContext


def _ctx(conn, customer_id):
    return ToolContext(conn=conn, customer_id=customer_id, today=date.today())


def test_issue_refund_blocks_final_sale(seeded_conn):
    res = execute_tool("issue_refund", {"order_id": 1002}, _ctx(seeded_conn, 1))
    payload = json.loads(res.content)
    assert payload["refunded"] is False
    assert res.decision == "denied"
    assert seeded_conn.execute("SELECT is_refunded FROM orders WHERE id=1002").fetchone()["is_refunded"] == 0
    assert seeded_conn.execute("SELECT decision FROM refunds WHERE order_id=1002").fetchone()["decision"] == "denied"


def test_issue_refund_approves_clean(seeded_conn):
    res = execute_tool("issue_refund", {"order_id": 1001}, _ctx(seeded_conn, 1))
    assert json.loads(res.content)["refunded"] is True
    assert res.decision == "approved"
    assert seeded_conn.execute("SELECT is_refunded FROM orders WHERE id=1001").fetchone()["is_refunded"] == 1


def test_issue_refund_escalates_over_threshold(seeded_conn):
    res = execute_tool("issue_refund", {"order_id": 1003}, _ctx(seeded_conn, 2))
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
