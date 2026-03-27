"""Skill service."""

import json

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
    description: str,
    skill_md: str | None = None,
    license: str | None = None,
    compatibility: str | None = None,
    metadata_json: dict[str, str] | None = None,
    allowed_tools: str | None = None,
) -> Skill:
    existing = await session.execute(select(Skill).where(Skill.name == name))
    if existing.scalar_one_or_none():
        raise ServiceError(f"Skill with name '{name}' already exists", 400)

    skill = Skill(
        name=name,
        description=description,
        skill_md=skill_md,
        license=license,
        compatibility=compatibility,
        metadata_json=json.dumps(metadata_json) if metadata_json else None,
        allowed_tools=allowed_tools,
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
    skill_md: str | None = None,
    license: str | None = None,
    compatibility: str | None = None,
    metadata_json: dict[str, str] | None = None,
    allowed_tools: str | None = None,
) -> Skill:
    skill = await session.get(Skill, skill_id)
    if not skill:
        raise ServiceError("Skill not found", 404)
    if name is not None:
        skill.name = name
    if description is not None:
        skill.description = description
    if skill_md is not None:
        skill.skill_md = skill_md
    if license is not None:
        skill.license = license
    if compatibility is not None:
        skill.compatibility = compatibility
    if metadata_json is not None:
        skill.metadata_json = json.dumps(metadata_json)
    if allowed_tools is not None:
        skill.allowed_tools = allowed_tools
    await session.commit()
    await session.refresh(skill)
    return skill


async def delete_skill(session: AsyncSession, skill_id: str) -> None:
    skill = await session.get(Skill, skill_id)
    if not skill:
        raise ServiceError("Skill not found", 404)
    await session.delete(skill)
    await session.commit()
