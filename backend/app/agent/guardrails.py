import re

# --- Pre-LLM input guardrail -------------------------------------------------
# Deterministic heuristics that flag likely manipulation BEFORE the model sees
# the message. This is defense-in-depth: the system prompt already instructs the
# model to resist, but a guardrail LLM is itself injectable, so we keep a
# code-level scan whose result is logged in the trace and reinforced in the prompt.
_PATTERNS = {
    "instruction_override": r"ignore\s+(all|any|previous|prior|your)\b|ignore\s+the\s+(policy|rules?|instructions?)|disregard\s+(the\s+)?(policy|instructions?|rules?)|override\s+(the\s+)?(policy|rules?)",
    "role_manipulation": r"you\s+are\s+now\b|act\s+as\s+(a|an|the|if|though)\b|developer\s+mode|jailbreak|\bDAN\b|pretend\s+(you|to\s+be)|new\s+persona|roleplay",
    "authority_claim": r"\bi\s+am\s+(the|your)\s+(ceo|manager|admin|administrator|supervisor|owner|boss)\b|manager\s+(approved|authoriz)|as\s+(an?|the)\s+(admin|administrator|supervisor)",
    "prompt_extraction": r"system\s+prompt|your\s+(instructions|rules|prompt)|reveal\s+(your|the)\s+(prompt|instructions|rules)|what\s+are\s+your\s+(rules|instructions)|repeat\s+(your|the)\s+(prompt|instructions)",
    "policy_bypass": r"bypass\s+(the\s+)?(policy|rules?|check)|forget\s+(the\s+)?(policy|rules?)|no\s+need\s+to\s+(check|verify)|skip\s+the\s+(policy|check)",
}


def detect_manipulation(text: str) -> list[str]:
    """Return the names of manipulation patterns present in the message (empty if clean)."""
    t = text.lower()
    return [name for name, pattern in _PATTERNS.items() if re.search(pattern, t)]


# --- Post-LLM output guardrail -----------------------------------------------
# Catch a model reply that CLAIMS a refund was completed when no refund was
# actually authorized this turn — prevents the agent from fabricating an outcome.
_REFUND_DONE = re.compile(
    r"refund\b[^.!?\n]{0,40}\b(processed|issued|completed|approved|refunded|done)\b"
    r"|\b(processed|issued|completed|approved)\b[^.!?\n]{0,20}\brefund\b"
    r"|✅\s*refunded"
    r"|status[:*\s]+refunded",
    re.IGNORECASE,
)


def claims_refund_completed(text: str) -> bool:
    return bool(_REFUND_DONE.search(text))


def validate_output(text: str, refund_approved: bool) -> tuple[bool, str]:
    """If the reply asserts a completed refund that did not actually happen, replace it."""
    if not refund_approved and claims_refund_completed(text):
        return False, (
            "I'm sorry — I can't confirm that refund. No refund was actually authorized "
            "for this request under our policy. If you can tell me the order number and "
            "what went wrong, I'll check exactly what I'm able to do."
        )
    return True, text
