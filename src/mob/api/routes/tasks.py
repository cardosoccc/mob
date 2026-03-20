"""Task API routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mob.database import get_session
from mob.models.task import Task
from mob.schemas import TaskCreate, TaskResponse

router = APIRouter()


@router.get("", response_model=list[TaskResponse])
async def list_tasks(
    agent_id: str | None = None, session: AsyncSession = Depends(get_session)
):
    query = select(Task).order_by(Task.created_at.desc())
    if agent_id:
        query = query.where(Task.agent_id == agent_id)
    result = await session.execute(query)
    return result.scalars().all()


@router.post("", response_model=TaskResponse, status_code=201)
async def create_task(data: TaskCreate, session: AsyncSession = Depends(get_session)):
    task = Task(
        instruction=data.instruction,
        definition_of_done=data.definition_of_done,
        agent_id=data.agent_id,
    )
    session.add(task)
    await session.commit()
    await session.refresh(task)
    return task


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str, session: AsyncSession = Depends(get_session)):
    task = await session.get(Task, task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    return task
