"""AgentRun API routes."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from mob.database import get_session
from mob.schemas import AgentRunCreate, AgentRunResponse, AgentRunSendMessage
from mob.services import ServiceError
from mob.services import agent_runs as run_service

router = APIRouter()


@router.get("", response_model=list[AgentRunResponse])
async def list_agent_runs(
    agent_id: str | None = None,
    state: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    try:
        return await run_service.list_agent_runs(session, agent_id=agent_id, state=state)
    except ServiceError as e:
        raise HTTPException(e.status_code, e.message)


@router.post("", response_model=AgentRunResponse, status_code=201)
async def create_agent_run(
    data: AgentRunCreate, session: AsyncSession = Depends(get_session)
):
    try:
        return await run_service.create_agent_run(
            session, agent_id=data.agent_id, task_id=data.task_id, name=data.name
        )
    except ServiceError as e:
        raise HTTPException(e.status_code, e.message)


@router.get("/{run_id}", response_model=AgentRunResponse)
async def get_agent_run(run_id: str, session: AsyncSession = Depends(get_session)):
    try:
        return await run_service.get_agent_run(session, run_id)
    except ServiceError as e:
        raise HTTPException(e.status_code, e.message)


@router.get("/{run_id}/logs")
async def get_agent_run_logs(run_id: str, tail: int = 100):
    """Fetch live logs from the AgentRun CR status in Kubernetes."""
    status = await run_service.get_agent_run_live_status(run_id)
    logs = status.get("logs", [])
    if tail and len(logs) > tail:
        logs = logs[-tail:]
    return JSONResponse(content={"logs": logs, "status": status})


@router.post("/{run_id}/stop", response_model=AgentRunResponse)
async def stop_agent_run(run_id: str, session: AsyncSession = Depends(get_session)):
    try:
        return await run_service.stop_agent_run(session, run_id)
    except ServiceError as e:
        raise HTTPException(e.status_code, e.message)


@router.put("/{run_id}/state", response_model=AgentRunResponse)
async def update_agent_run_state(
    run_id: str, state: str, session: AsyncSession = Depends(get_session)
):
    try:
        return await run_service.update_agent_run_state(session, run_id, state)
    except ServiceError as e:
        raise HTTPException(e.status_code, e.message)


@router.post("/{run_id}/send")
async def send_to_agent_run(
    run_id: str,
    data: AgentRunSendMessage,
    session: AsyncSession = Depends(get_session),
):
    try:
        return await run_service.send_message(session, run_id, message=data.message)
    except ServiceError as e:
        raise HTTPException(e.status_code, e.message)
