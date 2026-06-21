import json
from dataclasses import dataclass
from datetime import date

from app.agent.trace import now_iso
from app.data import crm
from app.data.policy_engine import evaluate_refund

_BADGE = {"APPROVE": "approved", "DENY": "denied", "ESCALATE": "escalated"}

REASON_CATEGORIES = [
    "defective", "damaged", "wrong_item", "not_as_described", "arrived_late", "changed_mind", "other",
]


@dataclass
class ToolContext:
    conn: object
    customer_id: int
    today: date
    has_evidence: bool = False  # a photo was actually uploaded this chat (backend-tracked)


@dataclass
class ToolResult:
    content: str
    is_error: bool = False
    decision: str | None = None
    prompt: dict | None = None  # {question, options} -> ends the turn, UI shows buttons


def _order_view(o: dict) -> dict:
    return {
        "id": o["id"], "item_name": o["item_name"], "category": o["category"],
        "amount": o["amount"], "status": o["status"], "order_date": o["order_date"],
        "delivered_date": o["delivered_date"],
        "is_final_sale": bool(o["is_final_sale"]), "is_refunded": bool(o["is_refunded"]),
    }


TOOL_SCHEMAS = [
    {
        "name": "get_customer",
        "description": "Get the current customer's profile (name, email, tier).",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "list_orders",
        "description": "List all orders belonging to the current customer.",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "get_order",
        "description": "Get details for one order by its order number. Fails if the order does not belong to the current customer.",
        "input_schema": {
            "type": "object",
            "properties": {"order_id": {"type": "integer", "description": "The order number."}},
            "required": ["order_id"], "additionalProperties": False,
        },
    },
    {
        "name": "check_refund_eligibility",
        "description": "Check, without acting, whether an order is refundable under policy. Pass the reason_category once you know it for an accurate check. Returns decision (APPROVE/DENY/ESCALATE), reasons, and matched rule IDs.",
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {"type": "integer"},
                "reason_category": {"type": "string", "enum": REASON_CATEGORIES,
                                    "description": "Why the customer wants a refund, if known."},
            },
            "required": ["order_id"], "additionalProperties": False,
        },
    },
    {
        "name": "issue_refund",
        "description": "Attempt to issue a refund. Requires a concrete reason and reason_category gathered from the customer (policy R7). The system re-validates against the policy engine and refuses anything ineligible. Only call after confirming eligibility and getting the customer's go-ahead.",
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {"type": "integer"},
                "reason": {"type": "string", "description": "The specific reason the customer gave."},
                "reason_category": {"type": "string", "enum": REASON_CATEGORIES},
                "evidence_has_receipt": {
                    "type": "boolean",
                    "description": "For unverifiable claims only: set true ONLY if the uploaded photo clearly shows a receipt/bill matching this order alongside the product. A product-only photo (no receipt) must be false.",
                },
            },
            "required": ["order_id", "reason", "reason_category"], "additionalProperties": False,
        },
    },
    {
        "name": "escalate_to_human",
        "description": "Escalate an order to a human agent (e.g. refunds over $500 or accounts flagged for review). Records an escalation ticket.",
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {"type": "integer"},
                "reason": {"type": "string", "description": "Why this is being escalated."},
            },
            "required": ["order_id", "reason"], "additionalProperties": False,
        },
    },
    {
        "name": "ask_user",
        "description": "Ask the customer to pick from a fixed set of options instead of typing. The UI shows buttons and locks free-text input until they choose. Use for bounded choices — which order they mean, or what the issue is.",
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "Short question shown above the options."},
                "options": {"type": "array", "items": {"type": "string"},
                            "description": "2-8 short choices to show as buttons."},
            },
            "required": ["question", "options"], "additionalProperties": False,
        },
    },
    {
        "name": "request_evidence",
        "description": "Ask the customer to upload a PHOTO as evidence for an unverifiable claim (defective / damaged / wrong item / not as described). The UI shows a photo uploader and locks text until they upload. Always ask for the product AND the receipt/bill in the same frame.",
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "What to ask the customer to photograph."},
            },
            "required": ["message"], "additionalProperties": False,
        },
    },
]


def _get_owned_order(ctx: ToolContext, order_id):
    o = crm.get_order(ctx.conn, order_id)
    if o is None:
        return None, ToolResult(f"No order #{order_id} exists.", is_error=True)
    if o["customer_id"] != ctx.customer_id:
        return None, ToolResult(f"Order #{order_id} does not belong to this customer's account.", is_error=True)
    return o, None


