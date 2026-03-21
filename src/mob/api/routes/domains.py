"""Domain API routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from mob.database import get_session
from mob.schemas import DomainCreate, DomainResponse, DomainUpdate
from mob.services import ServiceError
from mob.services import domains as domain_service

router = APIRouter()


@router.get("", response_model=list[DomainResponse])
async def list_domains(
    organization_id: str | None = None, session: AsyncSession = Depends(get_session)
):
    return await domain_service.list_domains(session, organization_id=organization_id)


@router.post("", response_model=DomainResponse, status_code=201)
async def create_domain(data: DomainCreate, session: AsyncSession = Depends(get_session)):
    try:
        return await domain_service.create_domain(
            session,
            identifier_suffix=data.identifier_suffix,
            name=data.name,
            organization_id=data.organization_id,
        )
    except ServiceError as e:
        raise HTTPException(e.status_code, e.message)


@router.get("/{domain_id}", response_model=DomainResponse)
async def get_domain(domain_id: str, session: AsyncSession = Depends(get_session)):
    try:
        return await domain_service.get_domain(session, domain_id)
    except ServiceError as e:
        raise HTTPException(e.status_code, e.message)


@router.put("/{domain_id}", response_model=DomainResponse)
async def update_domain(
    domain_id: str, data: DomainUpdate, session: AsyncSession = Depends(get_session)
):
    try:
        return await domain_service.update_domain(session, domain_id, name=data.name)
    except ServiceError as e:
        raise HTTPException(e.status_code, e.message)


@router.delete("/{domain_id}", status_code=204)
async def delete_domain(domain_id: str, session: AsyncSession = Depends(get_session)):
    try:
        await domain_service.delete_domain(session, domain_id)
    except ServiceError as e:
        raise HTTPException(e.status_code, e.message)
