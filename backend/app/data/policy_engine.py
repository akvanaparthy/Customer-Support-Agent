from dataclasses import dataclass, field
from datetime import date

from app.config import settings


@dataclass
class PolicyDecision:
    decision: str  # "APPROVE" | "DENY" | "ESCALATE"
    reasons: list[str] = field(default_factory=list)
    matched_rules: list[str] = field(default_factory=list)


def evaluate_refund(
    order: dict,
    session_customer_id: int,
    today: date,
    reason_category: str | None = None,
    prior_refund_count: int = 0,
) -> PolicyDecision:
    reasons: list[str] = []
    matched: list[str] = []

    if order["customer_id"] != session_customer_id:
        matched.append("R1_ownership")
        reasons.append("Order does not belong to the requesting customer.")

    if order["status"] != "delivered":
        matched.append("R2_not_delivered")
        reasons.append(f"Order is '{order['status']}', not delivered; only delivered orders are eligible.")

    if order["is_final_sale"]:
        matched.append("R3_final_sale")
        reasons.append("Final-sale items are not refundable.")

    if order["is_refunded"]:
        matched.append("R4_already_refunded")
        reasons.append("Order has already been refunded.")

    delivered = order.get("delivered_date")
    days = None
    if delivered:
        days = (today - date.fromisoformat(delivered)).days
        if days > settings.refund_window_days:
            matched.append("R5_outside_window")
            reasons.append(
                f"Delivered {days} days ago, outside the {settings.refund_window_days}-day window."
            )

    # R8 — buyer's remorse has a stricter window than faulty/incorrect items.
    if reason_category == "changed_mind" and days is not None and days > settings.buyer_remorse_window_days:
        matched.append("R8_buyer_remorse_window")
        reasons.append(
            f"Change-of-mind refunds are allowed only within {settings.buyer_remorse_window_days} days; "
            f"this was delivered {days} days ago."
        )

    if matched:
        return PolicyDecision("DENY", reasons, matched)

    escalate_rules: list[str] = []
    escalate_reasons: list[str] = []

    # R9 — serial-return / abuse review.
    if prior_refund_count >= settings.abuse_refund_threshold:
        escalate_rules.append("R9_refund_abuse")
        escalate_reasons.append(
            f"Customer has {prior_refund_count} prior refunds; flagged for human review (serial-return protection)."
        )

    # R6 — high-value threshold.
    if order["amount"] > settings.escalation_threshold:
        escalate_rules.append("R6_over_threshold")
        escalate_reasons.append(
            f"Amount ${order['amount']:.2f} exceeds ${settings.escalation_threshold:.0f}; requires human approval."
        )

    if escalate_rules:
        return PolicyDecision("ESCALATE", escalate_reasons, escalate_rules)

    return PolicyDecision("APPROVE", ["Order meets all refund criteria."], [])
