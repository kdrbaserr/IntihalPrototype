from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi import HTTPException as APIHTTPException
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from intihal_api.core.diagnostics import log_error, request_id
from intihal_api.core.errors import PUBLIC_MESSAGES
from intihal_api.core.redaction import safe_route

DEFAULT_CODES = {
    401: "authentication_required",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    422: "validation_error",
    503: "storage_unavailable",
}


def error_response(status: int, code: str, identifier: str, headers=None) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        headers={**(headers or {}), "Cache-Control": "no-store"},
        content={
            "detail": {"code": code, "message": PUBLIC_MESSAGES[code], "trace_id": identifier}
        },
    )


class RequestDiagnosticsMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        identifier = uuid4().hex  # don't trust a client-supplied correlation header
        token = request_id.set(identifier)
        started = False

        async def traced_send(message: Message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
                message["headers"] = [
                    (key, value)
                    for key, value in message.get("headers", [])
                    if key.lower() != b"x-request-id"
                ] + [(b"x-request-id", identifier.encode())]
            await send(message)

        try:
            await self.app(scope, receive, traced_send)
        except HTTPException as error:
            if started:
                raise RuntimeError(f"Response interrupted; trace_id={identifier}") from None
            code = error.detail.get("code") if isinstance(error.detail, dict) else None
            code = code if isinstance(code, str) and code in PUBLIC_MESSAGES else "invalid_request"
            log_error(
                error,
                code=code,
                event="http_expected_error",
                http_status=error.status_code,
                method=scope["method"],
                route=safe_route(scope),
            )
            await error_response(error.status_code, code, identifier, error.headers)(
                scope, receive, traced_send
            )
        except Exception as error:
            log_error(
                error,
                code="internal_error",
                event="http_unhandled_error",
                http_status=500,
                method=scope["method"],
                route=safe_route(scope),
            )
            if started:
                raise RuntimeError(f"Response interrupted; trace_id={identifier}") from None
            await error_response(500, "internal_error", identifier)(scope, receive, traced_send)
        finally:
            request_id.reset(token)


def install_error_handling(application: FastAPI) -> None:
    application.add_middleware(RequestDiagnosticsMiddleware)

    @application.exception_handler(HTTPException)
    async def http_error(request: Request, error: HTTPException):
        if request.scope.get("intihal_upload_limit_exceeded"):
            error = APIHTTPException(413, detail={"code": "request_too_large"})
        provided = error.detail.get("code") if isinstance(error.detail, dict) else None
        code = (
            provided
            if isinstance(provided, str) and provided in PUBLIC_MESSAGES
            else DEFAULT_CODES.get(
                error.status_code,
                "internal_error" if error.status_code >= 500 else "invalid_request",
            )
        )
        identifier = log_error(
            error,
            code=code,
            event="http_expected_error",
            http_status=error.status_code,
            method=request.method,
            route=safe_route(request.scope),
        )
        return error_response(error.status_code, code, identifier, error.headers)

    @application.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError):
        identifier = log_error(
            error,
            code="validation_error",
            event="http_validation_error",
            http_status=422,
            method=request.method,
            route=safe_route(request.scope),
        )
        return error_response(422, "validation_error", identifier)
