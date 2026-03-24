"""AgentRun service."""

import logging
import secrets

import httpx
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
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
    session: AsyncSession,
    agent_id: str | None = None,
    state: str | None = None,
) -> list[AgentRun]:
    query = select(AgentRun).order_by(AgentRun.created_at.desc())
    if agent_id:
        query = query.where(AgentRun.agent_id == agent_id)
    if state:
        try:
            query = query.where(AgentRun.state == AgentRunState(state))
        except ValueError:
            raise ServiceError(f"Invalid state filter: {state}", 400)
    result = await session.execute(query)
    return list(result.scalars().all())


async def create_agent_run(
    session: AsyncSession,
    agent_id: str,
    task_id: str | None = None,
    name: str | None = None,
) -> AgentRun:
    agent = await session.get(Agent, agent_id)
    if not agent:
        raise ServiceError("Agent not found", 404)

    if not name:
        suffix = secrets.token_hex(4)  # 8 hex chars
        name = f"{agent.name}-{suffix}"

    run = AgentRun(
        agent_id=agent_id,
        name=name,
        state=AgentRunState.PENDING,
        task_id=task_id,
    )
    session.add(run)
    try:
        await session.flush()
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise ServiceError(f"Run name '{name}' already exists", 409)
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


def _try_get_k8s_core_api():
    """Try to get a Kubernetes CoreV1Api client. Returns None if unavailable."""
    try:
        from kubernetes import client as k8s_client, config as k8s_config
        try:
            k8s_config.load_incluster_config()
        except k8s_config.ConfigException:
            k8s_config.load_kube_config()
        return k8s_client.CoreV1Api()
    except Exception:
        return None


def _get_pod_ip(pod_name: str) -> str:
    """Look up the cluster IP of a pod by name."""
    core_api = _try_get_k8s_core_api()
    if not core_api:
        raise ServiceError("Kubernetes is not available", 503)
    try:
        pod = core_api.read_namespaced_pod(
            name=pod_name,
            namespace=get_settings().kubernetes_namespace,
        )
    except Exception:
        raise ServiceError(f"Pod {pod_name} not found", 502)

    pod_ip = pod.status.pod_ip if pod.status else None
    if not pod_ip:
        raise ServiceError(f"Pod {pod_name} has no IP assigned", 502)
    return pod_ip


async def send_message(
    session: AsyncSession, run_id: str, message: str
) -> dict:
    run = await session.get(AgentRun, run_id)
    if not run:
        raise ServiceError("Agent run not found", 404)

    # Check live CR status to verify agent is running
    live_status = await get_agent_run_live_status(str(run.id))
    cr_state = live_status.get("state", "")
    if cr_state not in ("Idle", "Busy"):
        raise ServiceError(
            f"Agent is not running (state: {cr_state or 'unknown'})", 409
        )

    # Get pod name from CR status
    pod_name = live_status.get("podName")
    if not pod_name:
        raise ServiceError("Agent pod name not available", 502)

    # Get pod IP and forward the message
    pod_ip = _get_pod_ip(pod_name)

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(connect=5.0, read=120.0, write=5.0, pool=5.0)
        ) as client:
            resp = await client.post(
                f"http://{pod_ip}:8081/message",
                json={"message": message},
            )
    except httpx.ConnectError:
        raise ServiceError("Agent is unreachable", 502)
    except httpx.TimeoutException:
        raise ServiceError("Agent request timed out", 504)

    if resp.status_code == 409:
        raise ServiceError("Agent is busy", 409)

    if resp.status_code != 200:
        raise ServiceError(f"Agent returned error: {resp.text}", 502)

    return resp.json()
