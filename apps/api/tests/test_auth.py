import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from intihal_api.core.config import Settings, get_settings
from intihal_api.core.security import hash_password, token_digest, verify_password
from intihal_api.db.base import Base
from intihal_api.db.models import User, UserRole, UserSession, UserStatus
from intihal_api.db.session import get_db_session
from intihal_api.main import create_app

PASSWORD = "correct horse battery staple"
CSRF = {"X-CSRF-Protection": "1", "Origin": "http://localhost:3000"}


@asynccontextmanager
async def auth_api():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    application = create_app()

    async def override_session():
        async with factory() as session:
            yield session

    application.dependency_overrides[get_db_session] = override_session
    try:
        async with AsyncClient(
            transport=ASGITransport(app=application), base_url="http://test"
        ) as client:
            yield client, factory
    finally:
        await engine.dispose()


async def register(client, **overrides):
    return await client.post(
        "/api/v1/auth/register",
        headers=CSRF,
        json={
            "email": " Person@Example.com ",
            "display_name": "Person",
            "password": PASSWORD,
            **overrides,
        },
    )


async def login(client, **overrides):
    return await client.post(
        "/api/v1/auth/login",
        headers=CSRF,
        json={"email": "person@example.com", "password": PASSWORD, **overrides},
    )


def test_passwords_use_salted_argon2id():
    first, second = hash_password(PASSWORD), hash_password(PASSWORD)
    assert first.startswith("$argon2id$")
    assert first != second and PASSWORD not in first
    assert verify_password(PASSWORD, first)
    assert not verify_password("incorrect", first)
    assert not verify_password(PASSWORD, None)
    assert not verify_password(PASSWORD, "malformed")
    with pytest.raises(ValueError):
        hash_password("short")


def test_register_login_rotation_expiration_and_revocation():
    async def scenario():
        async with auth_api() as (client, factory):
            assert (await client.get("/api/v1/auth/me")).status_code == 401
            created = await register(client)
            assert created.status_code == 201
            assert created.json()["email"] == "person@example.com"
            assert created.json()["role"] == "user"
            assert "password_hash" not in created.text and PASSWORD not in created.text
            assert (await register(client)).status_code == 409
            assert (await login(client, password="wrong")).status_code == 401
            unknown = await login(client, email="absent@example.com")
            assert unknown.status_code == 401
            assert unknown.json()["detail"]["code"] == "invalid_credentials"
            logged_in = await login(client)
            assert logged_in.status_code == 200
            cookie = logged_in.headers["set-cookie"]
            assert "HttpOnly" in cookie and "SameSite=lax" in cookie
            assert "Max-Age=28800" in cookie and "Path=/" in cookie
            assert logged_in.headers["cache-control"] == "no-store"
            name = get_settings().session_cookie_name
            original = client.cookies.get(name)
            async with factory() as session:
                user = await session.scalar(select(User))
                credential = await session.scalar(select(UserSession))
                assert verify_password(PASSWORD, user.password_hash)
                assert credential.token_hash == token_digest(original)
                assert original not in credential.token_hash
            assert (await client.get("/api/v1/auth/me")).status_code == 200
            assert (await login(client)).status_code == 200
            current = client.cookies.get(name)
            assert current != original
            old_headers = {"Cookie": f"{name}={original}"}
            assert (await client.get("/api/v1/auth/me", headers=old_headers)).status_code == 401
            async with factory() as session:
                credential = await session.scalar(select(UserSession))
                credential.expires_at = datetime.now(UTC) - timedelta(seconds=1)
                await session.commit()
            assert (await client.get("/api/v1/auth/me")).status_code == 401
            assert (await login(client)).status_code == 200
            current = client.cookies.get(name)
            assert (await client.post("/api/v1/auth/logout", headers=CSRF)).status_code == 204
            assert client.cookies.get(name) is None
            assert (
                await client.get("/api/v1/auth/me", headers={"Cookie": f"{name}={current}"})
            ).status_code == 401
            assert (await client.post("/api/v1/auth/logout", headers=CSRF)).status_code == 204

    asyncio.run(scenario())


