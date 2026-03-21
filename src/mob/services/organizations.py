"""Organization service."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mob.models.domain import Domain
from mob.models.group import Group
from mob.models.organization import Organization
from mob.services import ServiceError


async def list_organizations(session: AsyncSession) -> list[Organization]:
    result = await session.execute(select(Organization).order_by(Organization.name))
    return list(result.scalars().all())


async def create_organization(
    session: AsyncSession, identifier: str, name: str
) -> Organization:
    existing = await session.execute(
        select(Organization).where(Organization.identifier == identifier)
    )
    if existing.scalar_one_or_none():
        raise ServiceError(
            f"Organization with identifier '{identifier}' already exists", 400
        )

    org = Organization(identifier=identifier, name=name)
    session.add(org)
    await session.flush()

    # Create default domain
    default_domain = Domain(
        identifier=f"{identifier}-default",
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


async def get_organization(session: AsyncSession, org_id: str) -> Organization:
    org = await session.get(Organization, org_id)
    if not org:
        raise ServiceError("Organization not found", 404)
    return org


async def update_organization(
    session: AsyncSession, org_id: str, name: str | None = None
) -> Organization:
    org = await session.get(Organization, org_id)
    if not org:
        raise ServiceError("Organization not found", 404)
    if name is not None:
        org.name = name
    await session.commit()
    await session.refresh(org)
    return org


async def delete_organization(session: AsyncSession, org_id: str) -> None:
    org = await session.get(Organization, org_id)
    if not org:
        raise ServiceError("Organization not found", 404)
    await session.delete(org)
    await session.commit()
