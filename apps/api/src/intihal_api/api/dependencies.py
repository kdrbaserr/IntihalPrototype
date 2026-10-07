from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from intihal_api.core.config import get_settings
from intihal_api.core.security import token_digest
from intihal_api.db.models import User, UserRole, UserSession, UserStatus
from intihal_api.db.session import get_db_session
from intihal_api.storage import ObjectStorageService

DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]


def require_csrf(request: Request) -> None:
    """A custom header forces browser preflight; reject untrusted origins as well."""
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    origin = request.headers.get("origin")
    if request.headers.get("X-CSRF-Protection") != "1" or (
        origin is not None and origin not in get_settings().cors_origins
    ):
        raise HTTPException(
            403, detail={"code": "csrf_rejected", "message": "İstek kaynağı doğrulanamadı."}
        )


async def require_current_user(request: Request, session: DatabaseSession) -> User:
    token = request.cookies.get(get_settings().session_cookie_name)
    if not token or len(token) > 128:
        raise _authentication_error()
    user = await session.scalar(
        select(User)
        .join(UserSession, UserSession.user_id == User.id)
        .where(
            UserSession.token_hash == token_digest(token),
            UserSession.expires_at > datetime.now(UTC),
        )
    )
    if user is None:
        raise _authentication_error()
    if user.status is UserStatus.DISABLED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "user_disabled", "message": "Kullanıcı hesabı devre dışı."},
        )
    require_csrf(request)
    return user


def get_object_storage(request: Request) -> ObjectStorageService:
    return request.app.state.storage


def _authentication_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={
            "code": "authentication_required",
            "message": "Giriş yapmanız gerekli.",
        },
    )


CurrentUser = Annotated[User, Depends(require_current_user)]


async def require_admin_user(current_user: CurrentUser) -> User:
    """Require the authenticated active user to have the administrator role."""

    if current_user.role is not UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "admin_required",
                "message": "Bu işlem için yönetici yetkisi gerekli.",
            },
        )
    return current_user


AdminUser = Annotated[User, Depends(require_admin_user)]
ObjectStorage = Annotated[ObjectStorageService, Depends(get_object_storage)]
