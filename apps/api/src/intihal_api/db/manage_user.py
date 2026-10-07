"""Trusted operator CLI: provision a password/role and revoke previous sessions."""

import argparse
import asyncio
from getpass import getpass

from sqlalchemy import delete, select

from intihal_api.api.auth import Registration
from intihal_api.core.security import hash_password
from intihal_api.db.models import User, UserRole, UserSession
from intihal_api.db.session import AsyncSessionFactory, engine


async def provision(email: str, name: str, role: str, password: str) -> None:
    body = Registration(email=email, display_name=name, password=password)
    encoded = hash_password(body.password)
    try:
        async with AsyncSessionFactory() as session:
            user = await session.scalar(select(User).where(User.email == body.email))
            if user is None:
                user = User(email=body.email, display_name=body.display_name)
                session.add(user)
            else:
                await session.execute(delete(UserSession).where(UserSession.user_id == user.id))
            user.password_hash = encoded
            user.display_name = body.display_name
            user.role = UserRole(role)
            await session.commit()
            print(f"Provisioned {body.email} with role {role}; previous sessions revoked.")
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("email")
    parser.add_argument("--name", required=True)
    parser.add_argument("--role", choices=["user", "admin"], default="user")
    arguments = parser.parse_args()
    password = getpass("Password (15–128 characters): ")
    if password != getpass("Confirm password: "):
        parser.error("Passwords do not match")
    asyncio.run(provision(arguments.email, arguments.name, arguments.role, password))


if __name__ == "__main__":
    main()
