"""AgentRun API routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mob.database import get_session
from mob.models.agent import Agent
from mob.models.agent_run import AgentRun, AgentRunState
from mob.schemas import AgentRunCreate, AgentRunResponse

router = APIRouter()


@router.get("", response_model=list[AgentRunResponse])
async def list_agent_runs(
    agent_id: str | None = None, session: AsyncSession = Depends(get_session)
):
    query = select(AgentRun).order_by(AgentRun.created_at.desc())
    if agent_id:
        query = query.where(AgentRun.agent_id == agent_id)
    result = await session.execute(query)
    return result.scalars().all()


@router.post("", response_model=AgentRunResponse, status_code=201)
async def create_agent_run(
    data: AgentRunCreate, session: AsyncSession = Depends(get_session)
):
    agent = await session.get(Agent, data.agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")

    run = AgentRun(
        agent_id=data.agent_id,
        state=AgentRunState.PENDING,
        task_id=data.task_id,
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return run


@router.get("/{run_id}", response_model=AgentRunResponse)
async def get_agent_run(run_id: str, session: AsyncSession = Depends(get_session)):
    run = await session.get(AgentRun, run_id)
    if not run:
        raise HTTPException(404, "Agent run not found")
    return run


@router.post("/{run_id}/stop", response_model=AgentRunResponse)
async def stop_agent_run(run_id: str, session: AsyncSession = Depends(get_session)):
    run = await session.get(AgentRun, run_id)
    if not run:
        raise HTTPException(404, "Agent run not found")

    if run.state in (AgentRunState.FINISHED, AgentRunState.FAILED):
        raise HTTPException(400, f"Agent run is already in terminal state: {run.state}")

    run.state = AgentRunState.FAILED
    run.error_message = "Stopped by user"
    await session.commit()
    await session.refresh(run)
    return run


@router.put("/{run_id}/state", response_model=AgentRunResponse)
async def update_agent_run_state(
    run_id: str, state: str, session: AsyncSession = Depends(get_session)
):
    run = await session.get(AgentRun, run_id)
    if not run:
        raise HTTPException(404, "Agent run not found")

    try:
        new_state = AgentRunState(state)
    except ValueError:
        raise HTTPException(400, f"Invalid state: {state}")

    run.state = new_state
    await session.commit()
    await session.refresh(run)
    return run
