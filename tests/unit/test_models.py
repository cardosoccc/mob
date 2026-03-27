"""Unit tests for database models."""

import pytest
import pytest_asyncio
from sqlalchemy import select

from mob.models.organization import Organization
from mob.models.domain import Domain
from mob.models.user import User
from mob.models.group import Group, GroupMember
from mob.models.agent import Agent, AgentSkill
from mob.models.session import Session, SessionState
from mob.models.task import Task
from mob.models.skill import Skill


@pytest.mark.asyncio
async def test_create_organization(session):
    org = Organization(identifier="test-org", name="Test Organization")
    session.add(org)
    await session.commit()

    result = await session.execute(select(Organization).where(Organization.identifier == "test-org"))
    fetched = result.scalar_one()
    assert fetched.name == "Test Organization"
    assert fetched.identifier == "test-org"
    assert fetched.id is not None
    assert fetched.created_at is not None


@pytest.mark.asyncio
async def test_create_domain(session):
    org = Organization(identifier="org-d", name="Org D")
    session.add(org)
    await session.flush()

    domain = Domain(identifier="org-d-dev", name="Development", organization_id=org.id)
    session.add(domain)
    await session.commit()

    result = await session.execute(select(Domain).where(Domain.identifier == "org-d-dev"))
    fetched = result.scalar_one()
    assert fetched.name == "Development"
    assert fetched.organization_id == org.id


@pytest.mark.asyncio
async def test_create_user(session):
    user = User(email="test@example.com", name="Test User")
    session.add(user)
    await session.commit()

    result = await session.execute(select(User).where(User.email == "test@example.com"))
    fetched = result.scalar_one()
    assert fetched.name == "Test User"
    assert fetched.id is not None


@pytest.mark.asyncio
async def test_create_group(session):
    org = Organization(identifier="org-g", name="Org G")
    session.add(org)
    await session.flush()

    group = Group(name="engineers", organization_id=org.id)
    session.add(group)
    await session.commit()

    result = await session.execute(select(Group).where(Group.name == "engineers"))
    fetched = result.scalar_one()
    assert fetched.organization_id == org.id


@pytest.mark.asyncio
async def test_group_membership(session):
    org = Organization(identifier="org-gm", name="Org GM")
    session.add(org)
    await session.flush()

    group = Group(name="team", organization_id=org.id)
    session.add(group)
    user = User(email="member@example.com", name="Member")
    session.add(user)
    await session.flush()

    member = GroupMember(group_id=group.id, user_id=user.id)
    session.add(member)
    await session.commit()

    result = await session.execute(select(GroupMember).where(GroupMember.group_id == group.id))
    fetched = result.scalar_one()
    assert fetched.user_id == user.id


@pytest.mark.asyncio
async def test_create_skill(session):
    skill = Skill(name="code-review", description="Reviews code", skills_md="# Code Review")
    session.add(skill)
    await session.commit()

    result = await session.execute(select(Skill).where(Skill.name == "code-review"))
    fetched = result.scalar_one()
    assert fetched.description == "Reviews code"
    assert fetched.skills_md == "# Code Review"


@pytest.mark.asyncio
async def test_create_agent(session):
    org = Organization(identifier="org-a", name="Org A")
    session.add(org)
    await session.flush()

    domain = Domain(identifier="org-a-default", name="Default", organization_id=org.id)
    session.add(domain)
    await session.flush()

    agent = Agent(
        name="test-agent",
        system_prompt="You are a test agent.",
        agent_template="ghcr.io/test/agent:latest",
        domain_id=domain.id,
    )
    session.add(agent)
    await session.commit()

    result = await session.execute(select(Agent).where(Agent.name == "test-agent"))
    fetched = result.scalar_one()
    assert fetched.agent_template == "ghcr.io/test/agent:latest"
    assert fetched.domain_id == domain.id


@pytest.mark.asyncio
async def test_agent_with_skills(session):
    org = Organization(identifier="org-as", name="Org AS")
    session.add(org)
    await session.flush()

    domain = Domain(identifier="org-as-default", name="Default", organization_id=org.id)
    session.add(domain)
    await session.flush()

    skill = Skill(name="testing", description="Testing skill")
    session.add(skill)
    await session.flush()

    agent = Agent(name="skilled-agent", agent_template="test:latest", domain_id=domain.id)
    session.add(agent)
    await session.flush()

    agent_skill = AgentSkill(agent_id=agent.id, skill_id=skill.id)
    session.add(agent_skill)
    await session.commit()

    result = await session.execute(select(AgentSkill).where(AgentSkill.agent_id == agent.id))
    fetched = result.scalar_one()
    assert fetched.skill_id == skill.id


@pytest.mark.asyncio
async def test_create_task(session):
    org = Organization(identifier="org-t", name="Org T")
    session.add(org)
    await session.flush()

    domain = Domain(identifier="org-t-default", name="Default", organization_id=org.id)
    session.add(domain)
    await session.flush()

    agent = Agent(name="task-agent", agent_template="test:latest", domain_id=domain.id)
    session.add(agent)
    await session.flush()

    task = Task(
        instruction="Write a hello world program",
        definition_of_done="Program outputs 'Hello, World!'",
        agent_id=agent.id,
    )
    session.add(task)
    await session.commit()

    result = await session.execute(select(Task).where(Task.agent_id == agent.id))
    fetched = result.scalar_one()
    assert fetched.instruction == "Write a hello world program"
    assert fetched.definition_of_done == "Program outputs 'Hello, World!'"


@pytest.mark.asyncio
async def test_create_session(session):
    org = Organization(identifier="org-ar", name="Org AR")
    session.add(org)
    await session.flush()

    domain = Domain(identifier="org-ar-default", name="Default", organization_id=org.id)
    session.add(domain)
    await session.flush()

    agent = Agent(name="run-agent", agent_template="test:latest", domain_id=domain.id)
    session.add(agent)
    await session.flush()

    sess = Session(name="run-agent-abc12345", agent_id=agent.id, state=SessionState.PENDING)
    session.add(sess)
    await session.commit()

    result = await session.execute(select(Session).where(Session.agent_id == agent.id))
    fetched = result.scalar_one()
    assert fetched.state == SessionState.PENDING
    assert fetched.name == "run-agent-abc12345"


@pytest.mark.asyncio
async def test_session_states(session):
    """Test all valid session states."""
    org = Organization(identifier="org-ars", name="Org ARS")
    session.add(org)
    await session.flush()

    domain = Domain(identifier="org-ars-default", name="Default", organization_id=org.id)
    session.add(domain)
    await session.flush()

    agent = Agent(name="state-agent", agent_template="test:latest", domain_id=domain.id)
    session.add(agent)
    await session.flush()

    for i, state in enumerate(SessionState):
        sess = Session(name=f"state-agent-{state.value}-{i}", agent_id=agent.id, state=state)
        session.add(sess)

    await session.commit()

    result = await session.execute(select(Session).where(Session.agent_id == agent.id))
    sessions = result.scalars().all()
    states = {s.state for s in sessions}
    assert states == {
        SessionState.PENDING,
        SessionState.STARTING,
        SessionState.IDLE,
        SessionState.BUSY,
        SessionState.FINISHED,
        SessionState.FAILED,
    }
