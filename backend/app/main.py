from contextlib import asynccontextmanager

import anthropic
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.agent.graph import arm_fault, build_graph, run_turn
from app.agent.prompts import load_policy_text
from app.agent.trace import get_trace, list_trace_summaries, save_trace
from app.config import settings
from app.data import crm
from app.data.db import connect
from app.data.seed import ensure_seeded
from app.models import ChatRequest, ChatResponse, OrderUpdate
from app.observability import log_event, setup_logging, setup_otel

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    setup_otel()
    ensure_seeded(settings.db_path)
    yield


app = FastAPI(title="Refund Support Agent", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

SESSIONS: dict[str, dict] = {}
_GRAPH = build_graph()
_CLIENT = None


def get_client():
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = anthropic.Anthropic(api_key=settings.anthropic_api_key or None, max_retries=0)
    return _CLIENT


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/debug/fault")
def debug_fault(mode: str = "off"):
    """Demo-only chaos hook: arm a transient ('retry') or hard ('fail') fault on the
    next agent call, so a failed/retried step can be demonstrated and debugged."""
    if not settings.enable_fault_injection:
        raise HTTPException(status_code=403, detail="Fault injection disabled")
    state = arm_fault(mode)
    log_event("fault_armed", mode=mode, state=state)
    return {"armed": state}


@app.get("/api/policy")
def policy():
    return {"policy": load_policy_text()}


@app.get("/api/customers")
def customers():
    conn = connect(settings.db_path)
    try:
        return {"customers": crm.list_customers_with_orders(conn)}
    finally:
        conn.close()


@app.get("/api/orders")
def orders():
    conn = connect(settings.db_path)
    try:
        return {"orders": crm.list_all_orders(conn)}
    finally:
        conn.close()


@app.patch("/api/orders/{order_id}")
def patch_order(order_id: int, body: OrderUpdate):
    if body.status is not None and body.status not in crm.ALLOWED_ORDER_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status")
    conn = connect(settings.db_path)
    try:
        updated = crm.update_order(
            conn, order_id,
            status=body.status, is_refunded=body.is_refunded, is_final_sale=body.is_final_sale,
        )
        if updated is None:
            raise HTTPException(status_code=404, detail="Order not found")
        return updated
    finally:
        conn.close()


def _parse_image(data_url):
    """Turn a 'data:image/...;base64,XXX' data URL into {media_type, data}, or None."""
    if not data_url:
        return None
    try:
        header, b64 = data_url.split(",", 1)
        media_type = header.split(";")[0].split(":", 1)[1]
    except (ValueError, IndexError):
        return None
    if not b64 or not media_type.startswith("image/"):
        return None
    return {"media_type": media_type, "data": b64}


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    conn = connect(settings.db_path)
    try:
        customer = crm.get_customer(conn, req.customer_id)
        if customer is None:
            raise HTTPException(status_code=404, detail="Unknown customer")
        session = SESSIONS.get(req.session_id)
        if session is None:
            # New chat: snapshot the customer's prior tickets once (stays cache-stable
            # for the whole chat; this chat's own messages provide in-conversation context).
            session = SESSIONS[req.session_id] = {
                "customer_id": req.customer_id,
                "messages": [],
                "tickets": crm.get_customer_tickets(conn, req.customer_id),
                "has_evidence": False,
            }
        image = _parse_image(req.image)
        if image:
            session["has_evidence"] = True  # a real photo exists; "evidence" can't be faked with words
        reply, decision, options, awaiting_photo, trace, messages = run_turn(
            _GRAPH, get_client(), conn, req.session_id, customer, session["messages"], req.message,
            tickets=session["tickets"], image=image, has_evidence=session.get("has_evidence", False),
        )
        session["messages"] = messages
        save_trace(conn, trace)
        return ChatResponse(reply=reply, decision=decision, options=options,
                            awaiting_photo=awaiting_photo, trace_id=trace.trace_id, session_id=req.session_id)
    finally:
        conn.close()


@app.get("/api/traces")
def traces(limit: int = 50):
    conn = connect(settings.db_path)
    try:
        return {"traces": [s.model_dump() for s in list_trace_summaries(conn, limit)]}
    finally:
        conn.close()


@app.get("/api/traces/{trace_id}")
def trace_detail(trace_id: str):
    conn = connect(settings.db_path)
    try:
        t = get_trace(conn, trace_id)
        if t is None:
            raise HTTPException(status_code=404, detail="Trace not found")
        return t.model_dump()
    finally:
        conn.close()
