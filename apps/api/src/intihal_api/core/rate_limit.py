"""Shared atomic fixed-window quotas; identities are stored only as keyed digests."""

import hashlib
import hmac
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from intihal_api.core.config import get_settings
from intihal_api.db.models import AuthenticationThrottle

WINDOW_SECONDS = 300


async def enforce_rate_limit(
    session: AsyncSession,
    *,
    identities: list[tuple[str, int]],
    code: str,
) -> None:
    now = datetime.now(UTC)
    window = int(now.timestamp()) // WINDOW_SECONDS
    await session.execute(
        delete(AuthenticationThrottle).where(AuthenticationThrottle.expires_at <= now)
    )
    insert = sqlite_insert if session.bind.dialect.name == "sqlite" else postgres_insert
    # Domain-separated HMAC prevents offline guessing of email/IP from database keys.
    secret = get_settings().redis_password.get_secret_value().encode()
    counts = []
    for identity, maximum in identities:
        key = hmac.new(
            secret, f"intihal-rate-limit:{identity}:{window}".encode(), hashlib.sha256
        ).hexdigest()
        statement = insert(AuthenticationThrottle).values(
            key=key,
            attempts=1,
            expires_at=datetime.fromtimestamp((window + 1) * WINDOW_SECONDS, UTC)
            + timedelta(seconds=1),
        )
        count = await session.scalar(
            statement.on_conflict_do_update(
                index_elements=[AuthenticationThrottle.key],
                set_={"attempts": AuthenticationThrottle.attempts + 1},
            ).returning(AuthenticationThrottle.attempts)
        )
        counts.append((count, maximum))
    await session.commit()
    if any(count > maximum for count, maximum in counts):
        raise HTTPException(
            429,
            detail={"code": code},
            headers={"Retry-After": str(WINDOW_SECONDS - int(now.timestamp()) % WINDOW_SECONDS)},
        )
