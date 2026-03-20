"""Domain API routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mob.database import get_session
from mob.models.domain import Domain
from mob.models.group import Group
from mob.models.organization import Organization
from mob.schemas import DomainCreate, DomainResponse, DomainUpdate

router = APIRouter()


@router.get("", response_model=list[DomainResponse])
async def list_domains(
    organization_id: str | None = None, session: AsyncSession = Depends(get_session)
):
    query = select(Domain).order_by(Domain.identifier)
    if organization_id:
        query = query.where(Domain.organization_id == organization_id)
    result = await session.execute(query)
    return result.scalars().all()


@router.post("", response_model=DomainResponse, status_code=201)
async def create_domain(data: DomainCreate, session: AsyncSession = Depends(get_session)):
    org = await session.get(Organization, data.organization_id)
    if not org:
        raise HTTPException(404, "Organization not found")

    identifier = f"{org.identifier}-{data.identifier_suffix}"
    existing = await session.execute(select(Domain).where(Domain.identifier == identifier))
    if existing.scalar_one_or_none():
        raise HTTPException(400, f"Domain with identifier '{identifier}' already exists")

    domain = Domain(
        identifier=identifier,
        name=data.name,
        organization_id=data.organization_id,
    )
    session.add(domain)
    await session.flush()

    # Create corresponding group for the domain
    group = Group(name=data.identifier_suffix, organization_id=data.organization_id)
    session.add(group)

    await session.commit()
    await session.refresh(domain)
    return domain


@router.get("/{domain_id}", response_model=DomainResponse)
async def get_domain(domain_id: str, session: AsyncSession = Depends(get_session)):
    domain = await session.get(Domain, domain_id)
    if not domain:
        raise HTTPException(404, "Domain not found")
    return domain


@router.put("/{domain_id}", response_model=DomainResponse)
async def update_domain(
    domain_id: str, data: DomainUpdate, session: AsyncSession = Depends(get_session)
):
    domain = await session.get(Domain, domain_id)
    if not domain:
        raise HTTPException(404, "Domain not found")
    if data.name is not None:
        domain.name = data.name
    await session.commit()
    await session.refresh(domain)
    return domain


@router.delete("/{domain_id}", status_code=204)
async def delete_domain(domain_id: str, session: AsyncSession = Depends(get_session)):
    domain = await session.get(Domain, domain_id)
    if not domain:
        raise HTTPException(404, "Domain not found")
    await session.delete(domain)
    await session.commit()
