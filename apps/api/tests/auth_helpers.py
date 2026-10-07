"""Issue real persisted sessions for endpoint ownership/role tests."""

import secrets
from datetime import UTC, datetime, timedelta

from intihal_api.core.config import get_settings
from intihal_api.core.security import token_digest
from intihal_api.db.models import UserSession


async def session_headers(session, user_id):
    token = secrets.token_urlsafe(32)
    session.add(
        UserSession(
            user_id=user_id,
            token_hash=token_digest(token),
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
    )
    await session.commit()
    return {"Cookie": f"{get_settings().session_cookie_name}={token}", "X-CSRF-Protection": "1"}
