"""Task API routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from mob.database import get_session
from mob.schemas import TaskCreate, TaskResponse
from mob.services import ServiceError
from mob.services import tasks as task_service

router = APIRouter()


@router.get("", response_model=list[TaskResponse])
async def list_tasks(
    agent_id: str | None = None, session: AsyncSession = Depends(get_session)
):
    return await task_service.list_tasks(session, agent_id=agent_id)


@router.post("", response_model=TaskResponse, status_code=201)
async def create_task(data: TaskCreate, session: AsyncSession = Depends(get_session)):
    try:
        return await task_service.create_task(
            session,
            instruction=data.instruction,
            agent_id=data.agent_id,
            definition_of_done=data.definition_of_done,
        )
    except ServiceError as e:
        raise HTTPException(e.status_code, e.message)


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str, session: AsyncSession = Depends(get_session)):
    try:
        return await task_service.get_task(session, task_id)
    except ServiceError as e:
        raise HTTPException(e.status_code, e.message)
