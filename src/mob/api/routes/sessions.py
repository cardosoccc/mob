"""Session API routes."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from mob.database import get_session
from mob.schemas import SessionCreate, SessionResponse, SessionSendMessage
from mob.services import ServiceError
from mob.services import sessions as session_service

router = APIRouter()


@router.get("", response_model=list[SessionResponse])
async def list_sessions(
    agent_id: str | None = None,
    state: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    try:
        return await session_service.list_sessions(session, agent_id=agent_id, state=state)
    except ServiceError as e:
        raise HTTPException(e.status_code, e.message)


@router.post("", response_model=SessionResponse, status_code=201)
async def create_session(
    data: SessionCreate, session: AsyncSession = Depends(get_session)
):
    try:
        return await session_service.create_session(
            session, agent_id=data.agent_id, task_id=data.task_id, name=data.name
        )
    except ServiceError as e:
        raise HTTPException(e.status_code, e.message)


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session_by_id(session_id: str, session: AsyncSession = Depends(get_session)):
    try:
        return await session_service.get_session(session, session_id)
    except ServiceError as e:
        raise HTTPException(e.status_code, e.message)


@router.get("/{session_id}/logs")
async def get_session_logs(session_id: str, tail: int = 100):
    """Fetch live logs from the Session CR status in Kubernetes."""
    status = await session_service.get_session_live_status(session_id)
    logs = status.get("logs", [])
    if tail and len(logs) > tail:
        logs = logs[-tail:]
    return JSONResponse(content={"logs": logs, "status": status})


@router.post("/{session_id}/stop", response_model=SessionResponse)
async def stop_session(session_id: str, session: AsyncSession = Depends(get_session)):
    try:
        return await session_service.stop_session(session, session_id)
    except ServiceError as e:
        raise HTTPException(e.status_code, e.message)


@router.put("/{session_id}/state", response_model=SessionResponse)
async def update_session_state(
    session_id: str, state: str, session: AsyncSession = Depends(get_session)
):
    try:
        return await session_service.update_session_state(session, session_id, state)
    except ServiceError as e:
        raise HTTPException(e.status_code, e.message)


@router.post("/{session_id}/send")
async def send_to_session(
    session_id: str,
    data: SessionSendMessage,
    session: AsyncSession = Depends(get_session),
):
    try:
        return await session_service.send_message(session, session_id, message=data.message)
    except ServiceError as e:
        raise HTTPException(e.status_code, e.message)
