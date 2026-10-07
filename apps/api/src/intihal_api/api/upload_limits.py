"""Bound the raw upload body before FastAPI parses or spools multipart data."""

from fastapi import HTTPException
from starlette.formparsers import MultiPartException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from intihal_api.uploads import MAX_UPLOAD_SIZE_BYTES

MAX_UPLOAD_REQUEST_BYTES = MAX_UPLOAD_SIZE_BYTES + 1024 * 1024


class UploadBodyLimitMiddleware:
    def __init__(self, app: ASGIApp, *, prefix: str):
        self.app = app
        self.paths = {f"{prefix}/documents", f"{prefix}/admin/sources"}

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] != "http"
            or scope["method"] != "POST"
            or scope["path"].rstrip("/") not in self.paths
        ):
            await self.app(scope, receive, send)
            return
        lengths = [value for key, value in scope.get("headers", []) if key == b"content-length"]
        if lengths:
            try:
                if len(lengths) != 1 or int(lengths[0]) < 0:
                    raise ValueError
                if int(lengths[0]) > MAX_UPLOAD_REQUEST_BYTES:
                    raise HTTPException(413, detail={"code": "request_too_large"})
            except ValueError as error:
                raise HTTPException(400, detail={"code": "invalid_request"}) from error
        received = 0

        async def bounded_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > MAX_UPLOAD_REQUEST_BYTES:
                    scope["intihal_upload_limit_exceeded"] = True
                    # Multipart parser closes already-spooled temporary files for this type.
                    raise MultiPartException("Upload request exceeds the size limit")
            return message

        await self.app(scope, bounded_receive, send)
