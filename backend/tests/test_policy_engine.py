from datetime import date, timedelta

from app.data.policy_engine import evaluate_refund

TODAY = date(2026, 6, 18)


def _order(**over):
    base = dict(
        id=1, customer_id=1, item_name="Widget", category="x", amount=100.0,
        status="delivered", order_date="2026-06-01",
        delivered_date=(TODAY - timedelta(days=10)).isoformat(),
        is_final_sale=0, is_refunded=0, refund_date=None,
    )
    base.update(over)
    return base


def test_clean_order_approves():
    d = evaluate_refund(_order(), 1, TODAY)
    assert d.decision == "APPROVE"
    assert d.matched_rules == []


def test_wrong_customer_denies():
    d = evaluate_refund(_order(customer_id=1), 2, TODAY)
    assert d.decision == "DENY"
    assert "R1_ownership" in d.matched_rules


def test_not_delivered_denies():
    for status in ("processing", "shipped", "cancelled"):
        d = evaluate_refund(_order(status=status), 1, TODAY)
        assert d.decision == "DENY"
        assert "R2_not_delivered" in d.matched_rules


def test_final_sale_denies():
    d = evaluate_refund(_order(is_final_sale=1), 1, TODAY)
    assert d.decision == "DENY"
    assert "R3_final_sale" in d.matched_rules


def test_already_refunded_denies():
    d = evaluate_refund(_order(is_refunded=1), 1, TODAY)
    assert d.decision == "DENY"
    assert "R4_already_refunded" in d.matched_rules


def test_outside_window_denies():
    d = evaluate_refund(_order(delivered_date=(TODAY - timedelta(days=31)).isoformat()), 1, TODAY)
    assert d.decision == "DENY"
    assert "R5_outside_window" in d.matched_rules


def test_over_threshold_escalates():
    d = evaluate_refund(_order(amount=900.0), 1, TODAY)
    assert d.decision == "ESCALATE"
    assert "R6_over_threshold" in d.matched_rules


def test_deny_takes_precedence_over_escalate():
    d = evaluate_refund(_order(amount=900.0, is_final_sale=1), 1, TODAY)
    assert d.decision == "DENY"
    assert "R3_final_sale" in d.matched_rules
