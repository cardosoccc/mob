"""Organization API routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from mob.database import get_session
from mob.schemas import OrganizationCreate, OrganizationResponse, OrganizationUpdate
from mob.services import ServiceError
from mob.services import organizations as org_service

router = APIRouter()


@router.get("", response_model=list[OrganizationResponse])
async def list_organizations(session: AsyncSession = Depends(get_session)):
    return await org_service.list_organizations(session)


@router.post("", response_model=OrganizationResponse, status_code=201)
async def create_organization(
    data: OrganizationCreate, session: AsyncSession = Depends(get_session)
):
    try:
        return await org_service.create_organization(
            session, identifier=data.identifier, name=data.name
        )
    except ServiceError as e:
        raise HTTPException(e.status_code, e.message)


@router.get("/{org_id}", response_model=OrganizationResponse)
async def get_organization(org_id: str, session: AsyncSession = Depends(get_session)):
    try:
        return await org_service.get_organization(session, org_id)
    except ServiceError as e:
        raise HTTPException(e.status_code, e.message)


@router.put("/{org_id}", response_model=OrganizationResponse)
async def update_organization(
    org_id: str, data: OrganizationUpdate, session: AsyncSession = Depends(get_session)
):
    try:
        return await org_service.update_organization(session, org_id, name=data.name)
    except ServiceError as e:
        raise HTTPException(e.status_code, e.message)


@router.delete("/{org_id}", status_code=204)
async def delete_organization(org_id: str, session: AsyncSession = Depends(get_session)):
    try:
        await org_service.delete_organization(session, org_id)
    except ServiceError as e:
        raise HTTPException(e.status_code, e.message)
