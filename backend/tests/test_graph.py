import types

import app.agent.graph as graph_mod
from app.agent.graph import arm_fault, build_graph, run_turn


class FakeUsage:
    def __init__(self, i, o):
        self.input_tokens, self.output_tokens = i, o


def _text(t):
    return types.SimpleNamespace(type="text", text=t)


def _tool(id, name, inp):
    return types.SimpleNamespace(type="tool_use", id=id, name=name, input=inp)


class FakeResp:
    def __init__(self, content, stop, usage):
        self.content, self.stop_reason, self.usage = content, stop, usage


class FakeMessages:
    def __init__(self, responses):
        self._responses, self._i = responses, 0

    def create(self, **kwargs):
        r = self._responses[self._i]
        self._i += 1
        return r


class FakeClient:
    def __init__(self, responses):
        self.messages = FakeMessages(responses)


def test_graph_runs_tool_then_finishes(seeded_conn):
    responses = [
        FakeResp([_tool("tu1", "get_order", {"order_id": 1001})], "tool_use", FakeUsage(1200, 30)),
        FakeResp([_text("Your order #1001 is Wireless Earbuds for $79.99.")], "end_turn", FakeUsage(1300, 40)),
    ]
    graph = build_graph()
    customer = {"id": 1, "name": "Alice Tan", "tier": "standard"}
    reply, decision, options, awaiting_photo, trace, messages = run_turn(
        graph, FakeClient(responses), seeded_conn, "sess-1", customer, [], "where is order 1001?"
    )
    assert "1001" in reply
    assert [s.type for s in trace.steps] == ["input_guardrail", "llm_call", "tool_call", "llm_call"]
    assert trace.total_tokens_in == 2500
    assert trace.step_count == 4


def test_output_scrubs_rule_ids(seeded_conn):
    responses = [
        FakeResp([_text("Sorry, this is denied under Rule R3 (final sale item).")], "end_turn", FakeUsage(100, 20)),
    ]
    graph = build_graph()
    customer = {"id": 1, "name": "Alice Tan", "tier": "standard"}
    reply, decision, options, awaiting_photo, trace, messages = run_turn(
        graph, FakeClient(responses), seeded_conn, "scrub", customer, [], "refund order 1002 please"
    )
    assert "R3" not in reply
    assert "Rule R" not in reply
    assert any(s.type == "output_guardrail" and s.name == "confidentiality_scrub" for s in trace.steps)


def test_ask_user_ends_turn_with_options(seeded_conn):
    responses = [
        FakeResp(
            [_text("Sure — which order is this about?"),
             _tool("tu1", "ask_user", {"question": "Which order?", "options": ["#1001 — Earbuds", "#1002 — Hoodie"]})],
            "tool_use", FakeUsage(900, 25),
        ),
    ]
    graph = build_graph()
    customer = {"id": 1, "name": "Alice Tan", "tier": "standard"}
    reply, decision, options, awaiting_photo, trace, messages = run_turn(
        graph, FakeClient(responses), seeded_conn, "pick", customer, [], "I have a problem with an order"
    )
    # the turn pauses at the picker without a second LLM round (only one FakeResp provided)
    assert options == ["#1001 — Earbuds", "#1002 — Hoodie"]
    assert "order" in reply.lower()
    assert [s.type for s in trace.steps] == ["input_guardrail", "llm_call", "tool_call"]


def test_injected_retry_recovers(seeded_conn, monkeypatch):
    monkeypatch.setattr(graph_mod.time, "sleep", lambda *a: None)
    arm_fault("retry")
    try:
        responses = [FakeResp([_text("Your order looks fine.")], "end_turn", FakeUsage(100, 20))]
        graph = build_graph()
        customer = {"id": 1, "name": "Alice Tan", "tier": "standard"}
        reply, decision, options, awaiting_photo, trace, messages = run_turn(
            graph, FakeClient(responses), seeded_conn, "fault", customer, [], "hi"
        )
        # one transient failure was retried, then the call succeeded
        assert any(s.type == "retry" for s in trace.steps)
        assert "fine" in reply.lower()
    finally:
        arm_fault("off")


def test_injected_failure_persists_trace(seeded_conn, monkeypatch):
    monkeypatch.setattr(graph_mod.time, "sleep", lambda *a: None)
    arm_fault("fail")
    try:
        graph = build_graph()
        customer = {"id": 1, "name": "Alice Tan", "tier": "standard"}
        reply, decision, options, awaiting_photo, trace, messages = run_turn(
            graph, FakeClient([]), seeded_conn, "faultf", customer, [], "hi"
        )
        # the run fails but a trace (with an error step) is still produced, and we degrade gracefully
        assert decision is None
        assert "ref:" in reply
        assert any(s.status == "error" for s in trace.steps)
    finally:
        arm_fault("off")


def test_request_evidence_awaits_photo(seeded_conn):
    responses = [
        FakeResp(
            [_text("Could you upload a photo of the item with your receipt?"),
             _tool("tu1", "request_evidence", {"message": "Upload a photo of the product with the receipt in frame."})],
            "tool_use", FakeUsage(800, 20),
        ),
    ]
    graph = build_graph()
    customer = {"id": 1, "name": "Alice Tan", "tier": "standard"}
    reply, decision, options, awaiting_photo, trace, messages = run_turn(
        graph, FakeClient(responses), seeded_conn, "ev", customer, [], "the item is defective"
    )
    assert awaiting_photo is True
    assert options is None
    assert "photo" in reply.lower() or "receipt" in reply.lower()
