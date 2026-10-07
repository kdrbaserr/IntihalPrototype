import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from auth_helpers import session_headers
from intihal_api.api.dependencies import get_object_storage
from intihal_api.db.models import DocumentStatus
from intihal_api.db.session import get_db_session
from intihal_api.documents.retention import cleanup_expired_documents
from intihal_api.main import create_app
from test_document_cleanup import cleanup_api, completed_document, counts
from test_document_upload import FakeStorage
from test_document_workflow import database


@pytest.mark.parametrize("days", [None, "7", "30", "8", "0", "garbage"])
def test_upload_accepts_only_supported_retention_windows(days):
    async def scenario():
        async with database() as (session, document, factory):
            headers = await session_headers(session, document.owner_id)
            storage = FakeStorage()
            app = create_app()

            async def db():
                async with factory() as request_session:
                    yield request_session

            app.dependency_overrides[get_db_session] = db
            app.dependency_overrides[get_object_storage] = lambda: storage
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                before = datetime.now(UTC)
                response = await client.post(
                    "/api/v1/documents",
                    headers=headers,
                    files={"file": ("test.txt", b"some readable text", "text/plain")},
                    data={} if days is None else {"retention_days": days},
                )
                if days in (None, "7", "30"):
                    assert response.status_code == 201, response.text
                    selected = int(days or 7)
                    data = response.json()
                    assert data["retention_days"] == selected
                    expires = datetime.fromisoformat(data["expires_at"])
                    assert before + timedelta(days=selected) <= expires
                    assert expires <= datetime.now(UTC) + timedelta(days=selected)
                else:
                    assert response.status_code == 422
                    assert storage.uploaded_key is None

    asyncio.run(scenario())


def test_expiration_cleans_derived_data_and_retries_storage_failure():
    async def scenario():
        async with cleanup_api() as (client, session, document, headers, _, storage, _):
            await completed_document(client, session, document, headers)
            now = datetime.now(UTC)
            document.expires_at = now + timedelta(seconds=1)
            await session.commit()
            assert await cleanup_expired_documents(session, storage, now=now) == 0
            assert storage.removed == []
            document.expires_at = now
            await session.commit()
            storage.fail = True
            assert await cleanup_expired_documents(session, storage, now=now) == 0
            await session.refresh(document)
            assert document.status is DocumentStatus.DELETED
            assert document.cleaned_at is None
            assert (await counts(session))[:3] == (1, 1, 1)
            storage.fail = False
            assert await cleanup_expired_documents(session, storage, now=now) == 1
            await session.refresh(document)
            assert document.cleaned_at is not None
            assert (await counts(session))[:3] == (0, 0, 0)
            assert storage.objects == {"sources/keep": b"corpus"}
            assert await cleanup_expired_documents(session, storage, now=now) == 0

    asyncio.run(scenario())


@pytest.mark.parametrize("status", list(DocumentStatus))
def test_expiration_waits_for_active_work(status):
    async def scenario():
        async with cleanup_api() as (_, session, document, _, _, storage, _):
            document.status = status
            document.expires_at = datetime.now(UTC) - timedelta(days=1)
            await session.commit()
            active = status in (
                DocumentStatus.QUEUED,
                DocumentStatus.EXTRACTING,
                DocumentStatus.ANALYZING,
            )
            assert await cleanup_expired_documents(session, storage) == (0 if active else 1)
            assert bool(storage.removed) is not active

    asyncio.run(scenario())
