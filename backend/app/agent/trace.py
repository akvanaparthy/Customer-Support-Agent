import json
import uuid
from datetime import datetime, timezone

from app.config import settings
from app.models import Trace, TraceStep, TraceSummary


def compute_cost(tokens_in: int, tokens_out: int) -> float:
    return (tokens_in / 1_000_000) * settings.price_input_per_mtok + (
        tokens_out / 1_000_000
    ) * settings.price_output_per_mtok


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class TraceRecorder:
    def __init__(self, session_id, customer_id, customer_name, user_message):
        self.trace_id = uuid.uuid4().hex[:12]
        self.session_id = session_id
        self.customer_id = customer_id
        self.customer_name = customer_name
        self.user_message = user_message
        self.timestamp = now_iso()
        self.steps: list[TraceStep] = []

    def add_step(self, type, name, input=None, output=None,
                 tokens_in=0, tokens_out=0, latency_ms=0, status="ok"):
        self.steps.append(TraceStep(
            type=type, name=name, input=input, output=output,
            tokens_in=tokens_in, tokens_out=tokens_out, latency_ms=latency_ms,
            cost_usd=compute_cost(tokens_in, tokens_out), status=status,
        ))

    def finalize(self, decision) -> Trace:
        return Trace(
            trace_id=self.trace_id, session_id=self.session_id,
            customer_id=self.customer_id, customer_name=self.customer_name,
            timestamp=self.timestamp, user_message=self.user_message, decision=decision,
            steps=self.steps,
            total_tokens_in=sum(s.tokens_in for s in self.steps),
            total_tokens_out=sum(s.tokens_out for s in self.steps),
            total_cost_usd=round(sum(s.cost_usd for s in self.steps), 6),
            total_latency_ms=sum(s.latency_ms for s in self.steps),
            step_count=len(self.steps),
        )


def save_trace(conn, trace: Trace) -> None:
    conn.execute(
        """INSERT OR REPLACE INTO traces
           (trace_id, session_id, customer_id, customer_name, timestamp, user_message,
            decision, total_tokens_in, total_tokens_out, total_cost_usd, total_latency_ms,
            step_count, steps_json)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (trace.trace_id, trace.session_id, trace.customer_id, trace.customer_name,
         trace.timestamp, trace.user_message, trace.decision, trace.total_tokens_in,
         trace.total_tokens_out, trace.total_cost_usd, trace.total_latency_ms,
         trace.step_count, json.dumps([s.model_dump() for s in trace.steps])),
    )
    conn.commit()


def get_trace(conn, trace_id: str) -> Trace | None:
    row = conn.execute("SELECT * FROM traces WHERE trace_id = ?", (trace_id,)).fetchone()
    if row is None:
        return None
    return Trace(
        trace_id=row["trace_id"], session_id=row["session_id"], customer_id=row["customer_id"],
        customer_name=row["customer_name"], timestamp=row["timestamp"],
        user_message=row["user_message"], decision=row["decision"],
        steps=[TraceStep(**s) for s in json.loads(row["steps_json"])],
        total_tokens_in=row["total_tokens_in"], total_tokens_out=row["total_tokens_out"],
        total_cost_usd=row["total_cost_usd"], total_latency_ms=row["total_latency_ms"],
        step_count=row["step_count"],
    )


def list_trace_summaries(conn, limit: int = 50) -> list[TraceSummary]:
    rows = conn.execute(
        """SELECT trace_id, session_id, customer_name, timestamp, user_message, decision,
                  total_tokens_in, total_tokens_out, total_cost_usd, total_latency_ms, step_count
           FROM traces ORDER BY timestamp DESC LIMIT ?""",
        (limit,),
    ).fetchall()
    return [TraceSummary(**dict(r)) for r in rows]
