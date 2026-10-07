"""Atomic database-backed limits survive restarts and work across API replicas."""

from sqlalchemy.ext.asyncio import AsyncSession

from intihal_api.core.rate_limit import enforce_rate_limit


async def check_auth_rate(session: AsyncSession, *, action: str, email: str, client: str) -> None:
    limits = [(f"{action}:ip:{client}", 50 if action == "login" else 20)]
    if action == "login":
        limits.append((f"login:email:{email}", 10))
    await enforce_rate_limit(session, identities=limits, code="auth_rate_limited")
