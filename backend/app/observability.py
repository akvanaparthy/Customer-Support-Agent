import json
import logging
import sys

from opentelemetry import trace

logger = logging.getLogger("agent")
_configured = False

# No-op until setup_otel() installs a real provider, so instrumentation is always safe
# to call and adds zero overhead when telemetry is disabled.
tracer = trace.get_tracer("refund-agent")


def setup_logging() -> None:
    """Emit structured JSON log lines to stdout (one per step / event). In prod these
    would be shipped to a log aggregator and queried by trace_id."""
    global _configured
    if _configured:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    _configured = True


def log_event(event: str, **fields) -> None:
    """One structured JSON log line. trace_id is the correlation key across UI and logs."""
    logger.info(json.dumps({"event": event, **fields}, default=str))


def setup_otel() -> None:
    """Export OpenTelemetry spans over OTLP/HTTP when enabled (e.g. to Jaeger). No-op
    otherwise, so the default local/docker run stays zero-config and the agent's spans
    simply go nowhere."""
    import os

    from app.config import settings

    if not settings.otel_enabled:
        return
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    base = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318").rstrip("/")
    provider = TracerProvider(resource=Resource.create({"service.name": "refund-agent"}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{base}/v1/traces")))
    trace.set_tracer_provider(provider)
    log_event("otel_enabled", endpoint=f"{base}/v1/traces")
