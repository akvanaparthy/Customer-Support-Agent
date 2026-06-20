import json
import logging
import sys

logger = logging.getLogger("agent")
_configured = False


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
