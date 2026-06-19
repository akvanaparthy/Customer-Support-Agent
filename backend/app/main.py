from contextlib import asynccontextmanager

import anthropic
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.agent.graph import build_graph, run_turn
from app.agent.prompts import load_policy_text
from app.agent.trace import get_trace, list_trace_summaries, save_trace
from app.config import settings
from app.data import crm
from app.data.db import connect
from app.data.seed import ensure_seeded
from app.models import ChatRequest, ChatResponse, OrderUpdate

@asynccontextmanager
async def lifespan(app: FastAPI):
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


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    conn = connect(settings.db_path)
    try:
        customer = crm.get_customer(conn, req.customer_id)
        if customer is None:
            raise HTTPException(status_code=404, detail="Unknown customer")
        session = SESSIONS.setdefault(req.session_id, {"customer_id": req.customer_id, "messages": []})
        reply, decision, trace, messages = run_turn(
            _GRAPH, get_client(), conn, req.session_id, customer, session["messages"], req.message
        )
        session["messages"] = messages
        save_trace(conn, trace)
        return ChatResponse(reply=reply, decision=decision, trace_id=trace.trace_id, session_id=req.session_id)
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
