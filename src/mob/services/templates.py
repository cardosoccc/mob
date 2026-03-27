"""Template service."""

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mob.models.template import Template
from mob.services import ServiceError


async def list_templates(session: AsyncSession) -> list[Template]:
    result = await session.execute(select(Template).order_by(Template.name))
    return list(result.scalars().all())


async def create_template(
    session: AsyncSession,
    name: str,
    image: str,
    runtime: str,
    description: str | None = None,
    capabilities: list[str] | None = None,
    resource_cpu_limit: str | None = None,
    resource_memory_limit: str | None = None,
) -> Template:
    existing = await session.execute(select(Template).where(Template.name == name))
    if existing.scalar_one_or_none():
        raise ServiceError(f"Template with name '{name}' already exists", 400)

    template = Template(
        name=name,
        image=image,
        description=description,
        runtime=runtime,
        capabilities=json.dumps(capabilities) if capabilities else None,
        resource_cpu_limit=resource_cpu_limit,
        resource_memory_limit=resource_memory_limit,
    )
    session.add(template)
    await session.commit()
    await session.refresh(template)
    return template


async def get_template(session: AsyncSession, template_id: str) -> Template:
    template = await session.get(Template, template_id)
    if not template:
        raise ServiceError("Template not found", 404)
    return template


async def update_template(
    session: AsyncSession,
    template_id: str,
    name: str | None = None,
    image: str | None = None,
    description: str | None = None,
    runtime: str | None = None,
    capabilities: list[str] | None = None,
    resource_cpu_limit: str | None = None,
    resource_memory_limit: str | None = None,
) -> Template:
    template = await session.get(Template, template_id)
    if not template:
        raise ServiceError("Template not found", 404)
    if name is not None:
        template.name = name
    if image is not None:
        template.image = image
    if description is not None:
        template.description = description
    if runtime is not None:
        template.runtime = runtime
    if capabilities is not None:
        template.capabilities = json.dumps(capabilities)
    if resource_cpu_limit is not None:
        template.resource_cpu_limit = resource_cpu_limit
    if resource_memory_limit is not None:
        template.resource_memory_limit = resource_memory_limit
    await session.commit()
    await session.refresh(template)
    return template


async def delete_template(session: AsyncSession, template_id: str) -> None:
    template = await session.get(Template, template_id)
    if not template:
        raise ServiceError("Template not found", 404)
    await session.delete(template)
    await session.commit()
