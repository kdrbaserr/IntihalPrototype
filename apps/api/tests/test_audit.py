import asyncio
from hashlib import sha256
from io import BytesIO
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError

from auth_helpers import session_headers
from intihal_api.api.dependencies import get_object_storage
from intihal_api.core.audit import AuditAction, record_audit
from intihal_api.corpus import SourceDocumentProcessingService
from intihal_api.db.models import AuditEvent, Document, SourceDocument, User, UserRole
from intihal_api.db.session import get_db_session
from intihal_api.documents.retention import cleanup_expired_documents
from intihal_api.main import create_app
from intihal_api.storage import ObjectStorageService
from intihal_api.uploads import DocumentUploadService
from test_admin_sources_api import FakeMinioClient
from test_document_cleanup import cleanup_api
from test_document_upload import FakeStorage
from test_document_workflow import CONTENT, database, seed_source


async def events(session):
    return list(await session.scalars(select(AuditEvent).order_by(AuditEvent.created_at)))


def assert_no_sensitive_data(records, *secrets):
    columns = inspect(AuditEvent).columns.keys()
    serialized = str([{key: getattr(row, key) for key in columns} for row in records])
    for secret in secrets:
        assert secret not in serialized


def test_audit_has_only_fixed_fields_and_rejects_arbitrary_payloads():
    assert set(inspect(AuditEvent).columns.keys()) == {
        "id",
        "created_at",
        "actor_id",
        "actor_kind",
        "action",
        "resource_type",
        "resource_id",
        "outcome",
    }
    with pytest.raises(ValueError):
        record_audit(None, action="secret-token", actor_id=uuid4(), resource_id=uuid4())
    with pytest.raises(TypeError):
        record_audit(None, action=AuditAction.DOCUMENT_UPLOAD, content="private contents")
    with pytest.raises(ValueError):
        record_audit(
            None, action=AuditAction.DOCUMENT_UPLOAD, actor_id="secret-token", resource_id=uuid4()
        )


def test_upload_audit_is_atomic_and_does_not_contain_file_or_credentials():
    async def scenario():
        async with database() as (session, document, _):
            storage = FakeStorage()
            uploaded = await DocumentUploadService(storage).create_document(
                owner_id=document.owner_id,
                filename="private-secret-name.txt",
                content_type="text/plain",
                stream=BytesIO(b"private document contents"),
                session=session,
            )
            records = await events(session)
            assert len(records) == 1
            event = records[0]
            assert (event.action, event.outcome, event.actor_kind) == (
                "document.upload",
                "succeeded",
                "user",
            )
            assert event.actor_id == uploaded.owner_id and event.resource_id == uploaded.id
            assert event.created_at is not None
            assert_no_sensitive_data(
                records,
                "private-secret-name",
                "private document contents",
                uploaded.sha256,
                uploaded.storage_key,
            )

    asyncio.run(scenario())


def test_audit_write_failure_rolls_back_upload_and_compensates_storage():
    async def scenario():
        async with database() as (session, document, _):
            owner_id = document.owner_id
            storage = FakeStorage()

            def fail_audit(db, **kwargs):
                db.add(
                    AuditEvent(
                        actor_kind="user",
                        actor_id=owner_id,
                        action="INVALID",
                        resource_type="document",
                        resource_id=uuid4(),
                        outcome="succeeded",
                    )
                )

            with patch("intihal_api.uploads.service.record_audit", side_effect=fail_audit):
                with pytest.raises(IntegrityError):
                    await DocumentUploadService(storage).create_document(
                        owner_id=owner_id,
                        filename="test.txt",
                        content_type="text/plain",
                        stream=BytesIO(b"private text"),
                        session=session,
                    )
            assert storage.removed_keys == [storage.uploaded_key]
            assert await events(session) == []
            assert len(list(await session.scalars(select(Document)))) == 1

    asyncio.run(scenario())


