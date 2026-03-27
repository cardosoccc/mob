"""Unit tests for Template model."""

import pytest
from sqlalchemy import select

from mob.models.template import Template


@pytest.mark.asyncio
async def test_create_template(session):
    tmpl = Template(
        name="test-template",
        image="mob-agent-pydantic:latest",
        runtime="pydantic-ai",
        description="Test template",
        capabilities='["chat"]',
    )
    session.add(tmpl)
    await session.commit()

    result = await session.execute(select(Template).where(Template.name == "test-template"))
    fetched = result.scalar_one()
    assert fetched.image == "mob-agent-pydantic:latest"
    assert fetched.runtime == "pydantic-ai"
    assert fetched.id is not None
    assert fetched.created_at is not None


@pytest.mark.asyncio
async def test_template_with_resource_limits(session):
    tmpl = Template(
        name="resource-template",
        image="mob-agent-pi:latest",
        runtime="pi",
        resource_cpu_limit="2000m",
        resource_memory_limit="2Gi",
    )
    session.add(tmpl)
    await session.commit()

    result = await session.execute(select(Template).where(Template.name == "resource-template"))
    fetched = result.scalar_one()
    assert fetched.resource_cpu_limit == "2000m"
    assert fetched.resource_memory_limit == "2Gi"


@pytest.mark.asyncio
async def test_template_repr(session):
    tmpl = Template(name="repr-tmpl", image="img:latest", runtime="pi")
    session.add(tmpl)
    await session.commit()
    assert "repr-tmpl" in repr(tmpl)
