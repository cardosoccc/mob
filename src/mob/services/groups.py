"""Group service."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mob.models.group import Group, GroupMember
from mob.models.user import User
from mob.services import ServiceError


async def list_groups(
    session: AsyncSession, organization_id: str | None = None
) -> list[Group]:
    query = select(Group).order_by(Group.name)
    if organization_id:
        query = query.where(Group.organization_id == organization_id)
    result = await session.execute(query)
    return list(result.scalars().all())


async def create_group(
    session: AsyncSession, name: str, organization_id: str
) -> Group:
    group = Group(name=name, organization_id=organization_id)
    session.add(group)
    await session.commit()
    await session.refresh(group)
    return group


async def get_group(session: AsyncSession, group_id: str) -> Group:
    group = await session.get(Group, group_id)
    if not group:
        raise ServiceError("Group not found", 404)
    return group


async def update_group(
    session: AsyncSession, group_id: str, name: str | None = None
) -> Group:
    group = await session.get(Group, group_id)
    if not group:
        raise ServiceError("Group not found", 404)
    if name is not None:
        group.name = name
    await session.commit()
    await session.refresh(group)
    return group


async def delete_group(session: AsyncSession, group_id: str) -> None:
    group = await session.get(Group, group_id)
    if not group:
        raise ServiceError("Group not found", 404)
    await session.delete(group)
    await session.commit()


async def add_member(
    session: AsyncSession, group_id: str, user_id: str
) -> dict:
    group = await session.get(Group, group_id)
    if not group:
        raise ServiceError("Group not found", 404)
    user = await session.get(User, user_id)
    if not user:
        raise ServiceError("User not found", 404)

    existing = await session.execute(
        select(GroupMember).where(
            GroupMember.group_id == group_id, GroupMember.user_id == user_id
        )
    )
    if existing.scalar_one_or_none():
        raise ServiceError("User is already a member of this group", 400)

    member = GroupMember(group_id=group_id, user_id=user_id)
    session.add(member)
    await session.commit()
    return {"status": "added"}


async def remove_member(
    session: AsyncSession, group_id: str, user_id: str
) -> None:
    result = await session.execute(
        select(GroupMember).where(
            GroupMember.group_id == group_id, GroupMember.user_id == user_id
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise ServiceError("Membership not found", 404)
    await session.delete(member)
    await session.commit()