def test_manual_delete_records_intent_and_completion_once_even_after_retry():
    async def scenario():
        async with cleanup_api() as (client, session, document, headers, other, storage, _):
            url = f"/api/v1/documents/{document.id}"
            owner_id, identifier = document.owner_id, document.id
            assert (await client.delete(url, headers=other)).status_code == 404
            assert await events(session) == []
            storage.fail = True
            assert (await client.delete(url, headers=headers)).status_code == 503
            records = await events(session)
            assert [event.outcome for event in records] == ["started"]
            storage.fail = False
            assert (await client.delete(url, headers=headers)).status_code == 204
            assert (await client.delete(url, headers=headers)).status_code == 204
            records = await events(session)
            assert sorted(event.outcome for event in records) == ["started", "succeeded"]
            assert all(
                event.actor_id == owner_id
                and event.resource_id == identifier
                and event.action == "document.delete"
                for event in records
            )
            assert_no_sensitive_data(
                records,
                headers["Cookie"],
                document.sha256,
                document.original_filename,
                document.storage_key,
            )

    asyncio.run(scenario())


def test_system_cleanup_can_complete_a_users_pending_deletion():
    async def scenario():
        async with cleanup_api() as (client, session, document, headers, _, storage, _):
            identifier = document.id
            owner_id = document.owner_id
            storage.fail = True
            assert (
                await client.delete(f"/api/v1/documents/{identifier}", headers=headers)
            ).status_code == 503
            storage.fail = False
            assert await cleanup_expired_documents(session, storage) == 1
            records = await events(session)
            started = next(event for event in records if event.outcome == "started")
            succeeded = next(event for event in records if event.outcome == "succeeded")
            assert started.actor_id == owner_id and started.actor_kind == "user"
            assert succeeded.actor_id is None and succeeded.actor_kind == "system"

    asyncio.run(scenario())


def test_admin_source_operations_record_ids_without_upload_or_session_data():
    async def scenario():
        async with database() as (session, document, factory):
            admin = await session.get(User, document.owner_id)
            admin.role = UserRole.ADMIN
            await session.commit()
            headers = await session_headers(session, admin.id)
            storage = ObjectStorageService(FakeMinioClient(), "intihal-documents")
            app = create_app()

            async def db():
                async with factory() as request_session:
                    yield request_session

            app.dependency_overrides[get_db_session] = db
            app.dependency_overrides[get_object_storage] = lambda: storage
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/v1/admin/sources",
                    headers=headers,
                    files={
                        "file": (
                            "private-source-name.txt",
                            b"private corpus contents",
                            "text/plain",
                        )
                    },
                    data={
                        "title": "private source title",
                        "license_name": "CC0",
                        "rights_holder": "private holder",
                        "license_evidence_reference": "private license evidence",
                    },
                )
                assert response.status_code == 201, response.text
                source_id = response.json()["id"]
                assert (
                    await client.get("/api/v1/admin/sources", headers=headers)
                ).status_code == 200
                assert (
                    await client.post(f"/api/v1/admin/sources/{source_id}/reindex", headers=headers)
                ).status_code == 200
                assert (
                    await client.post(f"/api/v1/admin/sources/{source_id}/disable", headers=headers)
                ).status_code == 200
            records = await events(session)
            assert sorted(event.action for event in records) == sorted(
                [
                    "admin.source.create",
                    "admin.source.create",
                    "admin.source.list",
                    "admin.source.disable",
                    "admin.source.reindex",
                    "admin.source.reindex",
                ]
            )
            assert all(event.actor_id == admin.id for event in records)
            assert_no_sensitive_data(
                records, "private", headers["Cookie"], response.json()["sha256"]
            )

    asyncio.run(scenario())


