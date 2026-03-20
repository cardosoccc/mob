"""Skill API routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mob.database import get_session
from mob.models.skill import Skill
from mob.schemas import SkillCreate, SkillResponse, SkillUpdate

router = APIRouter()


@router.get("", response_model=list[SkillResponse])
async def list_skills(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Skill).order_by(Skill.name))
    return result.scalars().all()


@router.post("", response_model=SkillResponse, status_code=201)
async def create_skill(data: SkillCreate, session: AsyncSession = Depends(get_session)):
    existing = await session.execute(select(Skill).where(Skill.name == data.name))
    if existing.scalar_one_or_none():
        raise HTTPException(400, f"Skill with name '{data.name}' already exists")

    skill = Skill(
        name=data.name,
        description=data.description,
        skills_md=data.skills_md,
        references_path=data.references_path,
    )
    session.add(skill)
    await session.commit()
    await session.refresh(skill)
    return skill


@router.get("/{skill_id}", response_model=SkillResponse)
async def get_skill(skill_id: str, session: AsyncSession = Depends(get_session)):
    skill = await session.get(Skill, skill_id)
    if not skill:
        raise HTTPException(404, "Skill not found")
    return skill


@router.put("/{skill_id}", response_model=SkillResponse)
async def update_skill(
    skill_id: str, data: SkillUpdate, session: AsyncSession = Depends(get_session)
):
    skill = await session.get(Skill, skill_id)
    if not skill:
        raise HTTPException(404, "Skill not found")
    if data.name is not None:
        skill.name = data.name
    if data.description is not None:
        skill.description = data.description
    if data.skills_md is not None:
        skill.skills_md = data.skills_md
    if data.references_path is not None:
        skill.references_path = data.references_path
    await session.commit()
    await session.refresh(skill)
    return skill


@router.delete("/{skill_id}", status_code=204)
async def delete_skill(skill_id: str, session: AsyncSession = Depends(get_session)):
    skill = await session.get(Skill, skill_id)
    if not skill:
        raise HTTPException(404, "Skill not found")
    await session.delete(skill)
    await session.commit()
