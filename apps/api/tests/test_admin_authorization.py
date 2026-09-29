import pytest
from fastapi import HTTPException

from intihal_api.api.dependencies import require_admin_user
from intihal_api.db.models import User, UserRole
from intihal_api.main import create_app


def make_user(role: UserRole) -> User:
    return User(
        email=f"{role.value}@example.com",
        display_name=role.value.title(),
        role=role,
    )


@pytest.mark.anyio
async def test_admin_role_is_authorized() -> None:
    admin = make_user(UserRole.ADMIN)

    assert await require_admin_user(admin) is admin


@pytest.mark.anyio
async def test_regular_user_cannot_use_admin_operations() -> None:
    with pytest.raises(HTTPException) as captured_error:
        await require_admin_user(make_user(UserRole.USER))

    assert captured_error.value.status_code == 403
    assert captured_error.value.detail["code"] == "admin_required"


def test_admin_source_routes_are_registered() -> None:
    paths = create_app().openapi()["paths"]

    assert paths["/api/v1/admin/sources"].keys() >= {"get", "post"}
    assert "post" in paths["/api/v1/admin/sources/{source_id}/disable"]
    assert "post" in paths["/api/v1/admin/sources/{source_id}/reindex"]
