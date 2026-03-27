"""Agent service."""

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mob.models.agent import Agent, AgentSkill
from mob.models.skill import Skill
from mob.services import ServiceError


async def _resolve_template(session: AsyncSession, agent_template: str) -> tuple[str, str | None, str | None]:
    """Resolve agent_template to (image, cpu_limit, memory_limit).

    If it matches a template name, use the template's image and resource limits.
    If it looks like a Docker image ref (contains : or /), use as-is.
    """
    from mob.models.template import Template

    # Check if it's a registered template name
    result = await session.execute(
        select(Template).where(Template.name == agent_template)
    )
    template = result.scalar_one_or_none()
    if template:
        return template.image, template.resource_cpu_limit, template.resource_memory_limit

    # Looks like a Docker image reference — use as-is
    if ":" in agent_template or "/" in agent_template:
        return agent_template, None, None

    # Neither a registered template nor a Docker ref — use as-is but it may fail at pod creation
    return agent_template, None, None


async def list_agents(
    session: AsyncSession, domain_id: str | None = None
) -> list[Agent]:
    query = select(Agent).order_by(Agent.name)
    if domain_id:
        query = query.where(Agent.domain_id == domain_id)
    result = await session.execute(query)
    return list(result.scalars().all())


async def create_agent(
    session: AsyncSession,
    name: str,
    agent_template: str,
    domain_id: str,
    system_prompt: str | None = None,
    model_endpoint: str | None = None,
    skill_ids: list[str] | None = None,
    env_defaults: dict[str, str] | None = None,
    custom_config: dict[str, str] | None = None,
) -> Agent:
    image, _, _ = await _resolve_template(session, agent_template)
    agent = Agent(
        name=name,
        system_prompt=system_prompt,
        agent_template=image,
        model_endpoint=model_endpoint,
        domain_id=domain_id,
        env_defaults=json.dumps(env_defaults) if env_defaults else None,
        custom_config=json.dumps(custom_config) if custom_config else None,
    )
    session.add(agent)
    await session.flush()

    for skill_id in (skill_ids or []):
        skill = await session.get(Skill, skill_id)
        if not skill:
            raise ServiceError(f"Skill '{skill_id}' not found", 404)
        session.add(AgentSkill(agent_id=agent.id, skill_id=skill_id))

    await session.commit()
    await session.refresh(agent)
    return agent


async def get_agent(session: AsyncSession, agent_id: str) -> Agent:
    agent = await session.get(Agent, agent_id)
    if not agent:
        raise ServiceError("Agent not found", 404)
    return agent


async def update_agent(
    session: AsyncSession,
    agent_id: str,
    name: str | None = None,
    system_prompt: str | None = None,
    agent_template: str | None = None,
    model_endpoint: str | None = None,
    skill_ids: list[str] | None = None,
    env_defaults: dict[str, str] | None = None,
    custom_config: dict[str, str] | None = None,
) -> Agent:
    agent = await session.get(Agent, agent_id)
    if not agent:
        raise ServiceError("Agent not found", 404)

    if name is not None:
        agent.name = name
    if system_prompt is not None:
        agent.system_prompt = system_prompt
    if agent_template is not None:
        image, _, _ = await _resolve_template(session, agent_template)
        agent.agent_template = image
    if model_endpoint is not None:
        agent.model_endpoint = model_endpoint
    if env_defaults is not None:
        agent.env_defaults = json.dumps(env_defaults)
    if custom_config is not None:
        agent.custom_config = json.dumps(custom_config)

    if skill_ids is not None:
        # Remove existing skills
        result = await session.execute(
            select(AgentSkill).where(AgentSkill.agent_id == agent_id)
        )
        for existing in result.scalars().all():
            await session.delete(existing)
        # Add new skills
        for skill_id in skill_ids:
            skill = await session.get(Skill, skill_id)
            if not skill:
                raise ServiceError(f"Skill '{skill_id}' not found", 404)
            session.add(AgentSkill(agent_id=agent_id, skill_id=skill_id))

    await session.commit()
    await session.refresh(agent)
    return agent


async def delete_agent(session: AsyncSession, agent_id: str) -> None:
    agent = await session.get(Agent, agent_id)
    if not agent:
        raise ServiceError("Agent not found", 404)
    await session.delete(agent)
    await session.commit()
