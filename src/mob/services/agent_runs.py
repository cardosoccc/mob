"""AgentRun service."""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mob.config import get_settings
from mob.models.agent import Agent
from mob.models.agent_run import AgentRun, AgentRunState
from mob.services import ServiceError

logger = logging.getLogger(__name__)

# Valid state transitions enforced by the service layer
VALID_TRANSITIONS: dict[AgentRunState, set[AgentRunState]] = {
    AgentRunState.PENDING: {AgentRunState.STARTING, AgentRunState.FAILED},
    AgentRunState.STARTING: {AgentRunState.IDLE, AgentRunState.FAILED},
    AgentRunState.IDLE: {AgentRunState.BUSY, AgentRunState.FINISHED, AgentRunState.FAILED},
    AgentRunState.BUSY: {AgentRunState.IDLE, AgentRunState.FINISHED, AgentRunState.FAILED},
    AgentRunState.FINISHED: set(),
    AgentRunState.FAILED: set(),
}


def _try_get_k8s_custom_api():
    """Try to get a Kubernetes CustomObjectsApi client. Returns None if unavailable."""
    try:
        from kubernetes import client as k8s_client, config as k8s_config
        try:
            k8s_config.load_incluster_config()
        except k8s_config.ConfigException:
            k8s_config.load_kube_config()
        return k8s_client.CustomObjectsApi()
    except Exception:
        return None


async def list_agent_runs(
    session: AsyncSession, agent_id: str | None = None
) -> list[AgentRun]:
    query = select(AgentRun).order_by(AgentRun.created_at.desc())
    if agent_id:
        query = query.where(AgentRun.agent_id == agent_id)
    result = await session.execute(query)
    return list(result.scalars().all())


async def create_agent_run(
    session: AsyncSession, agent_id: str, task_id: str | None = None
) -> AgentRun:
    agent = await session.get(Agent, agent_id)
    if not agent:
        raise ServiceError("Agent not found", 404)

    run = AgentRun(
        agent_id=agent_id,
        state=AgentRunState.PENDING,
        task_id=task_id,
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)

    # Try to create an AgentRun CR in Kubernetes
    custom_api = _try_get_k8s_custom_api()
    if custom_api:
        try:
            cr = {
                "apiVersion": "mob.io/v1",
                "kind": "AgentRun",
                "metadata": {
                    "name": f"ar-{str(run.id)[:8]}",
                    "namespace": get_settings().kubernetes_namespace,
                },
                "spec": {
                    "agentId": str(agent.id),
                    "agentName": agent.name,
                    "agentTemplate": agent.agent_template,
                    "systemPrompt": agent.system_prompt,
                    "modelEndpoint": agent.model_endpoint,
                    "taskId": str(task_id) if task_id else None,
                },
            }
            custom_api.create_namespaced_custom_object(
                group="mob.io",
                version="v1",
                namespace=get_settings().kubernetes_namespace,
                plural="agentruns",
                body=cr,
            )
            logger.info(f"Created AgentRun CR ar-{str(run.id)[:8]}")
        except Exception as e:
            logger.warning(f"Failed to create AgentRun CR: {e}")
            run.error_message = f"CR creation failed: {e}"
            await session.commit()
            await session.refresh(run)

    return run


async def get_agent_run(session: AsyncSession, run_id: str) -> AgentRun:
    run = await session.get(AgentRun, run_id)
    if not run:
        raise ServiceError("Agent run not found", 404)
    return run


async def get_agent_run_live_status(run_id: str) -> dict:
    """Read live status from the AgentRun CR (not the DB)."""
    custom_api = _try_get_k8s_custom_api()
    if not custom_api:
        return {}
    try:
        cr = custom_api.get_namespaced_custom_object(
            group="mob.io",
            version="v1",
            namespace=get_settings().kubernetes_namespace,
            plural="agentruns",
            name=f"ar-{run_id[:8]}",
        )
        return cr.get("status", {})
    except Exception:
        return {}


async def stop_agent_run(session: AsyncSession, run_id: str) -> AgentRun:
    run = await session.get(AgentRun, run_id)
    if not run:
        raise ServiceError("Agent run not found", 404)

    if run.state in (AgentRunState.FINISHED, AgentRunState.FAILED):
        raise ServiceError(
            f"Agent run is already in terminal state: {run.state}", 400
        )

    # Delete the CR — operator's finalizer will clean up the pod
    custom_api = _try_get_k8s_custom_api()
    if custom_api:
        try:
            custom_api.delete_namespaced_custom_object(
                group="mob.io",
                version="v1",
                namespace=get_settings().kubernetes_namespace,
                plural="agentruns",
                name=f"ar-{str(run.id)[:8]}",
            )
            logger.info(f"Deleted AgentRun CR ar-{str(run.id)[:8]}")
        except Exception as e:
            logger.warning(f"Failed to delete AgentRun CR: {e}")

    run.state = AgentRunState.FAILED
    run.error_message = "Stopped by user"
    await session.commit()
    await session.refresh(run)
    return run


async def update_agent_run_state(
    session: AsyncSession, run_id: str, state: str
) -> AgentRun:
    run = await session.get(AgentRun, run_id)
    if not run:
        raise ServiceError("Agent run not found", 404)

    try:
        new_state = AgentRunState(state)
    except ValueError:
        raise ServiceError(f"Invalid state: {state}", 400)

    # Enforce state transition guards
    allowed = VALID_TRANSITIONS.get(run.state, set())
    if new_state not in allowed:
        raise ServiceError(
            f"Invalid state transition: {run.state.value} -> {new_state.value}", 409
        )

    run.state = new_state
    await session.commit()
    await session.refresh(run)
    return run
