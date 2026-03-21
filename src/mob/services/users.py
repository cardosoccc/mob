"""User service."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mob.models.user import User
from mob.services import ServiceError


async def list_users(session: AsyncSession) -> list[User]:
    result = await session.execute(select(User).order_by(User.name))
    return list(result.scalars().all())


async def create_user(session: AsyncSession, email: str, name: str) -> User:
    existing = await session.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        raise ServiceError(f"User with email '{email}' already exists", 400)

    user = User(email=email, name=name)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def get_user(session: AsyncSession, user_id: str) -> User:
    user = await session.get(User, user_id)
    if not user:
        raise ServiceError("User not found", 404)
    return user


async def update_user(
    session: AsyncSession,
    user_id: str,
    name: str | None = None,
    email: str | None = None,
) -> User:
    user = await session.get(User, user_id)
    if not user:
        raise ServiceError("User not found", 404)
    if name is not None:
        user.name = name
    if email is not None:
        user.email = email
    await session.commit()
    await session.refresh(user)
    return user


async def delete_user(session: AsyncSession, user_id: str) -> None:
    user = await session.get(User, user_id)
    if not user:
        raise ServiceError("User not found", 404)
    await session.delete(user)
    await session.commit()