def test_csrf_header_origin_and_forged_identity_are_rejected():
    async def scenario():
        async with auth_api() as (client, _):
            body = {"email": "person@example.com", "password": PASSWORD}
            assert (await client.post("/api/v1/auth/login", json=body)).status_code == 403
            rejected = await client.post(
                "/api/v1/auth/login",
                json=body,
                headers={**CSRF, "Origin": "https://attacker.example"},
            )
            assert rejected.status_code == 403
            assert rejected.json()["detail"]["code"] == "csrf_rejected"
            assert (await register(client)).status_code == 201
            assert (await login(client)).status_code == 200
            assert (await client.post("/api/v1/auth/logout")).status_code == 403
            assert (
                await client.post(
                    "/api/v1/documents", headers={"Origin": "https://attacker.example"}
                )
            ).status_code == 403
            client.cookies.clear()
            assert (
                await client.get(
                    "/api/v1/documents",
                    headers={"X-User-ID": "11111111-1111-1111-1111-111111111111"},
                )
            ).status_code == 401

    asyncio.run(scenario())


def test_roles_are_server_owned_and_changes_apply_to_existing_sessions():
    async def scenario():
        async with auth_api() as (client, factory):
            assert (await register(client, role="admin")).status_code == 422
            assert (await register(client, password="short")).status_code == 422
            assert (await register(client)).status_code == 201
            assert (await login(client)).status_code == 200
            assert (await client.get("/api/v1/admin/sources")).status_code == 403
            async with factory() as session:
                user = await session.scalar(select(User))
                user.role = UserRole.ADMIN
                await session.commit()
            assert (await client.get("/api/v1/admin/sources")).status_code == 200
            async with factory() as session:
                user = await session.scalar(select(User))
                user.role = UserRole.USER
                await session.commit()
            assert (await client.get("/api/v1/admin/sources")).status_code == 403
            async with factory() as session:
                user = await session.scalar(select(User))
                user.status = UserStatus.DISABLED
                await session.commit()
            assert (await client.get("/api/v1/auth/me")).status_code == 403
            disabled = await login(client)
            assert disabled.status_code == 401
            assert disabled.json()["detail"]["code"] == "invalid_credentials"

    asyncio.run(scenario())


def test_login_throttling_is_persisted_and_errors_never_expose_passwords(caplog, monkeypatch):
    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 10, 7, 12, 0, tzinfo=UTC)

    monkeypatch.setattr("intihal_api.core.rate_limit.datetime", FixedDateTime)

    async def scenario():
        async with auth_api() as (client, _):
            for _ in range(10):
                assert (await login(client)).status_code == 401
            blocked = await login(client)
            assert blocked.status_code == 429
            assert blocked.json()["detail"]["code"] == "auth_rate_limited"
            assert int(blocked.headers["retry-after"]) > 0
            invalid = await register(client, password="short-secret")
            assert invalid.status_code == 422 and "short-secret" not in invalid.text
            assert PASSWORD not in caplog.text and "short-secret" not in caplog.text

    asyncio.run(scenario())


def test_production_uses_host_cookie_and_requires_https(monkeypatch):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, environment="production")
    with pytest.raises(ValidationError):
        Settings(_env_file=None, cors_origins=["*"])
    settings = Settings(
        _env_file=None, environment="production", cors_origins=["https://app.example"]
    )
    assert settings.session_cookie_secure and settings.session_cookie_name.startswith("__Host-")
    monkeypatch.setattr("intihal_api.api.auth.get_settings", lambda: settings)
    monkeypatch.setattr("intihal_api.api.dependencies.get_settings", lambda: settings)

    async def scenario():
        async with auth_api() as (client, _):
            headers = {"X-CSRF-Protection": "1", "Origin": "https://app.example"}
            client.base_url = "https://api.example"
            created = await client.post(
                "/api/v1/auth/register",
                headers=headers,
                json={
                    "email": "prod@example.com",
                    "password": PASSWORD,
                    "display_name": "Production",
                },
            )
            assert created.status_code == 201
            response = await client.post(
                "/api/v1/auth/login",
                headers=headers,
                json={"email": "prod@example.com", "password": PASSWORD},
            )
            assert response.status_code == 200
            assert "Secure" in response.headers["set-cookie"]
            assert "Domain=" not in response.headers["set-cookie"]
            assert (await client.get("/api/v1/auth/me")).status_code == 200

    asyncio.run(scenario())
