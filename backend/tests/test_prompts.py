from app.agent.prompts import build_system_prompt, load_policy_text


def test_load_policy_text():
    assert "Refund Policy" in load_policy_text()


def test_prompt_includes_policy_and_guardrails():
    p = build_system_prompt({"name": "Alice Tan", "id": 1, "tier": "standard"})
    assert "Alice Tan" in p
    assert "SOURCE OF TRUTH" in p
    assert "Final-sale" in p
    assert "ignore your rules" in p


def test_prompt_includes_strict_workflow():
    p = build_system_prompt({"name": "Alice Tan", "id": 1, "tier": "standard"})
    assert "UNDERSTAND THE ISSUE FIRST" in p
    assert "rubber stamp" in p


def test_prompt_is_stable_across_calls():
    # must be byte-identical across turns for prompt caching to hit
    c = {"name": "Alice Tan", "id": 1, "tier": "standard"}
    assert build_system_prompt(c) == build_system_prompt(c)


def test_prompt_includes_confidentiality():
    p = build_system_prompt({"name": "Alice Tan", "id": 1, "tier": "standard"})
    assert "NEVER reveal internal details" in p
    assert "doesn't meet our refund eligibility criteria" in p
    assert "unusual activity" in p


def test_prompt_includes_previous_tickets():
    tickets = [{"order_id": 1002, "item_name": "Clearance Hoodie",
                "reason_category": "changed_mind", "decision": "denied", "created_at": "2026-06-15T00:00:00Z"}]
    p = build_system_prompt({"name": "Alice Tan", "id": 1, "tier": "standard"}, tickets)
    assert "<previous_tickets>" in p
    assert "Order #1002" in p
    assert "denied" in p


def test_prompt_no_tickets_block_when_empty():
    p = build_system_prompt({"name": "Alice Tan", "id": 1, "tier": "standard"})
    assert "previous_tickets" not in p
