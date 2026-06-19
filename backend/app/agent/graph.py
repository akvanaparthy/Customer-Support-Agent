import time
from datetime import date
from typing import Any, Optional, TypedDict

import anthropic
from langgraph.graph import END, StateGraph

from app.agent.prompts import build_system_prompt
from app.agent.tools import TOOL_SCHEMAS, ToolContext, execute_tool
from app.agent.trace import TraceRecorder
from app.config import settings

RETRYABLE = (
    anthropic.RateLimitError,
    anthropic.APITimeoutError,
    anthropic.APIConnectionError,
    anthropic.InternalServerError,
)


class AgentState(TypedDict):
    messages: list
    client: Any
    conn: Any
    customer: dict
    today: date
    recorder: TraceRecorder
    decision: Optional[str]
    system: str


def _has_tool_use(content) -> bool:
    return any(getattr(b, "type", None) == "tool_use" for b in content)


def call_llm_with_retry(state: AgentState, max_attempts: int = 3):
    client, recorder = state["client"], state["recorder"]
    last_exc = None
    for attempt in range(max_attempts):
        start = time.perf_counter()
        try:
            resp = client.messages.create(
                model=settings.model,
                max_tokens=settings.max_tokens,
                system=state["system"],
                messages=state["messages"],
                tools=TOOL_SCHEMAS,
            )
            latency = int((time.perf_counter() - start) * 1000)
            text_out = "".join(
                getattr(b, "text", "") for b in resp.content if getattr(b, "type", None) == "text"
            )
            recorder.add_step(
                "llm_call", "claude",
                input={"messages_in_context": len(state["messages"]), "attempt": attempt + 1},
                output=text_out or "[requested tool call]",
                tokens_in=resp.usage.input_tokens, tokens_out=resp.usage.output_tokens,
                latency_ms=latency,
            )
            return resp
        except RETRYABLE as exc:
            latency = int((time.perf_counter() - start) * 1000)
            last_exc = exc
            recorder.add_step(
                "retry", "claude", input={"attempt": attempt + 1},
                output=f"{type(exc).__name__}: {exc}", latency_ms=latency, status="retried",
            )
            time.sleep(min(2 ** attempt * 0.5, 4))
    recorder.add_step("error", "claude",
                      output=f"LLM failed after {max_attempts} attempts: {last_exc}", status="error")
    raise last_exc


def agent_node(state: AgentState):
    resp = call_llm_with_retry(state)
    state["messages"].append({"role": "assistant", "content": resp.content})
    return {"messages": state["messages"]}


def tools_node(state: AgentState):
    last = state["messages"][-1]["content"]
    ctx = ToolContext(conn=state["conn"], customer_id=state["customer"]["id"], today=state["today"])
    recorder = state["recorder"]
    decision = state.get("decision")
    results = []
    for block in last:
        if getattr(block, "type", None) != "tool_use":
            continue
        start = time.perf_counter()
        res = execute_tool(block.name, block.input, ctx)
        latency = int((time.perf_counter() - start) * 1000)
        recorder.add_step(
            "tool_call", block.name, input=block.input, output=res.content,
            latency_ms=latency, status="error" if res.is_error else "ok",
        )
        if res.decision:
            decision = res.decision
        results.append({"type": "tool_result", "tool_use_id": block.id,
                        "content": res.content, "is_error": res.is_error})
    state["messages"].append({"role": "user", "content": results})
    return {"messages": state["messages"], "decision": decision}


def _should_continue(state: AgentState):
    return "tools" if _has_tool_use(state["messages"][-1]["content"]) else "end"


def build_graph():
    b = StateGraph(AgentState)
    b.add_node("agent", agent_node)
    b.add_node("tools", tools_node)
    b.set_entry_point("agent")
    b.add_conditional_edges("agent", _should_continue, {"tools": "tools", "end": END})
    b.add_edge("tools", "agent")
    return b.compile()


def run_turn(graph, client, conn, session_id, customer, history, user_message):
    recorder = TraceRecorder(session_id, customer["id"], customer["name"], user_message)
    messages = list(history) + [{"role": "user", "content": user_message}]
    state: AgentState = {
        "messages": messages, "client": client, "conn": conn, "customer": customer,
        "today": date.today(), "recorder": recorder, "decision": None,
        "system": build_system_prompt(customer),
    }
    final = graph.invoke(state)
    reply = ""
    for msg in reversed(final["messages"]):
        if msg["role"] == "assistant":
            reply = "".join(
                getattr(b, "text", "") for b in msg["content"] if getattr(b, "type", None) == "text"
            )
            break
    trace = recorder.finalize(final.get("decision"))
    return reply, final.get("decision"), trace, final["messages"]
