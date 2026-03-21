"""AgentRun service."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mob.models.agent import Agent
from mob.models.agent_run import AgentRun, AgentRunState
from mob.services import ServiceError


async def list_agent_runs(
    session: AsyncSession, agent_id: str | None = None
) -> list[AgentRun]:
    query = select(AgentRun).order_by(AgentRun.created_at.desc())
    if agent_id:
        query = query.where(AgentRun.agent_id == agent_id)
    result = await session.execute(query)
    return list(result.scalars().all())


async def create_agent_run(
    session: AsyncSession, agent_id: str, task_id: str | None = None
) -> AgentRun:
    agent = await session.get(Agent, agent_id)
    if not agent:
        raise ServiceError("Agent not found", 404)

    run = AgentRun(
        agent_id=agent_id,
        state=AgentRunState.PENDING,
        task_id=task_id,
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return run


async def get_agent_run(session: AsyncSession, run_id: str) -> AgentRun:
    run = await session.get(AgentRun, run_id)
    if not run:
        raise ServiceError("Agent run not found", 404)
    return run


async def stop_agent_run(session: AsyncSession, run_id: str) -> AgentRun:
    run = await session.get(AgentRun, run_id)
    if not run:
        raise ServiceError("Agent run not found", 404)

    if run.state in (AgentRunState.FINISHED, AgentRunState.FAILED):
        raise ServiceError(
            f"Agent run is already in terminal state: {run.state}", 400
        )

    run.state = AgentRunState.FAILED
    run.error_message = "Stopped by user"
    await session.commit()
    await session.refresh(run)
    return run


async def update_agent_run_state(
    session: AsyncSession, run_id: str, state: str
) -> AgentRun:
    run = await session.get(AgentRun, run_id)
    if not run:
        raise ServiceError("Agent run not found", 404)

    try:
        new_state = AgentRunState(state)
    except ValueError:
        raise ServiceError(f"Invalid state: {state}", 400)

    run.state = new_state
    await session.commit()
    await session.refresh(run)
    return run
