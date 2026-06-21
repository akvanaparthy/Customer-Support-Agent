import json
import time
from datetime import date
from typing import Any, Optional, TypedDict

import anthropic
from langgraph.graph import END, StateGraph
from opentelemetry.trace import Status, StatusCode, use_span

from app.agent.guardrails import (
    build_security_reminder,
    detect_manipulation,
    sanitize_output,
    validate_output,
)
from app.agent.prompts import build_system_prompt
from app.agent.tools import TOOL_SCHEMAS, ToolContext, ToolResult, execute_tool
from app.agent.trace import TraceRecorder
from app.config import settings
from app.observability import log_event, tracer

RETRYABLE = (
    anthropic.RateLimitError,
    anthropic.APITimeoutError,
    anthropic.APIConnectionError,
    anthropic.InternalServerError,
)


class _InjectedFault(Exception):
    """Synthetic transient failure for demonstrating retry/error handling on camera."""


_FAULT = {"mode": "off", "remaining": 0}


def arm_fault(mode: str) -> dict:
    """Arm a one-shot fault for the NEXT llm call(s): 'retry' (one transient failure then
    recovers), 'fail' (exhausts retries -> error step), or 'off'. Demo-only."""
    if mode == "retry":
        _FAULT.update(mode="retry", remaining=1)
    elif mode == "fail":
        _FAULT.update(mode="fail", remaining=99)
    else:
        _FAULT.update(mode="off", remaining=0)
    return dict(_FAULT)


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
        with tracer.start_as_current_span("gen_ai.chat") as span:
            span.set_attribute("gen_ai.system", "anthropic")
            span.set_attribute("gen_ai.request.model", settings.model)
            span.set_attribute("gen_ai.attempt", attempt + 1)
            try:
                if _FAULT["remaining"] > 0:
                    _FAULT["remaining"] -= 1
                    raise _InjectedFault("Simulated transient API failure (injected for demo)")
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
                span.set_attribute("gen_ai.usage.input_tokens", resp.usage.input_tokens)
                span.set_attribute("gen_ai.usage.output_tokens", resp.usage.output_tokens)
                span.set_attribute("gen_ai.latency_ms", latency)
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
            except (*RETRYABLE, _InjectedFault) as exc:
                latency = int((time.perf_counter() - start) * 1000)
                last_exc = exc
                span.set_status(Status(StatusCode.ERROR, str(exc)))
                span.record_exception(exc)
                recorder.add_step(
                    "retry", "claude", input={"attempt": attempt + 1},
                    output=f"{type(exc).__name__}: {exc}", latency_ms=latency, status="retried",
                )
                log_event("llm_retry", trace_id=recorder.trace_id, attempt=attempt + 1,
                          error=f"{type(exc).__name__}: {exc}")
                time.sleep(min(2 ** attempt * 0.5, 4))
    recorder.add_step("error", "claude",
                      output=f"LLM failed after {max_attempts} attempts: {last_exc}", status="error")
    log_event("llm_error", trace_id=recorder.trace_id, error=str(last_exc))
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
        with tracer.start_as_current_span(f"tool.{block.name}") as span:
            try:
                res = execute_tool(block.name, block.input, ctx)
            except Exception as exc:  # a tool bug must not crash the whole turn
                res = ToolResult(json.dumps({"error": "internal_error", "message": str(exc)}), is_error=True)
            span.set_attribute("tool.name", block.name)
            span.set_attribute("tool.is_error", res.is_error)
            if res.is_error:
                span.set_status(Status(StatusCode.ERROR))
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
    log_event("turn_start", trace_id=recorder.trace_id, session_id=session_id,
              customer_id=customer["id"], has_image=bool(image), flags=flags or None)
    turn_span = tracer.start_span("refund_agent.turn")
    turn_span.set_attribute("app.trace_id", recorder.trace_id)
    turn_span.set_attribute("session.id", session_id)
    turn_span.set_attribute("customer.id", customer["id"])
    try:
        with use_span(turn_span, end_on_exit=False):
            final = graph.invoke(state)
    except Exception as exc:
        turn_span.set_status(Status(StatusCode.ERROR, str(exc)))
        turn_span.record_exception(exc)
        turn_span.end()
        # persist the failed run so it's debuggable in the dashboard, and degrade gracefully
        if not (recorder.steps and recorder.steps[-1].status == "error"):
            recorder.add_step("error", "agent", output=f"{type(exc).__name__}: {exc}", status="error")
        log_event("turn_error", trace_id=recorder.trace_id, error=f"{type(exc).__name__}: {exc}")
        trace = recorder.finalize(None)
        fallback = ("I'm sorry — something went wrong on our end and I couldn't finish that. "
                    f"Please try again in a moment. (ref: {recorder.trace_id[:8]})")
        return fallback, None, None, False, trace, list(history)

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

    turn_span.set_attribute("refund.decision", decision or "none")
    turn_span.end()
    trace = recorder.finalize(decision)
    return reply, decision, options, awaiting_photo, trace, final["messages"]
