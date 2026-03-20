"""Organization API routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mob.database import get_session
from mob.models.organization import Organization
from mob.models.domain import Domain
from mob.models.group import Group
from mob.schemas import OrganizationCreate, OrganizationResponse, OrganizationUpdate

router = APIRouter()


@router.get("", response_model=list[OrganizationResponse])
async def list_organizations(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Organization).order_by(Organization.name))
    return result.scalars().all()


@router.post("", response_model=OrganizationResponse, status_code=201)
async def create_organization(
    data: OrganizationCreate, session: AsyncSession = Depends(get_session)
):
    existing = await session.execute(
        select(Organization).where(Organization.identifier == data.identifier)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(400, f"Organization with identifier '{data.identifier}' already exists")

    org = Organization(identifier=data.identifier, name=data.name)
    session.add(org)
    await session.flush()

    # Create default domain
    default_domain = Domain(
        identifier=f"{data.identifier}-default",
        name="Default",
        organization_id=org.id,
    )
    session.add(default_domain)

    # Create default group for the default domain
    default_group = Group(
        name="default",
        organization_id=org.id,
    )
    session.add(default_group)

    await session.commit()
    await session.refresh(org)
    return org


@router.get("/{org_id}", response_model=OrganizationResponse)
async def get_organization(org_id: str, session: AsyncSession = Depends(get_session)):
    org = await session.get(Organization, org_id)
    if not org:
        raise HTTPException(404, "Organization not found")
    return org


@router.put("/{org_id}", response_model=OrganizationResponse)
async def update_organization(
    org_id: str, data: OrganizationUpdate, session: AsyncSession = Depends(get_session)
):
    org = await session.get(Organization, org_id)
    if not org:
        raise HTTPException(404, "Organization not found")
    if data.name is not None:
        org.name = data.name
    await session.commit()
    await session.refresh(org)
    return org


@router.delete("/{org_id}", status_code=204)
async def delete_organization(org_id: str, session: AsyncSession = Depends(get_session)):
    org = await session.get(Organization, org_id)
    if not org:
        raise HTTPException(404, "Organization not found")
    await session.delete(org)
    await session.commit()
