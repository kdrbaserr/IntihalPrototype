import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from io import BytesIO
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from auth_helpers import session_headers
from intihal_api.api.dependencies import get_object_storage
from intihal_api.api.upload_limits import MAX_UPLOAD_REQUEST_BYTES
from intihal_api.core.diagnostics import log_error
from intihal_api.core.redaction import REDACTED, install_private_logging
from intihal_api.db.models import AuthenticationThrottle, Document, User, UserRole
from intihal_api.db.session import get_db_session
from intihal_api.main import create_app
from intihal_api.storage import ObjectStorageService
from test_admin_sources_api import FakeMinioClient
from test_auth import CSRF, auth_api, login
from test_document_workflow import database


@asynccontextmanager
async def upload_api():
    async with database() as (session, document, factory):
        owner = await session.get(User, document.owner_id)
        owner.role = UserRole.ADMIN
        await session.commit()
        headers = await session_headers(session, owner.id)
        minio = FakeMinioClient()
        storage = ObjectStorageService(minio, "intihal-documents")
        app = create_app()

        async def db():
            async with factory() as request_session:
                yield request_session

        app.dependency_overrides[get_db_session] = db
        app.dependency_overrides[get_object_storage] = lambda: storage
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield client, session, headers, minio, factory, app


async def upload(client, headers, *, source=False):
    return await client.post(
        "/api/v1/admin/sources" if source else "/api/v1/documents",
        headers=headers,
        files={"file": ("test.txt", b"private document text", "text/plain")},
        data={
            "title": "test",
            "license_name": "CC0",
            "rights_holder": "test",
            "license_evidence_reference": "test",
        }
        if source
        else {},
    )


def test_user_upload_limit_is_shared_by_source_uploads_and_survives_app_recreation():
    async def scenario():
        async with upload_api() as (client, session, headers, minio, factory, app):
            for _ in range(10):
                assert (await upload(client, headers)).status_code == 201
            blocked = await upload(client, headers, source=True)
            assert blocked.status_code == 429
            assert blocked.json()["detail"]["code"] == "upload_rate_limited"
            assert 0 < int(blocked.headers["Retry-After"]) <= 300
            assert len(minio.objects) == 10
            counters = list(await session.scalars(select(AuthenticationThrottle)))
            assert sorted(row.attempts for row in counters) == [11, 11]
            assert all(len(row.key) == 64 for row in counters)
            assert "private" not in str([(r.key, r.attempts) for r in counters])
            replacement = create_app()
            replacement.dependency_overrides = app.dependency_overrides.copy()
            async with AsyncClient(
                transport=ASGITransport(app=replacement), base_url="http://test"
            ) as restarted:
                assert (await upload(restarted, headers)).status_code == 429
            assert len(list(await session.scalars(select(Document)))) == 11

    asyncio.run(scenario())


def test_upload_ip_limit_covers_multiple_accounts_and_ignores_forwarded_headers():
    async def scenario():
        async with upload_api() as (client, session, headers, minio, _, _):
            for _ in range(10):
                assert (await upload(client, headers)).status_code == 201
            for index in range(2):
                user = User(id=uuid4(), email=f"user{index}@test.example", display_name="Private")
                session.add(user)
                await session.commit()
                other_headers = await session_headers(session, user.id)
                if index == 0:
                    for _ in range(10):
                        assert (await upload(client, other_headers)).status_code == 201
                else:
                    other_headers["X-Forwarded-For"] = "198.51.100.99"
                    assert (await upload(client, other_headers)).status_code == 429
            assert len(minio.objects) == 20

    asyncio.run(scenario())


def test_upload_window_reopens_after_expiry(monkeypatch):
    current = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return current

    monkeypatch.setattr("intihal_api.core.rate_limit.datetime", Clock)

    async def scenario():
        nonlocal current
        async with upload_api() as (client, _, headers, _, _, _):
            for _ in range(10):
                assert (await upload(client, headers)).status_code == 201
            assert (await upload(client, headers)).status_code == 429
            current += timedelta(seconds=301)
            assert (await upload(client, headers)).status_code == 201

    asyncio.run(scenario())