def execute_tool(name: str, tool_input: dict, ctx: ToolContext) -> ToolResult:
    if name == "get_customer":
        c = crm.get_customer(ctx.conn, ctx.customer_id)
        return ToolResult(json.dumps({"id": c["id"], "name": c["name"], "email": c["email"], "tier": c["tier"]}))

    if name == "list_orders":
        orders = crm.list_orders(ctx.conn, ctx.customer_id)
        return ToolResult(json.dumps([_order_view(o) for o in orders]))

    if name == "get_order":
        o, err = _get_owned_order(ctx, tool_input.get("order_id"))
        return err if err else ToolResult(json.dumps(_order_view(o)))

    if name == "check_refund_eligibility":
        o, err = _get_owned_order(ctx, tool_input.get("order_id"))
        if err:
            return err
        category = tool_input.get("reason_category")
        prior = crm.count_prior_refunds(ctx.conn, ctx.customer_id)
        prior_denied = crm.prior_denied_categories(ctx.conn, o["id"])
        has_history = crm.has_prior_activity(ctx.conn, ctx.customer_id, o["id"])
        d = evaluate_refund(o, ctx.customer_id, ctx.today, reason_category=category,
                            prior_refund_count=prior, prior_denied_categories=prior_denied,
                            evidence_provided=ctx.has_evidence, has_history=has_history)
        if category:
            crm.log_claim(ctx.conn, o["id"], ctx.customer_id, category, _BADGE[d.decision], now_iso())
        badge = _BADGE[d.decision] if d.decision != "APPROVE" else None
        return ToolResult(
            json.dumps({"decision": d.decision, "reasons": d.reasons, "matched_rules": d.matched_rules}),
            decision=badge,
        )

    if name == "issue_refund":
        o, err = _get_owned_order(ctx, tool_input.get("order_id"))
        if err:
            return err
        reason = (tool_input.get("reason") or "").strip()
        category = tool_input.get("reason_category")
        if not reason or category not in REASON_CATEGORIES:
            return ToolResult(
                json.dumps({"refunded": False, "error": "reason_required",
                            "message": "A specific reason and reason_category are required before a refund can be issued (policy R7). Ask the customer what went wrong first."}),
                is_error=True,
            )
        prior = crm.count_prior_refunds(ctx.conn, ctx.customer_id)
        prior_denied = crm.prior_denied_categories(ctx.conn, o["id"])
        has_history = crm.has_prior_activity(ctx.conn, ctx.customer_id, o["id"])
        d = evaluate_refund(o, ctx.customer_id, ctx.today, reason_category=category,
                            prior_refund_count=prior, prior_denied_categories=prior_denied,
                            evidence_provided=ctx.has_evidence,
                            evidence_has_receipt=bool(tool_input.get("evidence_has_receipt", False)),
                            has_history=has_history)
        crm.log_claim(ctx.conn, o["id"], ctx.customer_id, category, _BADGE[d.decision], now_iso())
        if d.decision != "APPROVE":
            crm.record_refund(ctx.conn, o["id"], o["amount"], _BADGE[d.decision],
                              f"[{category}] {reason} | " + "; ".join(d.reasons), now_iso())
            return ToolResult(
                json.dumps({"refunded": False, "decision": d.decision, "reasons": d.reasons,
                            "matched_rules": d.matched_rules, "message": "Refund refused by policy engine."}),
                decision=_BADGE[d.decision],
            )
        crm.mark_order_refunded(ctx.conn, o["id"], now_iso()[:10])
        crm.record_refund(ctx.conn, o["id"], o["amount"], "approved", f"[{category}] {reason}", now_iso())
        return ToolResult(
            json.dumps({"refunded": True, "amount": o["amount"], "reason_category": category,
                        "message": f"Refund of ${o['amount']:.2f} issued for order #{o['id']}."}),
            decision="approved",
        )

    if name == "escalate_to_human":
        o, err = _get_owned_order(ctx, tool_input.get("order_id"))
        if err:
            return err
        reason = tool_input.get("reason", "Escalated to a human agent.")
        ticket = f"ESC-{o['id']}"
        crm.record_refund(ctx.conn, o["id"], o["amount"], "escalated", reason, now_iso())
        return ToolResult(
            json.dumps({"escalated": True, "ticket_id": ticket,
                        "message": f"Escalated order #{o['id']} to a human agent. Ticket {ticket}."}),
            decision="escalated",
        )

    if name == "ask_user":
        question = tool_input.get("question") or "Please choose an option:"
        options = [str(o) for o in (tool_input.get("options") or [])]
        return ToolResult(
            json.dumps({"presented": True, "question": question, "options": options}),
            prompt={"question": question, "options": options},
        )

    if name == "request_evidence":
        msg = tool_input.get("message") or "Please upload a clear photo of the product, with your receipt in the same frame."
        return ToolResult(
            json.dumps({"requested": True, "message": msg}),
            prompt={"question": msg, "photo": True},
        )

    return ToolResult(f"Unknown tool: {name}", is_error=True)
