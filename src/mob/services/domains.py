"""Domain service."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mob.models.domain import Domain
from mob.models.group import Group
from mob.models.organization import Organization
from mob.services import ServiceError


async def list_domains(
    session: AsyncSession, organization_id: str | None = None
) -> list[Domain]:
    query = select(Domain).order_by(Domain.identifier)
    if organization_id:
        query = query.where(Domain.organization_id == organization_id)
    result = await session.execute(query)
    return list(result.scalars().all())


async def create_domain(
    session: AsyncSession,
    identifier_suffix: str,
    name: str,
    organization_id: str,
) -> Domain:
    org = await session.get(Organization, organization_id)
    if not org:
        raise ServiceError("Organization not found", 404)

    identifier = f"{org.identifier}-{identifier_suffix}"
    existing = await session.execute(
        select(Domain).where(Domain.identifier == identifier)
    )
    if existing.scalar_one_or_none():
        raise ServiceError(
            f"Domain with identifier '{identifier}' already exists", 400
        )

    domain = Domain(
        identifier=identifier,
        name=name,
        organization_id=organization_id,
    )
    session.add(domain)
    await session.flush()

    # Create corresponding group for the domain
    group = Group(name=identifier_suffix, organization_id=organization_id)
    session.add(group)

    await session.commit()
    await session.refresh(domain)
    return domain


async def get_domain(session: AsyncSession, domain_id: str) -> Domain:
    domain = await session.get(Domain, domain_id)
    if not domain:
        raise ServiceError("Domain not found", 404)
    return domain


async def update_domain(
    session: AsyncSession, domain_id: str, name: str | None = None
) -> Domain:
    domain = await session.get(Domain, domain_id)
    if not domain:
        raise ServiceError("Domain not found", 404)
    if name is not None:
        domain.name = name
    await session.commit()
    await session.refresh(domain)
    return domain


async def delete_domain(session: AsyncSession, domain_id: str) -> None:
    domain = await session.get(Domain, domain_id)
    if not domain:
        raise ServiceError("Domain not found", 404)
    await session.delete(domain)
    await session.commit()
