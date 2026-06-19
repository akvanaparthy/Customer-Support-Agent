from app.agent.prompts import build_system_prompt, load_policy_text


def test_load_policy_text():
    assert "Refund Policy" in load_policy_text()


def test_prompt_includes_policy_and_guardrails():
    p = build_system_prompt({"name": "Alice Tan", "id": 1, "tier": "standard"})
    assert "Alice Tan" in p
    assert "SOURCE OF TRUTH" in p
    assert "Final-sale" in p
    assert "ignore your rules" in p
