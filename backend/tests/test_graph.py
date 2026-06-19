import types

from app.agent.graph import build_graph, run_turn


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
    reply, decision, trace, messages = run_turn(
        graph, FakeClient(responses), seeded_conn, "sess-1", customer, [], "where is order 1001?"
    )
    assert "1001" in reply
    assert [s.type for s in trace.steps] == ["llm_call", "tool_call", "llm_call"]
    assert trace.total_tokens_in == 2500
    assert trace.step_count == 3