def test_login_ip_limit_stops_rotating_email_addresses_without_argon_work(monkeypatch):
    calls = 0

    def verify(*args):
        nonlocal calls
        calls += 1
        return False

    monkeypatch.setattr("intihal_api.api.auth.verify_password", verify)

    async def scenario():
        async with auth_api() as (client, _):
            for index in range(50):
                assert (await login(client, email=f"private{index}@example.com")).status_code == 401
            blocked = await client.post(
                "/api/v1/auth/login",
                headers={**CSRF, "X-Forwarded-For": "198.51.100.1"},
                json={"email": "different@example.com", "password": "private password"},
            )
            assert blocked.status_code == 429
            assert calls == 50

    asyncio.run(scenario())


@pytest.mark.parametrize("path", ["/api/v1/documents", "/api/v1/admin/sources"])
def test_large_declared_body_is_rejected_without_reading(path):
    async def scenario():
        app = create_app()
        reads = 0
        messages = []

        async def receive():
            nonlocal reads
            reads += 1
            raise AssertionError("Oversized request body should not be read")

        async def send(message):
            messages.append(message)

        await app(
            {
                "type": "http",
                "http_version": "1.1",
                "method": "POST",
                "scheme": "http",
                "path": path,
                "root_path": "",
                "query_string": b"",
                "headers": [(b"content-length", str(MAX_UPLOAD_REQUEST_BYTES + 1).encode())],
            },
            receive,
            send,
        )
        assert reads == 0
        assert messages[0]["status"] == 413
        assert json.loads(messages[1]["body"])["detail"]["code"] == "request_too_large"

    asyncio.run(scenario())


def test_large_stream_without_length_is_bounded_and_temporary_files_close(monkeypatch):
    import starlette.formparsers

    files = []

    class File(BytesIO):
        def __init__(self, **kwargs):
            super().__init__()
            files.append(self)

    monkeypatch.setattr(starlette.formparsers, "SpooledTemporaryFile", File)
    monkeypatch.setattr("intihal_api.api.upload_limits.MAX_UPLOAD_REQUEST_BYTES", 1024)

    async def scenario():
        app = create_app()
        boundary = b'--upload\r\nContent-Disposition: form-data; name="file"; filename="p.txt"\r\n'
        boundary += b"Content-Type: text/plain\r\n\r\n" + b"private document" * 10

        async def chunks():
            yield boundary
            yield b"private document" * 100
            raise AssertionError("Reading must stop at the body limit")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/documents",
                content=chunks(),
                headers={"Content-Type": "multipart/form-data; boundary=upload"},
            )
        assert response.status_code == 413, response.text
        assert response.json()["detail"]["code"] == "request_too_large"
        assert files and all(file.closed for file in files)

    asyncio.run(scenario())


def test_diagnostics_redact_pii_and_arbitrary_document_text(caplog):
    identifier = str(uuid4())
    secret = "Any arbitrary private paragraph without recognizable PII patterns"
    log_error(
        ValueError(secret),
        code=secret,
        event=secret,
        document_id=identifier,
        email="private@example.com",
        phone="05551234567",
        token="opaque-cookie-token",
        document_text=secret,
        body={"paragraph": secret},
        unknown_key=secret,
        **{"Private Person Name": secret},
    )
    record = json.loads(
        next(r.getMessage() for r in caplog.records if r.name == "intihal_api.core.diagnostics")
    )
    assert record["document_id"] == identifier
    assert record["document_text"] == record["email"] == record["body"] == REDACTED
    assert record["event"] == "redacted_event" and record["code"] == "internal_error"
    assert "Private Person Name" not in caplog.text
    for value in (secret, "private@example.com", "05551234567", "opaque-cookie-token"):
        assert value not in caplog.text


@pytest.mark.parametrize(
    "name",
    [
        "pdfminer.pdfinterp",
        "pypdf",
        "pymupdf",
        "docx",
        "charset_normalizer",
        "urllib3.connectionpool",
        "httpx",
        "sqlalchemy.engine",
        "uvicorn.access",
        "uvicorn.error",
        "intihal_api.extraction",
    ],
)
def test_external_messages_arguments_exceptions_and_extras_are_redacted(caplog, name):
    install_private_logging()
    secret = "private document paragraph and person@example.com"
    try:
        raise ValueError(secret)
    except ValueError:
        logging.getLogger(name).error(
            "Failed with %s", secret, exc_info=True, extra={"document_text": secret}
        )
    record = next(r for r in caplog.records if r.name == name)
    assert secret not in caplog.text
    assert secret not in str(record.__dict__)
    assert record.exc_info is None
