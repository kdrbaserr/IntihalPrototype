"""Cross-resource attacks and session replay must leave business data untouched."""

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import delete, select

from intihal_api.core.config import get_settings
from intihal_api.core.security import token_digest
from intihal_api.db.models import AuditEvent, DocumentStatus, User, UserRole, UserSession
from test_auth import PASSWORD, auth_api, login, register
from test_document_cleanup import cleanup_api, completed_document, counts


def protected_operations(document_id, analysis_id):
    doc = f"/api/v1/documents/{document_id}"
    analysis = f"/api/v1/analyses/{analysis_id}"
    return [
        ("GET", "/api/v1/auth/me", None),
        ("GET", "/api/v1/documents", None),
        ("GET", doc, None),
        ("GET", analysis, None),
        ("GET", analysis + "/matches?limit=1&offset=0", None),
        ("POST", doc + "/analysis", None),
        ("POST", "/api/v1/analyses", {"document_id": str(document_id)}),
        ("POST", analysis + "/retry", None),
        ("DELETE", doc, None),
    ]


@pytest.mark.parametrize(
    "state", ["expired", "revoked", "mutated", "digest", "oversized", "bearer_only", "random"]
)
def test_invalid_sessions_cannot_read_start_retry_or_delete(state, caplog):
    async def scenario():
        async with cleanup_api() as (client, session, document, headers, _, storage, _):
            analysis = await completed_document(client, session, document, headers)
            identifier, analysis_id = document.id, analysis.id
            raw = headers["Cookie"].split("=", 1)[1]
            candidate = raw
            if state == "expired":
                credential = await session.scalar(
                    select(UserSession).where(UserSession.token_hash == token_digest(raw))
                )
                credential.expires_at = datetime.now(UTC) - timedelta(seconds=1)
                await session.commit()
            elif state == "revoked":
                await session.execute(
                    delete(UserSession).where(UserSession.token_hash == token_digest(raw))
                )
                await session.commit()
            elif state == "mutated":
                candidate = ("A" if raw[0] != "A" else "B") + raw[1:]
            elif state == "digest":
                candidate = token_digest(raw)
            elif state == "oversized":
                candidate = "opaque-private-session" * 10
            elif state == "random":
                candidate = "random-private-session-that-was-never-issued"
            attack = {"X-CSRF-Protection": "1", "X-User-ID": str(document.owner_id)}
            if state == "bearer_only":
                attack["Authorization"] = f"Bearer {raw}"
            else:
                attack["Cookie"] = f"{get_settings().session_cookie_name}={candidate}"
            before = await counts(session)
            objects = storage.objects.copy()
            for method, path, payload in protected_operations(identifier, analysis_id):
                response = await client.request(method, path, headers=attack, json=payload)
                assert response.status_code == 401, (state, method, path, response.text)
                assert raw not in response.text and candidate not in response.text
            assert await counts(session) == before
            await session.refresh(document)
            assert document.status is DocumentStatus.COMPLETED
            assert storage.objects == objects and storage.removed == []
            assert list(await session.scalars(select(AuditEvent))) == []
            assert raw not in caplog.text and candidate not in caplog.text

    asyncio.run(scenario())


@pytest.mark.parametrize("role", [UserRole.USER, UserRole.ADMIN])
def test_forged_owner_header_does_not_override_other_users_real_session(role):
    async def scenario():
        async with cleanup_api() as (client, session, document, owner, other, storage, _):
            analysis = await completed_document(client, session, document, owner)
            foreign = await session.scalar(select(User).where(User.email == "other@cleanup.test"))
            foreign.role = role
            await session.commit()
            attack = {**other, "X-User-ID": str(document.owner_id)}
            before = await counts(session)
            for method, path, payload in protected_operations(document.id, analysis.id)[2:]:
                response = await client.request(method, path, headers=attack, json=payload)
                assert response.status_code == 404, (role, method, path, response.text)
                assert document.original_filename not in response.text
            assert (await client.get("/api/v1/documents", headers=attack)).json() == []
            assert (await client.get("/api/v1/auth/me", headers=attack)).json()["id"] == str(
                foreign.id
            )
            assert await counts(session) == before and storage.removed == []

    asyncio.run(scenario())


def test_other_user_cannot_resume_an_owners_pending_permanent_deletion():
    async def scenario():
        async with cleanup_api() as (client, session, document, owner, other, storage, _):
            analysis = await completed_document(client, session, document, owner)
            identifier = document.id
            storage.fail = True
            assert (
                await client.delete(f"/api/v1/documents/{identifier}", headers=owner)
            ).status_code == 503
            storage.fail = False
            before = await counts(session)
            for method, path, payload in protected_operations(identifier, analysis.id)[2:]:
                assert (
                    await client.request(method, path, headers=other, json=payload)
                ).status_code == 404
            assert storage.removed == [] and await counts(session) == before
            assert (
                await client.delete(f"/api/v1/documents/{identifier}", headers=owner)
            ).status_code == 204
            assert (await counts(session))[:3] == (0, 0, 0)

    asyncio.run(scenario())


def test_password_reset_revokes_all_browser_sessions_and_requires_new_password(caplog):
    from intihal_api.db import manage_user

    async def scenario():
        async with auth_api() as (client, factory):
            assert (await register(client)).status_code == 201
            name = get_settings().session_cookie_name
            assert (await login(client)).status_code == 200
            first = client.cookies.get(name)
            client.cookies.clear()
            assert (await login(client)).status_code == 200
            second = client.cookies.get(name)
            assert first != second
            for token in (first, second):
                assert (
                    await client.get("/api/v1/auth/me", headers={"Cookie": f"{name}={token}"})
                ).status_code == 200
            async with factory() as session:
                assert len(list(await session.scalars(select(UserSession)))) == 2
            new_password = "new private password for the reset"
            with (
                patch.object(manage_user, "AsyncSessionFactory", factory),
                patch.object(manage_user, "engine") as engine,
            ):
                engine.dispose = AsyncMock()
                await manage_user.provision("person@example.com", "Private", "user", new_password)
            for token in (first, second):
                for path in ("/api/v1/auth/me", "/api/v1/documents", "/api/v1/admin/sources"):
                    assert (
                        await client.get(path, headers={"Cookie": f"{name}={token}"})
                    ).status_code == 401
            assert (await login(client, password=PASSWORD)).status_code == 401
            assert (await login(client, password=new_password)).status_code == 200
            async with factory() as session:
                assert len(list(await session.scalars(select(UserSession)))) == 1
            assert first not in caplog.text and second not in caplog.text
            assert new_password not in caplog.text

    asyncio.run(scenario())
