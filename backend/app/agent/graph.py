import json
import time
from datetime import date
from typing import Any, Optional, TypedDict

import anthropic
from langgraph.graph import END, StateGraph

from app.agent.guardrails import (
    build_security_reminder,
    detect_manipulation,
    sanitize_output,
    validate_output,
)
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


def _get(b, key, default=None):
    return b.get(key, default) if isinstance(b, dict) else getattr(b, key, default)


def _serialize_context(system: str, messages: list) -> dict:
    """Readable snapshot of the exact prompt sent to the model, for the trace viewer."""
    def summarize(content):
        if isinstance(content, str):
            return content[:1000]
        parts = []
        for b in content:
            t = _get(b, "type")
            if t == "text":
                parts.append((_get(b, "text", "") or "")[:1000])
            elif t == "tool_use":
                parts.append(f"[tool_use: {_get(b, 'name')}({json.dumps(_get(b, 'input'))[:300]})]")
            elif t == "tool_result":
                parts.append(f"[tool_result: {str(_get(b, 'content', ''))[:500]}]")
            else:
                parts.append(f"[{t}]")
        return "\n".join(parts)

    return {
        "system": system,
        "messages": [{"role": m["role"], "content": summarize(m["content"])} for m in messages],
    }


class AgentState(TypedDict):
    messages: list
    client: Any
    conn: Any
    customer: dict
    today: date
    recorder: TraceRecorder
    decision: Optional[str]
    system: str
    pending_prompt: Optional[dict]
    has_evidence: bool


def _has_tool_use(content) -> bool:
    return any(getattr(b, "type", None) == "tool_use" for b in content)


def _image_block(image: dict) -> dict:
    return {"type": "image", "source": {"type": "base64", "media_type": image["media_type"], "data": image["data"]}}


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
                # Prompt caching: auto-cache the stable prefix (tools + system + prior
                # turns). Each new turn reads that prefix at 0.1x instead of full price.
                cache_control={"type": "ephemeral"},
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
                cache_read=getattr(resp.usage, "cache_read_input_tokens", 0) or 0,
                cache_write=getattr(resp.usage, "cache_creation_input_tokens", 0) or 0,
                latency_ms=latency,
                context=_serialize_context(state["system"], state["messages"]),
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
    ctx = ToolContext(conn=state["conn"], customer_id=state["customer"]["id"], today=state["today"],
                      has_evidence=state.get("has_evidence", False))
    recorder = state["recorder"]
    decision = state.get("decision")
    pending = state.get("pending_prompt")
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
        if res.prompt:
            pending = res.prompt
        results.append({"type": "tool_result", "tool_use_id": block.id,
                        "content": res.content, "is_error": res.is_error})
    state["messages"].append({"role": "user", "content": results})
    return {"messages": state["messages"], "decision": decision, "pending_prompt": pending}


def _should_continue(state: AgentState):
    return "tools" if _has_tool_use(state["messages"][-1]["content"]) else "end"


def _after_tools(state: AgentState):
    # ask_user pauses the turn so the UI can collect a bounded choice from the customer.
    return "end" if state.get("pending_prompt") else "agent"


def build_graph():
    b = StateGraph(AgentState)
    b.add_node("agent", agent_node)
    b.add_node("tools", tools_node)
    b.set_entry_point("agent")
    b.add_conditional_edges("agent", _should_continue, {"tools": "tools", "end": END})
    b.add_conditional_edges("tools", _after_tools, {"agent": "agent", "end": END})
    return b.compile()


def run_turn(graph, client, conn, session_id, customer, history, user_message, tickets=(), image=None, has_evidence=False):
    recorder = TraceRecorder(session_id, customer["id"], customer["name"], user_message)

    # Layer 1 — pre-LLM input guardrail (deterministic manipulation scan).
    flags = detect_manipulation(user_message)
    recorder.add_step(
        "input_guardrail", "manipulation_scan",
        input=user_message[:300],
        output=("flagged: " + ", ".join(flags)) if flags else "no manipulation detected",
        status="flagged" if flags else "ok",
    )

    # Inject the per-turn security reminder into the USER turn (not the cached system
    # prefix) so the system prompt stays byte-identical across turns and caches cleanly.
    text = user_message
    if flags:
        text = build_security_reminder(flags) + "\n\n" + user_message
    # when the customer uploads a photo, send it as an image block the model can see
    user_content = [_image_block(image), {"type": "text", "text": text}] if image else text

    messages = list(history) + [{"role": "user", "content": user_content}]
    state: AgentState = {
        "messages": messages, "client": client, "conn": conn, "customer": customer,
        "today": date.today(), "recorder": recorder, "decision": None,
        "system": build_system_prompt(customer, tickets), "pending_prompt": None,
        "has_evidence": has_evidence,
    }
    final = graph.invoke(state)

    reply = ""
    for msg in reversed(final["messages"]):
        if msg["role"] == "assistant":
            reply = "".join(
                getattr(b, "text", "") for b in msg["content"] if getattr(b, "type", None) == "text"
            )
            break

    decision = final.get("decision")
    pending = final.get("pending_prompt")
    options = pending.get("options") if pending else None
    awaiting_photo = bool(pending and pending.get("photo"))
    if pending and not reply.strip():
        reply = pending.get("question", "")

    # Layer 5 — post-LLM output guardrails.
    # (a) block fabricated refund claims.
    ok, safe = validate_output(reply, refund_approved=(decision == "approved"))
    if not ok:
        recorder.add_step(
            "output_guardrail", "claim_validation",
            input=reply[:300], output="Blocked an unverified refund-completion claim.",
            status="flagged",
        )
        reply = safe

    # (b) scrub internal rule IDs / policy-prompt leakage from the customer reply.
    cleaned, scrubbed = sanitize_output(reply)
    if scrubbed:
        recorder.add_step(
            "output_guardrail", "confidentiality_scrub",
            input=reply[:300], output="Redacted internal policy/rule references from the customer reply.",
            status="flagged",
        )
        reply = cleaned

    trace = recorder.finalize(decision)
    return reply, decision, options, awaiting_photo, trace, final["messages"]
