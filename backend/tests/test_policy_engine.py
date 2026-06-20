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


# --- R8: buyer's-remorse window ---------------------------------------------

def test_changed_mind_outside_buyer_window_denies():
    # delivered 20 days ago: inside the 30-day window (R5 ok) but past the 14-day remorse window
    d = evaluate_refund(
        _order(delivered_date=(TODAY - timedelta(days=20)).isoformat()),
        1, TODAY, reason_category="changed_mind",
    )
    assert d.decision == "DENY"
    assert "R8_buyer_remorse_window" in d.matched_rules


def test_changed_mind_within_buyer_window_approves():
    d = evaluate_refund(
        _order(delivered_date=(TODAY - timedelta(days=10)).isoformat()),
        1, TODAY, reason_category="changed_mind",
    )
    assert d.decision == "APPROVE"


def test_late_defect_escalates_for_verification():
    # 20 days (past the 14-day remorse window), defective -> ESCALATE for human verify (R10)
    d = evaluate_refund(
        _order(delivered_date=(TODAY - timedelta(days=20)).isoformat()),
        1, TODAY, reason_category="defective",
    )
    assert d.decision == "ESCALATE"
    assert "R10_late_defect_review" in d.matched_rules


def test_defect_within_remorse_window_approves():
    # within 14 days, defective -> nothing to game -> APPROVE
    d = evaluate_refund(
        _order(delivered_date=(TODAY - timedelta(days=10)).isoformat()),
        1, TODAY, reason_category="defective",
    )
    assert d.decision == "APPROVE"


def test_reason_shopping_escalates():
    # order previously DENIED under changed_mind, now re-claimed as defective -> ESCALATE (R11)
    d = evaluate_refund(
        _order(delivered_date=(TODAY - timedelta(days=5)).isoformat()),
        1, TODAY, reason_category="defective", prior_denied_categories={"changed_mind"},
    )
    assert d.decision == "ESCALATE"
    assert "R11_reason_shopping" in d.matched_rules


def test_same_reason_retry_not_flagged():
    # retrying the SAME category that was denied is not reason-shopping
    d = evaluate_refund(
        _order(delivered_date=(TODAY - timedelta(days=5)).isoformat()),
        1, TODAY, reason_category="defective", prior_denied_categories={"defective"},
    )
    assert d.decision == "APPROVE"


# --- R9: serial-return abuse ------------------------------------------------

def test_abuse_escalates():
    d = evaluate_refund(_order(), 1, TODAY, prior_refund_count=2)
    assert d.decision == "ESCALATE"
    assert "R9_refund_abuse" in d.matched_rules


def test_abuse_below_threshold_approves():
    d = evaluate_refund(_order(), 1, TODAY, prior_refund_count=1)
    assert d.decision == "APPROVE"
