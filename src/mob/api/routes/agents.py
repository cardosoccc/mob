"""Agent API routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from mob.database import get_session
from mob.schemas import AgentCreate, AgentResponse, AgentUpdate
from mob.services import ServiceError
from mob.services import agents as agent_service

router = APIRouter()


@router.get("", response_model=list[AgentResponse])
async def list_agents(
    domain_id: str | None = None, session: AsyncSession = Depends(get_session)
):
    return await agent_service.list_agents(session, domain_id=domain_id)


@router.post("", response_model=AgentResponse, status_code=201)
async def create_agent(data: AgentCreate, session: AsyncSession = Depends(get_session)):
    try:
        return await agent_service.create_agent(
            session,
            name=data.name,
            agent_template=data.agent_template,
            domain_id=data.domain_id,
            system_prompt=data.system_prompt,
            model_endpoint=data.model_endpoint,
            skill_ids=data.skill_ids,
            env_defaults=data.env_defaults,
            custom_config=data.custom_config,
        )
    except ServiceError as e:
        raise HTTPException(e.status_code, e.message)


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: str, session: AsyncSession = Depends(get_session)):
    try:
        return await agent_service.get_agent(session, agent_id)
    except ServiceError as e:
        raise HTTPException(e.status_code, e.message)


@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: str, data: AgentUpdate, session: AsyncSession = Depends(get_session)
):
    try:
        return await agent_service.update_agent(
            session,
            agent_id,
            name=data.name,
            system_prompt=data.system_prompt,
            agent_template=data.agent_template,
            model_endpoint=data.model_endpoint,
            skill_ids=data.skill_ids,
            env_defaults=data.env_defaults,
            custom_config=data.custom_config,
        )
    except ServiceError as e:
        raise HTTPException(e.status_code, e.message)


@router.delete("/{agent_id}", status_code=204)
async def delete_agent(agent_id: str, session: AsyncSession = Depends(get_session)):
    try:
        await agent_service.delete_agent(session, agent_id)
    except ServiceError as e:
        raise HTTPException(e.status_code, e.message)
