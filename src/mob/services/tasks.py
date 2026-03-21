"""Task service."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mob.models.task import Task
from mob.services import ServiceError


async def list_tasks(
    session: AsyncSession, agent_id: str | None = None
) -> list[Task]:
    query = select(Task).order_by(Task.created_at.desc())
    if agent_id:
        query = query.where(Task.agent_id == agent_id)
    result = await session.execute(query)
    return list(result.scalars().all())


async def create_task(
    session: AsyncSession,
    instruction: str,
    agent_id: str,
    definition_of_done: str | None = None,
) -> Task:
    task = Task(
        instruction=instruction,
        definition_of_done=definition_of_done,
        agent_id=agent_id,
    )
    session.add(task)
    await session.commit()
    await session.refresh(task)
    return task


async def get_task(session: AsyncSession, task_id: str) -> Task:
    task = await session.get(Task, task_id)
    if not task:
        raise ServiceError("Task not found", 404)
    return task
