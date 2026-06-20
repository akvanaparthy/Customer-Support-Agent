from dataclasses import dataclass, field
from datetime import date

from app.config import settings

# Physical-condition claims that can't be verified remotely and would otherwise
# let a change-of-mind bypass the 14-day window by re-labelling.
LATE_VERIFY_CATEGORIES = {"defective", "damaged"}

# Claims the system cannot confirm from data — the customer just asserts them.
# These require a product photo before payout (R13) and human review if the
# customer already has refund/ticket history (R12).
UNVERIFIABLE_CATEGORIES = {"defective", "damaged", "wrong_item", "not_as_described"}


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
    prior_denied_categories=(),
    evidence_provided: bool = True,
    has_history: bool = False,
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

    # R10 — defect/damage claims past the change-of-mind window can't be verified
    # remotely; a human checks before paying (closes the 'just say defective' bypass of R8).
    if (reason_category in LATE_VERIFY_CATEGORIES and days is not None
            and settings.buyer_remorse_window_days < days <= settings.refund_window_days):
        escalate_rules.append("R10_late_defect_review")
        escalate_reasons.append(
            f"{reason_category.capitalize()} claim on an item delivered {days} days ago (past the "
            f"{settings.buyer_remorse_window_days}-day change-of-mind window) requires human verification."
        )

    # R11 — reason shopping: this order was already denied under a different reason.
    shopped = sorted(c for c in prior_denied_categories if c and c != reason_category)
    if reason_category and shopped:
        escalate_rules.append("R11_reason_shopping")
        escalate_reasons.append(
            f"This order was previously denied under a different reason ({', '.join(shopped)}); "
            f"a changed reason ('{reason_category}') is flagged for human review."
        )

    # R13 / R12 — unverifiable claims need photo evidence; with refund/ticket history
    # they go to a human even with a photo.
    if reason_category in UNVERIFIABLE_CATEGORIES and not evidence_provided:
        escalate_rules.append("R13_evidence_required")
        escalate_reasons.append(
            f"A '{reason_category}' claim cannot be confirmed from records; a product photo "
            "(with the receipt in frame) is required before it can be approved."
        )
    elif reason_category in UNVERIFIABLE_CATEGORIES and has_history:
        escalate_rules.append("R12_history_review")
        escalate_reasons.append(
            "Customer has prior refund/ticket history; unverifiable claims on this account "
            "are reviewed by a human even with a photo."
        )

    if escalate_rules:
        return PolicyDecision("ESCALATE", escalate_reasons, escalate_rules)

    return PolicyDecision("APPROVE", ["Order meets all refund criteria."], [])
