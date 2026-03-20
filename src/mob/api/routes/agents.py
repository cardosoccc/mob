"""Agent API routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from mob.database import get_session
from mob.models.agent import Agent, AgentSkill
from mob.models.skill import Skill
from mob.schemas import AgentCreate, AgentResponse, AgentSendMessage, AgentUpdate

router = APIRouter()


@router.get("", response_model=list[AgentResponse])
async def list_agents(
    domain_id: str | None = None, session: AsyncSession = Depends(get_session)
):
    query = select(Agent).order_by(Agent.name)
    if domain_id:
        query = query.where(Agent.domain_id == domain_id)
    result = await session.execute(query)
    return result.scalars().all()


@router.post("", response_model=AgentResponse, status_code=201)
async def create_agent(data: AgentCreate, session: AsyncSession = Depends(get_session)):
    agent = Agent(
        name=data.name,
        system_prompt=data.system_prompt,
        agent_template=data.agent_template,
        model_endpoint=data.model_endpoint,
        domain_id=data.domain_id,
    )
    session.add(agent)
    await session.flush()

    for skill_id in data.skill_ids:
        skill = await session.get(Skill, skill_id)
        if not skill:
            raise HTTPException(404, f"Skill '{skill_id}' not found")
        session.add(AgentSkill(agent_id=agent.id, skill_id=skill_id))

    await session.commit()
    await session.refresh(agent)
    return agent


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: str, session: AsyncSession = Depends(get_session)):
    agent = await session.get(Agent, agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")
    return agent


@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: str, data: AgentUpdate, session: AsyncSession = Depends(get_session)
):
    agent = await session.get(Agent, agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")

    if data.name is not None:
        agent.name = data.name
    if data.system_prompt is not None:
        agent.system_prompt = data.system_prompt
    if data.agent_template is not None:
        agent.agent_template = data.agent_template
    if data.model_endpoint is not None:
        agent.model_endpoint = data.model_endpoint

    if data.skill_ids is not None:
        # Remove existing skills
        result = await session.execute(
            select(AgentSkill).where(AgentSkill.agent_id == agent_id)
        )
        for existing in result.scalars().all():
            await session.delete(existing)
        # Add new skills
        for skill_id in data.skill_ids:
            skill = await session.get(Skill, skill_id)
            if not skill:
                raise HTTPException(404, f"Skill '{skill_id}' not found")
            session.add(AgentSkill(agent_id=agent_id, skill_id=skill_id))

    await session.commit()
    await session.refresh(agent)
    return agent


@router.delete("/{agent_id}", status_code=204)
async def delete_agent(agent_id: str, session: AsyncSession = Depends(get_session)):
    agent = await session.get(Agent, agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")
    await session.delete(agent)
    await session.commit()


@router.post("/{agent_id}/send")
async def send_message(
    agent_id: str, data: AgentSendMessage, session: AsyncSession = Depends(get_session)
):
    """Send a message to a running agent."""
    agent = await session.get(Agent, agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")
    # In a full implementation, this would forward the message to the agent's pod
    return {"status": "sent", "agent_id": agent_id, "run_id": data.run_id}
