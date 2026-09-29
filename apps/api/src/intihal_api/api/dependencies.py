from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from intihal_api.db.models import User, UserRole, UserStatus
from intihal_api.db.session import get_db_session
from intihal_api.storage import ObjectStorageService

DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]


async def require_current_user(
    session: DatabaseSession,
    x_user_id: Annotated[str | None, Header(alias="X-User-ID")] = None,
) -> User:
    """Resolve the temporary pre-auth identity and require an active database user."""

    if x_user_id is None:
        raise _authentication_error()
    try:
        user_id = UUID(x_user_id)
    except ValueError as error:
        raise _authentication_error() from error

    user = await session.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise _authentication_error()
    if user.status is UserStatus.DISABLED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "user_disabled", "message": "Kullanıcı hesabı devre dışı."},
        )
    return user


def get_object_storage(request: Request) -> ObjectStorageService:
    return request.app.state.storage


def _authentication_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={
            "code": "authentication_required",
            "message": "Geçerli bir kullanıcı kimliği gerekli.",
        },
        headers={"WWW-Authenticate": "X-User-ID"},
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
