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


def test_security_note_injected_when_flagged():
    p = build_system_prompt({"name": "Alice Tan", "id": 1, "tier": "standard"},
                            manipulation_flags=["authority_claim"])
    assert "SECURITY ALERT" in p
    assert "authority_claim" in p
