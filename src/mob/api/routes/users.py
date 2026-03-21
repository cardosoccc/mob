"""User API routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from mob.database import get_session
from mob.schemas import UserCreate, UserResponse, UserUpdate
from mob.services import ServiceError
from mob.services import users as user_service

router = APIRouter()


@router.get("", response_model=list[UserResponse])
async def list_users(session: AsyncSession = Depends(get_session)):
    return await user_service.list_users(session)


@router.post("", response_model=UserResponse, status_code=201)
async def create_user(data: UserCreate, session: AsyncSession = Depends(get_session)):
    try:
        return await user_service.create_user(session, email=data.email, name=data.name)
    except ServiceError as e:
        raise HTTPException(e.status_code, e.message)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: str, session: AsyncSession = Depends(get_session)):
    try:
        return await user_service.get_user(session, user_id)
    except ServiceError as e:
        raise HTTPException(e.status_code, e.message)


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str, data: UserUpdate, session: AsyncSession = Depends(get_session)
):
    try:
        return await user_service.update_user(
            session, user_id, name=data.name, email=data.email
        )
    except ServiceError as e:
        raise HTTPException(e.status_code, e.message)


@router.delete("/{user_id}", status_code=204)
async def delete_user(user_id: str, session: AsyncSession = Depends(get_session)):
    try:
        await user_service.delete_user(session, user_id)
    except ServiceError as e:
        raise HTTPException(e.status_code, e.message)
