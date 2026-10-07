"""Atomic database-backed limits survive restarts and work across API replicas."""

from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from intihal_api.core.security import token_digest
from intihal_api.db.models import AuthenticationThrottle


async def check_auth_rate(session: AsyncSession, *, action: str, email: str, client: str) -> None:
    now = datetime.now(UTC)
    window = int(now.timestamp()) // 300
    await session.execute(
        delete(AuthenticationThrottle).where(AuthenticationThrottle.expires_at <= now)
    )
    insert = sqlite_insert if session.bind.dialect.name == "sqlite" else postgres_insert
    counts = []
    limits = [(f"{action}:ip:{client}", 50 if action == "login" else 20)]
    if action == "login":
        limits.append((f"login:email:{email}", 10))
    for identity, maximum in limits:
        statement = insert(AuthenticationThrottle).values(
            key=token_digest(f"{identity}:{window}"),
            attempts=1,
            expires_at=datetime.fromtimestamp((window + 1) * 300, UTC) + timedelta(seconds=1),
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
            detail={
                "code": "auth_rate_limited",
                "message": "Çok fazla deneme. Birkaç dakika sonra yeniden deneyin.",
            },
            headers={"Retry-After": str(300 - int(now.timestamp()) % 300)},
        )
