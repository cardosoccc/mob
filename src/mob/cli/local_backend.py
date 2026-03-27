"""Local backend - calls service layer directly for local mode."""

import asyncio
import re
import sys
from typing import Any

from mob.database import get_session_factory, init_db
from mob.schemas import (
    AgentResponse,
    SessionResponse,
    DomainResponse,
    GroupResponse,
    OrganizationResponse,
    SkillResponse,
    TaskResponse,
    UserResponse,
)
from mob.services import ServiceError
from mob.services import sessions as session_svc
from mob.services import agents as agent_svc
from mob.services import domains as domain_svc
from mob.services import groups as group_svc
from mob.services import organizations as org_svc
from mob.services import skills as skill_svc
from mob.services import tasks as task_svc
from mob.services import users as user_svc


def _to_dict(model: Any, schema_class: type) -> dict:
    """Convert a SQLAlchemy model to a dict using a Pydantic response schema."""
    return schema_class.model_validate(model).model_dump(mode="json")


def _to_list(models: list, schema_class: type) -> list[dict]:
    return [_to_dict(m, schema_class) for m in models]


def _match(pattern: str, path: str) -> re.Match | None:
    return re.match(pattern, path)


async def _execute(method: str, path: str, data: dict | None = None, params: dict | None = None) -> Any:
    """Route the request to the appropriate service function."""
    await init_db()
    factory = get_session_factory()
    async with factory() as session:
        return await _route(session, method, path, data or {}, params or {})


