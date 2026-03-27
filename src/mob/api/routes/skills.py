"""Skill API routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from mob.database import get_session
from mob.schemas import SkillCreate, SkillResponse, SkillUpdate
from mob.services import ServiceError
from mob.services import skills as skill_service

router = APIRouter()


@router.get("", response_model=list[SkillResponse])
async def list_skills(session: AsyncSession = Depends(get_session)):
    return await skill_service.list_skills(session)


@router.post("", response_model=SkillResponse, status_code=201)
async def create_skill(data: SkillCreate, session: AsyncSession = Depends(get_session)):
    try:
        return await skill_service.create_skill(
            session,
            name=data.name,
            description=data.description,
            skill_md=data.skill_md,
            license=data.license,
            compatibility=data.compatibility,
            metadata_json=data.metadata_json,
            allowed_tools=data.allowed_tools,
        )
    except ServiceError as e:
        raise HTTPException(e.status_code, e.message)


@router.get("/{skill_id}", response_model=SkillResponse)
async def get_skill(skill_id: str, session: AsyncSession = Depends(get_session)):
    try:
        return await skill_service.get_skill(session, skill_id)
    except ServiceError as e:
        raise HTTPException(e.status_code, e.message)


@router.put("/{skill_id}", response_model=SkillResponse)
async def update_skill(
    skill_id: str, data: SkillUpdate, session: AsyncSession = Depends(get_session)
):
    try:
        return await skill_service.update_skill(
            session,
            skill_id,
            name=data.name,
            description=data.description,
            skill_md=data.skill_md,
            license=data.license,
            compatibility=data.compatibility,
            metadata_json=data.metadata_json,
            allowed_tools=data.allowed_tools,
        )
    except ServiceError as e:
        raise HTTPException(e.status_code, e.message)


@router.delete("/{skill_id}", status_code=204)
async def delete_skill(skill_id: str, session: AsyncSession = Depends(get_session)):
    try:
        await skill_service.delete_skill(session, skill_id)
    except ServiceError as e:
        raise HTTPException(e.status_code, e.message)
