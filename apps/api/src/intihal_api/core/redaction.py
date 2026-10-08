"""Fail-closed diagnostic fields and guards for libraries that can echo document text."""

import logging
from collections.abc import Mapping
from pathlib import Path
from uuid import UUID

import pymupdf

REDACTED = "[REDACTED]"
PRIVATE_LOGGERS = (
    "httpx",
    "httpcore",
    "urllib3",
    "minio",
    "pypdf",
    "pdfminer",
    "pymupdf",
    "docx",
    "charset_normalizer",
    "sqlalchemy",
)
SENSITIVE_FIELDS = {
    "email",
    "ip",
    "name",
    "phone",
    "password",
    "cookie",
    "token",
    "content",
    "body",
    "text",
    "document_text",
    "storage_key",
    "headers",
    "params",
}
LOG_RECORD_FIELDS = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {
    "message",
    "asctime",
}


class RouteTemplate(str):
    """Only server-defined route templates may enter diagnostics, never raw request URLs."""


def safe_route(scope: Mapping[str, object]) -> RouteTemplate | None:
    path = getattr(scope.get("route"), "path", None)
    return RouteTemplate(path) if path is not None else None


def safe_context(context: dict) -> dict:
    result = {}
    for key, value in context.items():
        if key in {"document_id", "analysis_id", "task_id"}:
            try:
                result[key] = str(UUID(str(value))) if value is not None else None
            except (ValueError, TypeError, AttributeError):
                result[key] = REDACTED
        elif key == "http_status" and type(value) is int and 100 <= value <= 599:
            result[key] = value
        elif key == "attempt" and type(value) is int and 0 <= value <= 1000:
            result[key] = value
        elif (
            key == "stage"
            and isinstance(value, str)
            and value
            in {
                "extract",
                "analyze",
                "dispatch",
                "retention_cleanup",
            }
        ):
            result[key] = value
        elif (
            key == "method"
            and isinstance(value, str)
            and value
            in {
                "GET",
                "POST",
                "PUT",
                "PATCH",
                "DELETE",
                "HEAD",
                "OPTIONS",
            }
        ):
            result[key] = value
        elif key == "route" and (value is None or isinstance(value, RouteTemplate)):
            result[key] = value
        elif key in SENSITIVE_FIELDS:
            result[key] = REDACTED
        else:
            # Unknown names themselves may contain PII: don't copy their keys either.
            result["redacted_fields"] = True
    return result


def private_record(record: logging.LogRecord) -> bool:
    return (
        record.name.startswith(PRIVATE_LOGGERS)
        or record.name == "uvicorn.access"
        or (record.name == "uvicorn.error" and record.levelno >= logging.ERROR)
        or (record.name.startswith("intihal_api") and record.name != "intihal_api.core.diagnostics")
    )


def redact_record(record: logging.LogRecord) -> None:
    if private_record(record):
        record.msg = REDACTED + " diagnostic from " + record.name
        record.args = ()
        record.exc_info = None
        record.exc_text = None
        record.stack_info = None
        record.pathname = Path(record.pathname).name
        for key in list(record.__dict__):
            if key not in LOG_RECORD_FIELDS:
                del record.__dict__[key]


class PrivacyFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        redact_record(record)
        return True


def install_private_logging() -> None:
    # MuPDF otherwise prints parser diagnostics directly to stderr, outside logging filters.
    pymupdf.TOOLS.mupdf_display_errors(False)
    pymupdf.TOOLS.mupdf_display_warnings(False)
    pymupdf.set_messages(pylogging=True, pylogging_name="pymupdf")
    factory = logging.getLogRecordFactory()
    if not getattr(factory, "_intihal_privacy", False):

        def private_factory(*args, **kwargs):
            record = factory(*args, **kwargs)
            redact_record(record)
            return record

        private_factory.__dict__["_intihal_privacy"] = True
        logging.setLogRecordFactory(private_factory)
    # Handler filter runs after logging's extra fields are merged into the record.
    loggers = [
        logging.getLogger(),
        *[
            logger
            for logger in logging.Logger.manager.loggerDict.values()
            if isinstance(logger, logging.Logger)
        ],
    ]
    for logger in loggers:
        for handler in logger.handlers:
            if not any(isinstance(f, PrivacyFilter) for f in handler.filters):
                handler.addFilter(PrivacyFilter())