async def _route(session: Any, method: str, path: str, data: dict, params: dict) -> Any:
    """Match path and dispatch to service."""

    # ── Organizations ──────────────────────────────────────────
    if path == "/organizations":
        if method == "GET":
            models = await org_svc.list_organizations(session)
            return _to_list(models, OrganizationResponse)
        if method == "POST":
            model = await org_svc.create_organization(
                session, identifier=data["identifier"], name=data["name"]
            )
            return _to_dict(model, OrganizationResponse)

    m = _match(r"^/organizations/([^/]+)$", path)
    if m:
        org_id = m.group(1)
        if method == "GET":
            model = await org_svc.get_organization(session, org_id)
            return _to_dict(model, OrganizationResponse)
        if method == "PUT":
            model = await org_svc.update_organization(
                session, org_id, name=data.get("name")
            )
            return _to_dict(model, OrganizationResponse)
        if method == "DELETE":
            await org_svc.delete_organization(session, org_id)
            return None

    # ── Domains ────────────────────────────────────────────────
    if path == "/domains":
        if method == "GET":
            models = await domain_svc.list_domains(
                session, organization_id=params.get("organization_id")
            )
            return _to_list(models, DomainResponse)
        if method == "POST":
            model = await domain_svc.create_domain(
                session,
                identifier_suffix=data["identifier_suffix"],
                name=data["name"],
                organization_id=data["organization_id"],
            )
            return _to_dict(model, DomainResponse)

    m = _match(r"^/domains/([^/]+)$", path)
    if m:
        domain_id = m.group(1)
        if method == "GET":
            model = await domain_svc.get_domain(session, domain_id)
            return _to_dict(model, DomainResponse)
        if method == "PUT":
            model = await domain_svc.update_domain(
                session, domain_id, name=data.get("name")
            )
            return _to_dict(model, DomainResponse)
        if method == "DELETE":
            await domain_svc.delete_domain(session, domain_id)
            return None

    # ── Users ──────────────────────────────────────────────────
    if path == "/users":
        if method == "GET":
            models = await user_svc.list_users(session)
            return _to_list(models, UserResponse)
        if method == "POST":
            model = await user_svc.create_user(
                session, email=data["email"], name=data["name"]
            )
            return _to_dict(model, UserResponse)

    m = _match(r"^/users/([^/]+)$", path)
    if m:
        user_id = m.group(1)
        if method == "GET":
            model = await user_svc.get_user(session, user_id)
            return _to_dict(model, UserResponse)
        if method == "PUT":
            model = await user_svc.update_user(
                session, user_id, name=data.get("name"), email=data.get("email")
            )
            return _to_dict(model, UserResponse)
        if method == "DELETE":
            await user_svc.delete_user(session, user_id)
            return None

    # ── Groups ─────────────────────────────────────────────────
    if path == "/groups":
        if method == "GET":
            models = await group_svc.list_groups(
                session, organization_id=params.get("organization_id")
            )
            return _to_list(models, GroupResponse)
        if method == "POST":
            model = await group_svc.create_group(
                session, name=data["name"], organization_id=data["organization_id"]
            )
            return _to_dict(model, GroupResponse)

    m = _match(r"^/groups/([^/]+)/members/([^/]+)$", path)
    if m:
        group_id, user_id = m.group(1), m.group(2)
        if method == "DELETE":
            await group_svc.remove_member(session, group_id, user_id)
            return None

    m = _match(r"^/groups/([^/]+)/members$", path)
    if m:
        group_id = m.group(1)
        if method == "POST":
            return await group_svc.add_member(
                session, group_id, user_id=data["user_id"]
            )

    m = _match(r"^/groups/([^/]+)$", path)
    if m:
        group_id = m.group(1)
        if method == "GET":
            model = await group_svc.get_group(session, group_id)
            return _to_dict(model, GroupResponse)
        if method == "PUT":
            model = await group_svc.update_group(
                session, group_id, name=data.get("name")
            )
            return _to_dict(model, GroupResponse)
        if method == "DELETE":
            await group_svc.delete_group(session, group_id)
            return None

    # ── Agents ─────────────────────────────────────────────────
    if path == "/agents":
        if method == "GET":
            models = await agent_svc.list_agents(
                session, domain_id=params.get("domain_id")
            )
            return _to_list(models, AgentResponse)
        if method == "POST":
            model = await agent_svc.create_agent(
                session,
                name=data["name"],
                agent_template=data["agent_template"],
                domain_id=data["domain_id"],
                system_prompt=data.get("system_prompt"),
                model_endpoint=data.get("model_endpoint"),
                skill_ids=data.get("skill_ids", []),
                env_defaults=data.get("env_defaults"),
                custom_config=data.get("custom_config"),
            )
            return _to_dict(model, AgentResponse)

    m = _match(r"^/agents/([^/]+)$", path)
    if m:
        agent_id = m.group(1)
        if method == "GET":
            model = await agent_svc.get_agent(session, agent_id)
            return _to_dict(model, AgentResponse)
        if method == "PUT":
            model = await agent_svc.update_agent(
                session,
                agent_id,
                name=data.get("name"),
                system_prompt=data.get("system_prompt"),
                agent_template=data.get("agent_template"),
                model_endpoint=data.get("model_endpoint"),
                skill_ids=data.get("skill_ids"),
                env_defaults=data.get("env_defaults"),
                custom_config=data.get("custom_config"),
            )
            return _to_dict(model, AgentResponse)
        if method == "DELETE":
            await agent_svc.delete_agent(session, agent_id)
            return None

    # ── Sessions ───────────────────────────────────────────────
    if path == "/sessions":
        if method == "GET":
            models = await session_svc.list_sessions(
                session,
                agent_id=params.get("agent_id"),
                state=params.get("state"),
            )
            return _to_list(models, SessionResponse)
        if method == "POST":
            model = await session_svc.create_session(
                session,
                agent_id=data["agent_id"],
                task_id=data.get("task_id"),
                name=data.get("name"),
                env_overrides=data.get("env_overrides"),
            )
            return _to_dict(model, SessionResponse)

    m = _match(r"^/sessions/([^/]+)/send$", path)
    if m:
        session_id = m.group(1)
        if method == "POST":
            return await session_svc.send_message(
                session, session_id, message=data["message"]
            )

    m = _match(r"^/sessions/([^/]+)/logs$", path)
    if m:
        session_id = m.group(1)
        if method == "GET":
            status = await session_svc.get_session_live_status(session_id)
            return {"logs": status.get("logs", []), "status": status}

    m = _match(r"^/sessions/([^/]+)/stop$", path)
    if m:
        session_id = m.group(1)
        if method == "POST":
            model = await session_svc.stop_session(session, session_id)
            return _to_dict(model, SessionResponse)

    m = _match(r"^/sessions/([^/]+)/state$", path)
    if m:
        session_id = m.group(1)
        if method == "PUT":
            model = await session_svc.update_session_state(
                session, session_id, state=data["state"]
            )
            return _to_dict(model, SessionResponse)

    m = _match(r"^/sessions/([^/]+)$", path)
    if m:
        session_id = m.group(1)
        if method == "GET":
            model = await session_svc.get_session(session, session_id)
            return _to_dict(model, SessionResponse)

    # ── Tasks ──────────────────────────────────────────────────
    if path == "/tasks":
        if method == "GET":
            models = await task_svc.list_tasks(
                session, agent_id=params.get("agent_id")
            )
            return _to_list(models, TaskResponse)
        if method == "POST":
            model = await task_svc.create_task(
                session,
                instruction=data["instruction"],
                agent_id=data["agent_id"],
                definition_of_done=data.get("definition_of_done"),
            )
            return _to_dict(model, TaskResponse)

    m = _match(r"^/tasks/([^/]+)$", path)
    if m:
        task_id = m.group(1)
        if method == "GET":
            model = await task_svc.get_task(session, task_id)
            return _to_dict(model, TaskResponse)

    # ── Skills ─────────────────────────────────────────────────
    if path == "/skills":
        if method == "GET":
            models = await skill_svc.list_skills(session)
            return _to_list(models, SkillResponse)
        if method == "POST":
            model = await skill_svc.create_skill(
                session,
                name=data["name"],
                description=data.get("description"),
                skills_md=data.get("skills_md"),
                references_path=data.get("references_path"),
            )
            return _to_dict(model, SkillResponse)

    m = _match(r"^/skills/([^/]+)$", path)
    if m:
        skill_id = m.group(1)
        if method == "GET":
            model = await skill_svc.get_skill(session, skill_id)
            return _to_dict(model, SkillResponse)
        if method == "PUT":
            model = await skill_svc.update_skill(
                session,
                skill_id,
                name=data.get("name"),
                description=data.get("description"),
                skills_md=data.get("skills_md"),
                references_path=data.get("references_path"),
            )
            return _to_dict(model, SkillResponse)
        if method == "DELETE":
            await skill_svc.delete_skill(session, skill_id)
            return None

    raise ValueError(f"No local route for {method} {path}")


def local_request(method: str, path: str, data: dict | None = None, params: dict | None = None) -> Any:
    """Execute a local request synchronously by calling service layer directly."""
    try:
        return asyncio.run(_execute(method, path, data, params))
    except ServiceError as e:
        print(f"Error ({e.status_code}): {e.message}", file=sys.stderr)
        sys.exit(1)
