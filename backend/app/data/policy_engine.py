from dataclasses import dataclass, field
from datetime import date

from app.config import settings


@dataclass
class PolicyDecision:
    decision: str  # "APPROVE" | "DENY" | "ESCALATE"
    reasons: list[str] = field(default_factory=list)
    matched_rules: list[str] = field(default_factory=list)


def evaluate_refund(order: dict, session_customer_id: int, today: date) -> PolicyDecision:
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
    if delivered:
        days = (today - date.fromisoformat(delivered)).days
        if days > settings.refund_window_days:
            matched.append("R5_outside_window")
            reasons.append(
                f"Delivered {days} days ago, outside the {settings.refund_window_days}-day window."
            )

    if matched:
        return PolicyDecision("DENY", reasons, matched)

    if order["amount"] > settings.escalation_threshold:
        return PolicyDecision(
            "ESCALATE",
            [f"Amount ${order['amount']:.2f} exceeds ${settings.escalation_threshold:.0f}; requires human approval."],
            ["R6_over_threshold"],
        )

    return PolicyDecision("APPROVE", ["Order meets all refund criteria."], [])