def test_operator_user_provision_does_not_record_password_or_hash():
    from intihal_api.db import manage_user

    async def scenario():
        async with database() as (session, document, factory):
            owner_id = document.owner_id
            with (
                patch.object(manage_user, "AsyncSessionFactory", factory),
                patch.object(manage_user, "engine") as engine,
            ):
                engine.dispose = AsyncMock()
                await manage_user.provision(
                    "owner@test.example", "Private name", "admin", "private-secret-password-123"
                )
            records = await events(session)
            assert len(records) == 1
            event = records[0]
            assert event.action == "admin.user.provision"
            assert event.actor_kind == "operator" and event.actor_id is None
            assert event.resource_id == owner_id
            await session.refresh(await session.get(User, owner_id))
            user = await session.get(User, owner_id)
            assert user.role is UserRole.ADMIN
            assert_no_sensitive_data(
                records,
                "private-secret-password-123",
                user.password_hash,
                user.email,
                user.display_name,
            )

    asyncio.run(scenario())


@pytest.mark.parametrize("failure", ["extraction", "commit"])
def test_failed_admin_index_does_not_leave_a_success_event(failure):
    async def scenario():
        async with database() as (session, document, _):
            actor_id = document.owner_id
            identifier = await seed_source(session)
            source = await session.get(SourceDocument, identifier)
            source.sha256 = sha256(CONTENT.encode()).hexdigest()
            await session.commit()
            real_commit = session.commit
            commits = 0

            async def commit():
                nonlocal commits
                commits += 1
                if commits == 2:
                    raise RuntimeError("private SQL details")
                await real_commit()

            if failure == "commit":
                session.commit = commit
                with pytest.raises(RuntimeError):
                    await SourceDocumentProcessingService().process(
                        source_document=source,
                        stream=BytesIO(CONTENT.encode()),
                        session=session,
                        actor_id=actor_id,
                    )
            else:
                with patch(
                    "intihal_api.corpus.service.extract_and_chunk_document",
                    side_effect=RuntimeError("private content and token"),
                ):
                    with pytest.raises(RuntimeError):
                        await SourceDocumentProcessingService().process(
                            source_document=source,
                            stream=BytesIO(CONTENT.encode()),
                            session=session,
                            actor_id=actor_id,
                        )
            records = await events(session)
            assert sorted(event.outcome for event in records) == ["failed", "started"]
            assert all(event.action == "admin.source.reindex" for event in records)
            assert_no_sensitive_data(records, "private", CONTENT)

    asyncio.run(scenario())


def test_failed_cleanup_commit_preserves_only_started_audit_until_retry():
    async def scenario():
        async with cleanup_api() as (client, session, document, headers, _, _, fault):
            url = f"/api/v1/documents/{document.id}"
            fault["fail_commit"] = True
            assert (await client.delete(url, headers=headers)).status_code == 500
            assert [event.outcome for event in await events(session)] == ["started"]
            fault["fail_commit"] = False
            assert (await client.delete(url, headers=headers)).status_code == 204
            assert sorted(event.outcome for event in await events(session)) == [
                "started",
                "succeeded",
            ]

    asyncio.run(scenario())


@pytest.mark.parametrize("existing", [False, True])
def test_local_admin_seed_also_records_privilege_provision(existing):
    from intihal_api.core.config import Settings
    from intihal_api.db import seed

    async def scenario():
        async with database() as (session, document, factory):
            identifier = document.owner_id if existing else uuid4()
            settings = Settings(
                _env_file=None, demo_user_id=identifier, demo_password="private-demo-password-123"
            )
            with (
                patch.object(seed, "AsyncSessionFactory", factory),
                patch.object(seed, "get_settings", return_value=settings),
            ):
                await seed.seed_local_demo_user()
            records = await events(session)
            assert len(records) == 1
            assert records[0].action == "admin.user.provision"
            assert records[0].actor_kind == "operator"
            assert records[0].resource_id == identifier
            assert_no_sensitive_data(records, "private-demo-password-123")

    asyncio.run(scenario())
