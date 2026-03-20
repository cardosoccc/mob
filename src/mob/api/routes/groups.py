"""Group API routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mob.database import get_session
from mob.models.group import Group, GroupMember
from mob.models.user import User
from mob.schemas import GroupCreate, GroupMemberAdd, GroupResponse, GroupUpdate

router = APIRouter()


@router.get("", response_model=list[GroupResponse])
async def list_groups(
    organization_id: str | None = None, session: AsyncSession = Depends(get_session)
):
    query = select(Group).order_by(Group.name)
    if organization_id:
        query = query.where(Group.organization_id == organization_id)
    result = await session.execute(query)
    return result.scalars().all()


@router.post("", response_model=GroupResponse, status_code=201)
async def create_group(data: GroupCreate, session: AsyncSession = Depends(get_session)):
    group = Group(name=data.name, organization_id=data.organization_id)
    session.add(group)
    await session.commit()
    await session.refresh(group)
    return group


@router.get("/{group_id}", response_model=GroupResponse)
async def get_group(group_id: str, session: AsyncSession = Depends(get_session)):
    group = await session.get(Group, group_id)
    if not group:
        raise HTTPException(404, "Group not found")
    return group


@router.put("/{group_id}", response_model=GroupResponse)
async def update_group(
    group_id: str, data: GroupUpdate, session: AsyncSession = Depends(get_session)
):
    group = await session.get(Group, group_id)
    if not group:
        raise HTTPException(404, "Group not found")
    if data.name is not None:
        group.name = data.name
    await session.commit()
    await session.refresh(group)
    return group


@router.delete("/{group_id}", status_code=204)
async def delete_group(group_id: str, session: AsyncSession = Depends(get_session)):
    group = await session.get(Group, group_id)
    if not group:
        raise HTTPException(404, "Group not found")
    await session.delete(group)
    await session.commit()


@router.post("/{group_id}/members", status_code=201)
async def add_member(
    group_id: str, data: GroupMemberAdd, session: AsyncSession = Depends(get_session)
):
    group = await session.get(Group, group_id)
    if not group:
        raise HTTPException(404, "Group not found")
    user = await session.get(User, data.user_id)
    if not user:
        raise HTTPException(404, "User not found")

    existing = await session.execute(
        select(GroupMember).where(
            GroupMember.group_id == group_id, GroupMember.user_id == data.user_id
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(400, "User is already a member of this group")

    member = GroupMember(group_id=group_id, user_id=data.user_id)
    session.add(member)
    await session.commit()
    return {"status": "added"}


@router.delete("/{group_id}/members/{user_id}", status_code=204)
async def remove_member(
    group_id: str, user_id: str, session: AsyncSession = Depends(get_session)
):
    result = await session.execute(
        select(GroupMember).where(
            GroupMember.group_id == group_id, GroupMember.user_id == user_id
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(404, "Membership not found")
    await session.delete(member)
    await session.commit()
