import json
import logging
import traceback
from contextvars import ContextVar
from pathlib import Path
from uuid import uuid4

from intihal_api.core.errors import PUBLIC_MESSAGES
from intihal_api.core.redaction import safe_context

SAFE_EVENTS = {
    "http_unhandled_error",
    "http_expected_error",
    "http_validation_error",
    "worker_unhandled_error",
    "workflow_stage_error",
    "document_cleanup_failed",
    "source_cleanup_failed",
    "retention_cleanup_failed",
}

request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
logger = logging.getLogger(__name__)


def exception_trace(error: BaseException) -> list[dict]:
    """Keep full frame locations and cause types without arguments, SQL or locals."""
    chain = []
    seen = set()
    while error is not None and id(error) not in seen:
        seen.add(id(error))
        chain.append(
            {
                "exception_type": f"{type(error).__module__}.{type(error).__name__}",
                "frames": [
                    {
                        "file": Path(frame.f_code.co_filename).name,
                        "line": line,
                        "function": frame.f_code.co_name,
                    }
                    for frame, line in traceback.walk_tb(error.__traceback__)
                ],
            }
        )
        error = error.__cause__ or (None if error.__suppress_context__ else error.__context__)
    return chain


def log_error(error: BaseException, *, code: str, event: str, **context) -> str:
    identifier = request_id.get() or uuid4().hex
    context = safe_context(context)
    logger.log(
        logging.ERROR if context.get("http_status", 500) >= 500 else logging.WARNING,
        json.dumps(
            {
                "event": event
                if isinstance(event, str) and event in SAFE_EVENTS
                else "redacted_event",
                "code": code
                if isinstance(code, str) and code in PUBLIC_MESSAGES
                else "internal_error",
                "trace_id": identifier,
                **context,
                "trace": exception_trace(error),
            },
            ensure_ascii=False,
        ),
    )
    return identifier
