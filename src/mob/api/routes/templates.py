"""Template API routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from mob.database import get_session
from mob.schemas import TemplateCreate, TemplateResponse, TemplateUpdate
from mob.services import ServiceError
from mob.services import templates as template_service

router = APIRouter()


@router.get("", response_model=list[TemplateResponse])
async def list_templates(session: AsyncSession = Depends(get_session)):
    return await template_service.list_templates(session)


@router.post("", response_model=TemplateResponse, status_code=201)
async def create_template(data: TemplateCreate, session: AsyncSession = Depends(get_session)):
    try:
        return await template_service.create_template(
            session,
            name=data.name,
            image=data.image,
            runtime=data.runtime,
            description=data.description,
            capabilities=data.capabilities,
            resource_cpu_limit=data.resource_cpu_limit,
            resource_memory_limit=data.resource_memory_limit,
        )
    except ServiceError as e:
        raise HTTPException(e.status_code, e.message)


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(template_id: str, session: AsyncSession = Depends(get_session)):
    try:
        return await template_service.get_template(session, template_id)
    except ServiceError as e:
        raise HTTPException(e.status_code, e.message)


@router.put("/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: str, data: TemplateUpdate, session: AsyncSession = Depends(get_session)
):
    try:
        return await template_service.update_template(
            session,
            template_id,
            name=data.name,
            image=data.image,
            description=data.description,
            runtime=data.runtime,
            capabilities=data.capabilities,
            resource_cpu_limit=data.resource_cpu_limit,
            resource_memory_limit=data.resource_memory_limit,
        )
    except ServiceError as e:
        raise HTTPException(e.status_code, e.message)


@router.delete("/{template_id}", status_code=204)
async def delete_template(template_id: str, session: AsyncSession = Depends(get_session)):
    try:
        await template_service.delete_template(session, template_id)
    except ServiceError as e:
        raise HTTPException(e.status_code, e.message)
