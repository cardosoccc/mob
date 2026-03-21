"""Skill service."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mob.models.skill import Skill
from mob.services import ServiceError


async def list_skills(session: AsyncSession) -> list[Skill]:
    result = await session.execute(select(Skill).order_by(Skill.name))
    return list(result.scalars().all())


async def create_skill(
    session: AsyncSession,
    name: str,
    description: str | None = None,
    skills_md: str | None = None,
    references_path: str | None = None,
) -> Skill:
    existing = await session.execute(select(Skill).where(Skill.name == name))
    if existing.scalar_one_or_none():
        raise ServiceError(f"Skill with name '{name}' already exists", 400)

    skill = Skill(
        name=name,
        description=description,
        skills_md=skills_md,
        references_path=references_path,
    )
    session.add(skill)
    await session.commit()
    await session.refresh(skill)
    return skill


async def get_skill(session: AsyncSession, skill_id: str) -> Skill:
    skill = await session.get(Skill, skill_id)
    if not skill:
        raise ServiceError("Skill not found", 404)
    return skill


async def update_skill(
    session: AsyncSession,
    skill_id: str,
    name: str | None = None,
    description: str | None = None,
    skills_md: str | None = None,
    references_path: str | None = None,
) -> Skill:
    skill = await session.get(Skill, skill_id)
    if not skill:
        raise ServiceError("Skill not found", 404)
    if name is not None:
        skill.name = name
    if description is not None:
        skill.description = description
    if skills_md is not None:
        skill.skills_md = skills_md
    if references_path is not None:
        skill.references_path = references_path
    await session.commit()
    await session.refresh(skill)
    return skill


async def delete_skill(session: AsyncSession, skill_id: str) -> None:
    skill = await session.get(Skill, skill_id)
    if not skill:
        raise ServiceError("Skill not found", 404)
    await session.delete(skill)
    await session.commit()
