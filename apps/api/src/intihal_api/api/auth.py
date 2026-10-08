"""Cookie authentication; public registration can only create ordinary users."""

import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from starlette.concurrency import run_in_threadpool

from intihal_api.api.dependencies import CurrentUser, DatabaseSession, require_csrf
from intihal_api.core.auth_throttle import check_auth_rate
from intihal_api.core.config import get_settings
from intihal_api.core.security import hash_password, password_hasher, token_digest, verify_password
from intihal_api.db.models import User, UserRole, UserSession, UserStatus

router = APIRouter(prefix="/auth", tags=["Authentication"])


class Credentials(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=128, repr=False)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        value = value.strip().lower()
        if value.count("@") != 1 or not all(value.split("@")) or any(c.isspace() for c in value):
            raise ValueError("Geçerli bir e-posta adresi girin.")
        return value


class Registration(Credentials):
    password: str = Field(min_length=15, max_length=128, repr=False)
    display_name: str = Field(min_length=1, max_length=200)

    @field_validator("display_name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Ad gerekli.")
        return value.strip()


class UserView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: str
    display_name: str
    role: UserRole


def no_cache(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


async def create_session(
    user: User, request: Request, response: Response, session: DatabaseSession
) -> None:
    settings = get_settings()
    now = datetime.now(UTC)
    # Rotate the current browser session at login; also remove expired credentials.
    previous = request.cookies.get(settings.session_cookie_name, "")
    await session.execute(
        delete(UserSession).where(
            (UserSession.expires_at <= now) | (UserSession.token_hash == token_digest(previous))
        )
    )
    token = secrets.token_urlsafe(32)
    session.add(
        UserSession(
            user_id=user.id,
            token_hash=token_digest(token),
            expires_at=now + timedelta(seconds=settings.session_ttl_seconds),
        )
    )
    await session.commit()
    response.set_cookie(
        settings.session_cookie_name,
        token,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
        max_age=settings.session_ttl_seconds,
    )
    no_cache(response)


@router.post(
    "/register", response_model=UserView, status_code=201, dependencies=[Depends(require_csrf)]
)
async def register(
    body: Registration, request: Request, session: DatabaseSession, response: Response
) -> User:
    await check_auth_rate(
        session,
        action="register",
        email=body.email,
        client=request.client.host if request.client else "unknown",
    )
    user = User(
        email=body.email,
        display_name=body.display_name,
        role=UserRole.USER,
        password_hash=await run_in_threadpool(hash_password, body.password),
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError as error:
        await session.rollback()
        raise HTTPException(
            409,
            detail={
                "code": "registration_conflict",
                "message": "Bu adresle kayıt oluşturulamıyor.",
            },
        ) from error
    no_cache(response)
    return user


@router.post("/login", response_model=UserView, dependencies=[Depends(require_csrf)])
async def login(
    body: Credentials, request: Request, response: Response, session: DatabaseSession
) -> User:
    await check_auth_rate(
        session,
        action="login",
        email=body.email,
        client=request.client.host if request.client else "unknown",
    )
    user = await session.scalar(select(User).where(User.email == body.email))
    valid = await run_in_threadpool(
        verify_password, body.password, user.password_hash if user else None
    )
    if (
        not valid
        or user is None
        or user.password_hash is None
        or user.status is not UserStatus.ACTIVE
    ):
        raise HTTPException(
            401, detail={"code": "invalid_credentials", "message": "E-posta veya parola hatalı."}
        )
    if password_hasher.check_needs_rehash(user.password_hash):
        user.password_hash = await run_in_threadpool(hash_password, body.password)
    await create_session(user, request, response, session)
    return user


@router.get("/me", response_model=UserView)
async def me(user: CurrentUser, response: Response) -> User:
    no_cache(response)
    return user


@router.post("/logout", status_code=204, dependencies=[Depends(require_csrf)])
async def logout(request: Request, response: Response, session: DatabaseSession) -> None:
    settings = get_settings()
    token = request.cookies.get(settings.session_cookie_name, "")
    await session.execute(delete(UserSession).where(UserSession.token_hash == token_digest(token)))
    await session.commit()
    response.delete_cookie(
        settings.session_cookie_name,
        path="/",
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
    )
    no_cache(response)
