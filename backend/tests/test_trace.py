from app.agent.trace import (
    TraceRecorder, compute_cost, save_trace, get_trace, list_trace_summaries,
)


def test_compute_cost():
    assert compute_cost(1_000_000, 1_000_000) == 18.0


def test_compute_cost_with_cache():
    # 1M cache_read @ 0.1*3 = 0.30 ; 1M cache_write @ 1.25*3 = 3.75 ; 1M output @ 15 = 15
    c = compute_cost(0, 1_000_000, cache_read=1_000_000, cache_write=1_000_000)
    assert round(c, 4) == round(0.30 + 3.75 + 15, 4)


def test_recorder_finalize_totals():
    r = TraceRecorder("sess-1", 1, "Alice Tan", "hi")
    r.add_step("llm_call", "claude", output="hi", tokens_in=1000, tokens_out=200, latency_ms=300)
    r.add_step("tool_call", "get_order", input={"order_id": 1001}, output="{}", latency_ms=5)
    t = r.finalize("approved")
    assert t.step_count == 2
    assert t.total_tokens_in == 1000
    assert t.total_tokens_out == 200
    assert t.decision == "approved"


def test_persist_roundtrip(seeded_conn):
    r = TraceRecorder("sess-1", 1, "Alice Tan", "refund please")
    r.add_step("llm_call", "claude", output="ok", tokens_in=500, tokens_out=50, latency_ms=120)
    t = r.finalize("denied")
    save_trace(seeded_conn, t)
    got = get_trace(seeded_conn, t.trace_id)
    assert got is not None
    assert got.trace_id == t.trace_id
    assert len(got.steps) == 1
    assert got.steps[0].name == "claude"
    summaries = list_trace_summaries(seeded_conn)
    assert any(s.trace_id == t.trace_id and s.decision == "denied" for s in summaries)
