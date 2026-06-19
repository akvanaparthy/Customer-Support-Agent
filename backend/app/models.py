from typing import Any, Optional

from pydantic import BaseModel


class TraceStep(BaseModel):
    type: str  # llm_call | tool_call | retry | error
    name: str
    input: Any = None
    output: Any = None
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: int = 0
    cost_usd: float = 0.0
    status: str = "ok"  # ok | retried | error
    context: Any = None  # for llm_call steps: the exact {system, messages} sent to the model


class Trace(BaseModel):
    trace_id: str
    session_id: str
    customer_id: Optional[int] = None
    customer_name: Optional[str] = None
    timestamp: str
    user_message: str
    decision: Optional[str] = None
    steps: list[TraceStep] = []
    total_tokens_in: int = 0
    total_tokens_out: int = 0
    total_cost_usd: float = 0.0
    total_latency_ms: int = 0
    step_count: int = 0


class TraceSummary(BaseModel):
    trace_id: str
    session_id: str
    customer_name: Optional[str] = None
    timestamp: str
    user_message: str
    decision: Optional[str] = None
    total_tokens_in: int = 0
    total_tokens_out: int = 0
    total_cost_usd: float = 0.0
    total_latency_ms: int = 0
    step_count: int = 0


class ChatRequest(BaseModel):
    session_id: str
    customer_id: int
    message: str


class ChatResponse(BaseModel):
    reply: str
    decision: Optional[str] = None
    trace_id: str
    session_id: str


class OrderUpdate(BaseModel):
    status: Optional[str] = None
    is_refunded: Optional[bool] = None
    is_final_sale: Optional[bool] = None
