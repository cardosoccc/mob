"""Group API routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from mob.database import get_session
from mob.schemas import GroupCreate, GroupMemberAdd, GroupResponse, GroupUpdate
from mob.services import ServiceError
from mob.services import groups as group_service

router = APIRouter()


@router.get("", response_model=list[GroupResponse])
async def list_groups(
    organization_id: str | None = None, session: AsyncSession = Depends(get_session)
):
    return await group_service.list_groups(session, organization_id=organization_id)


@router.post("", response_model=GroupResponse, status_code=201)
async def create_group(data: GroupCreate, session: AsyncSession = Depends(get_session)):
    try:
        return await group_service.create_group(
            session, name=data.name, organization_id=data.organization_id
        )
    except ServiceError as e:
        raise HTTPException(e.status_code, e.message)


@router.get("/{group_id}", response_model=GroupResponse)
async def get_group(group_id: str, session: AsyncSession = Depends(get_session)):
    try:
        return await group_service.get_group(session, group_id)
    except ServiceError as e:
        raise HTTPException(e.status_code, e.message)


@router.put("/{group_id}", response_model=GroupResponse)
async def update_group(
    group_id: str, data: GroupUpdate, session: AsyncSession = Depends(get_session)
):
    try:
        return await group_service.update_group(session, group_id, name=data.name)
    except ServiceError as e:
        raise HTTPException(e.status_code, e.message)


@router.delete("/{group_id}", status_code=204)
async def delete_group(group_id: str, session: AsyncSession = Depends(get_session)):
    try:
        await group_service.delete_group(session, group_id)
    except ServiceError as e:
        raise HTTPException(e.status_code, e.message)


@router.post("/{group_id}/members", status_code=201)
async def add_member(
    group_id: str, data: GroupMemberAdd, session: AsyncSession = Depends(get_session)
):
    try:
        return await group_service.add_member(session, group_id, user_id=data.user_id)
    except ServiceError as e:
        raise HTTPException(e.status_code, e.message)


@router.delete("/{group_id}/members/{user_id}", status_code=204)
async def remove_member(
    group_id: str, user_id: str, session: AsyncSession = Depends(get_session)
):
    try:
        await group_service.remove_member(session, group_id, user_id)
    except ServiceError as e:
        raise HTTPException(e.status_code, e.message)
