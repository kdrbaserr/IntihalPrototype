"""Provision a local demo administrator with an explicitly supplied password."""

import asyncio

from sqlalchemy import delete

from intihal_api.core.config import get_settings
from intihal_api.core.security import hash_password
from intihal_api.db.models import User, UserRole, UserSession
from intihal_api.db.session import AsyncSessionFactory, engine


async def seed_local_demo_user() -> None:
    settings = get_settings()
    if settings.environment != "local":
        raise RuntimeError("Demo user seeding is allowed only in the local environment.")

    if settings.demo_password is None:
        raise RuntimeError("Set INTIHAL_DEMO_PASSWORD (15–128 characters) before seeding.")
    encoded = hash_password(settings.demo_password.get_secret_value())

    async with AsyncSessionFactory() as session:
        user = await session.get(User, settings.demo_user_id)
        if user is None:
            session.add(
                User(
                    id=settings.demo_user_id,
                    email="demo@intihal.local",
                    display_name="Yerel Demo Kullanıcısı",
                    role=UserRole.ADMIN,
                    password_hash=encoded,
                )
            )
            await session.commit()
            print(f"Created local demo user: {settings.demo_user_id}")
        else:
            user.role = UserRole.ADMIN
            user.password_hash = encoded
            await session.execute(delete(UserSession).where(UserSession.user_id == user.id))
            await session.commit()
            print(f"Local demo user already exists: {settings.demo_user_id}")


async def main() -> None:
    try:
        await seed_local_demo_user()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
