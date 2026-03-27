"""Session service."""

import asyncio
import json
import logging
import secrets
import socket

import httpx
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from mob.config import get_settings, is_local_mode
from mob.models.agent import Agent
from mob.models.session import Session, SessionState
from mob.services import ServiceError

logger = logging.getLogger(__name__)

# Valid state transitions enforced by the service layer
VALID_TRANSITIONS: dict[SessionState, set[SessionState]] = {
    SessionState.PENDING: {SessionState.STARTING, SessionState.FAILED},
    SessionState.STARTING: {SessionState.IDLE, SessionState.FAILED},
    SessionState.IDLE: {SessionState.BUSY, SessionState.FINISHED, SessionState.FAILED},
    SessionState.BUSY: {SessionState.IDLE, SessionState.FINISHED, SessionState.FAILED},
    SessionState.FINISHED: set(),
    SessionState.FAILED: set(),
}

# CR status uses title-case; DB uses lowercase enum values
CR_STATE_TO_DB_STATE: dict[str, SessionState] = {
    "Pending": SessionState.PENDING,
    "Starting": SessionState.STARTING,
    "Idle": SessionState.IDLE,
    "Busy": SessionState.BUSY,
    "Finished": SessionState.FINISHED,
    "Failed": SessionState.FAILED,
}

TERMINAL_STATES = {SessionState.FINISHED, SessionState.FAILED}

# Cached K8s API clients (initialized on first use)
_k8s_custom_api = None
_k8s_core_api = None
_k8s_config_loaded = False

# Reusable HTTP client for agent pod communication
_http_client: httpx.AsyncClient | None = None

AGENT_HTTP_PORT = 8081


def _load_k8s_config():
    """Load K8s config once (in-cluster or kubeconfig)."""
    global _k8s_config_loaded
    if _k8s_config_loaded:
        return
    from kubernetes import config as k8s_config
    try:
        k8s_config.load_incluster_config()
    except k8s_config.ConfigException:
        k8s_config.load_kube_config()
    _k8s_config_loaded = True


def _try_get_k8s_custom_api():
    """Try to get a cached Kubernetes CustomObjectsApi client. Returns None if unavailable."""
    global _k8s_custom_api
    if _k8s_custom_api is not None:
        return _k8s_custom_api
    try:
        from kubernetes import client as k8s_client
        _load_k8s_config()
        _k8s_custom_api = k8s_client.CustomObjectsApi()
        return _k8s_custom_api
    except Exception:
        return None


def _list_cr_statuses_sync() -> dict[str, dict] | None:
    """Batch-list all Session CR statuses. Returns {cr_name: status_dict}, or None if K8s unavailable."""
    custom_api = _try_get_k8s_custom_api()
    if not custom_api:
        return None
    try:
        result = custom_api.list_namespaced_custom_object(
            group="mob.io",
            version="v1",
            namespace=get_settings().kubernetes_namespace,
            plural="sessions",
        )
        return {
            item["metadata"]["name"]: item.get("status", {})
            for item in result.get("items", [])
        }
    except Exception:
        return None


def _enrich_sessions_with_live_state(
    sessions: list[Session], cr_statuses: dict[str, dict] | None
) -> list[Session]:
    """Merge live CR state into Session objects for non-terminal sessions.

    If cr_statuses is None (K8s unavailable), returns sessions unchanged (graceful degradation).
    """
    if cr_statuses is None:
        return sessions
    for sess in sessions:
        if sess.state in TERMINAL_STATES:
            continue
        cr_name = f"s-{str(sess.id)[:8]}"
        status = cr_statuses.get(cr_name)
        if status:
            cr_state = status.get("state", "")
            db_state = CR_STATE_TO_DB_STATE.get(cr_state)
            if db_state:
                sess.state = db_state
            pod_name = status.get("podName")
            if pod_name:
                sess.pod_name = pod_name
            error_msg = status.get("errorMessage")
            if error_msg:
                sess.error_message = error_msg
        else:
            # CR not found for a non-terminal session — mark as failed
            sess.state = SessionState.FAILED
            sess.error_message = "CR not found"
    return sessions


async def list_sessions(
    session: AsyncSession,
    agent_id: str | None = None,
    state: str | None = None,
) -> list[Session]:
    # Validate state filter early
    state_filter: SessionState | None = None
    if state:
        try:
            state_filter = SessionState(state)
        except ValueError:
            raise ServiceError(f"Invalid state filter: {state}", 400)

    query = select(Session).order_by(Session.created_at.desc())
    if agent_id:
        query = query.where(Session.agent_id == agent_id)

    result = await session.execute(query)
    sessions = list(result.scalars().all())

    # Enrich with live K8s state
    cr_statuses = await asyncio.to_thread(_list_cr_statuses_sync)
    _enrich_sessions_with_live_state(sessions, cr_statuses)

    # Apply state filter post-enrichment
    if state_filter:
        sessions = [s for s in sessions if s.state == state_filter]

    return sessions


def _build_env_vars(agent: "Agent", env_overrides: dict[str, str] | None = None) -> dict[str, str] | None:
    """Merge agent env_defaults + custom_config (prefixed) + runtime overrides."""
    merged: dict[str, str] = {}

    # Layer 1: agent env_defaults
    if agent.env_defaults:
        defaults = json.loads(agent.env_defaults) if isinstance(agent.env_defaults, str) else agent.env_defaults
        for k, v in defaults.items():
            if v:  # skip empty-value (required-at-runtime) entries unless overridden
                merged[k] = v

    # Layer 2: agent custom_config with AGENT_CUSTOM_ prefix
    if agent.custom_config:
        custom = json.loads(agent.custom_config) if isinstance(agent.custom_config, str) else agent.custom_config
        for k, v in custom.items():
            merged[f"AGENT_CUSTOM_{k.upper()}"] = str(v)

    # Layer 3: runtime overrides (highest priority)
    if env_overrides:
        merged.update(env_overrides)

    return merged if merged else None


async def create_session(
    session: AsyncSession,
    agent_id: str,
    task_id: str | None = None,
    name: str | None = None,
    env_overrides: dict[str, str] | None = None,
) -> Session:
    agent = await session.get(Agent, agent_id)
    if not agent:
        raise ServiceError("Agent not found", 404)

    if not name:
        suffix = secrets.token_hex(4)  # 8 hex chars
        name = f"{agent.name}-{suffix}"

    sess = Session(
        agent_id=agent_id,
        name=name,
        state=SessionState.PENDING,
        task_id=task_id,
    )
    session.add(sess)
    try:
        await session.flush()
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise ServiceError(f"Session name '{name}' already exists", 409)
    await session.refresh(sess)

    # Create skills ConfigMap if agent has skills
    skills_configmap_name = None
    from sqlalchemy.orm import selectinload
    agent_with_skills = await session.execute(
        select(Agent).options(selectinload(Agent.skills)).where(Agent.id == agent_id)
    )
    agent_obj = agent_with_skills.scalar_one()
    if agent_obj.skills:
        from mob.models.skill import Skill
        skill_ids = [ask.skill_id for ask in agent_obj.skills]
        skills_result = await session.execute(
            select(Skill).where(Skill.id.in_(skill_ids))
        )
        skill_models = list(skills_result.scalars().all())

        if skill_models:
            skills_configmap_name = f"mob-skills-{name}"
            configmap_data = {}
            for sk in skill_models:
                # Key is skill-name.md, value is the SKILL.md content
                md_content = f"---\nname: {sk.name}\ndescription: {sk.description}\n---\n"
                if sk.skill_md:
                    md_content += sk.skill_md
                configmap_data[f"{sk.name}.md"] = md_content

            # Create the ConfigMap via K8s API
            try:
                from kubernetes import client as k8s_client
                _load_k8s_config()
                core_api = k8s_client.CoreV1Api()
                cm = k8s_client.V1ConfigMap(
                    metadata=k8s_client.V1ObjectMeta(
                        name=skills_configmap_name,
                        namespace=get_settings().kubernetes_namespace,
                    ),
                    data=configmap_data,
                )
                core_api.create_namespaced_config_map(
                    namespace=get_settings().kubernetes_namespace,
                    body=cm,
                )
                logger.info(f"Created skills ConfigMap {skills_configmap_name}")
            except Exception as e:
                logger.warning(f"Failed to create skills ConfigMap: {e}")
                skills_configmap_name = None

    # Resolve template resource limits
    resource_cpu_limit = None
    resource_memory_limit = None
    from mob.models.template import Template
    result = await session.execute(
        select(Template).where(Template.image == agent.agent_template)
    )
    tmpl = result.scalar_one_or_none()
    if tmpl:
        resource_cpu_limit = tmpl.resource_cpu_limit
        resource_memory_limit = tmpl.resource_memory_limit

    # Try to create a Session CR in Kubernetes
    custom_api = _try_get_k8s_custom_api()
    if custom_api:
        try:
            cr = {
                "apiVersion": "mob.io/v1",
                "kind": "Session",
                "metadata": {
                    "name": f"s-{str(sess.id)[:8]}",
                    "namespace": get_settings().kubernetes_namespace,
                },
                "spec": {
                    "agentId": str(agent.id),
                    "agentName": agent.name,
                    "agentTemplate": agent.agent_template,
                    "systemPrompt": agent.system_prompt,
                    "modelEndpoint": agent.model_endpoint,
                    "taskId": str(task_id) if task_id else None,
                    "envVars": _build_env_vars(agent, env_overrides),
                    "skillsConfigmap": skills_configmap_name,
                },
            }
            if resource_cpu_limit:
                cr["spec"]["resourceCpuLimit"] = resource_cpu_limit
            if resource_memory_limit:
                cr["spec"]["resourceMemoryLimit"] = resource_memory_limit
            custom_api.create_namespaced_custom_object(
                group="mob.io",
                version="v1",
                namespace=get_settings().kubernetes_namespace,
                plural="sessions",
                body=cr,
            )
            logger.info(f"Created Session CR s-{str(sess.id)[:8]}")
        except Exception as e:
            logger.warning(f"Failed to create Session CR: {e}")
            sess.error_message = f"CR creation failed: {e}"
            await session.commit()
            await session.refresh(sess)

    return sess


async def get_session(session: AsyncSession, session_id: str) -> Session:
    sess = await session.get(Session, session_id)
    if not sess:
        raise ServiceError("Session not found", 404)

    # Enrich non-terminal sessions with live K8s state
    if sess.state not in TERMINAL_STATES:
        result = await asyncio.to_thread(
            _get_single_cr_status_sync, str(sess.id)
        )
        if result is None:
            pass  # K8s unavailable — degrade gracefully, keep DB state
        elif result is _CR_NOT_FOUND:
            sess.state = SessionState.FAILED
            sess.error_message = "CR not found"
        elif result:
            cr_state = result.get("state", "")
            db_state = CR_STATE_TO_DB_STATE.get(cr_state)
            if db_state:
                sess.state = db_state
            pod_name = result.get("podName")
            if pod_name:
                sess.pod_name = pod_name
            error_msg = result.get("errorMessage")
            if error_msg:
                sess.error_message = error_msg

    return sess


_CR_NOT_FOUND = object()


def _get_single_cr_status_sync(session_id: str) -> dict | object | None:
    """Read live status for a single Session CR.

    Returns:
        dict: CR status (may be empty if status not yet set)
        _CR_NOT_FOUND: K8s available but CR doesn't exist
        None: K8s unavailable
    """
    custom_api = _try_get_k8s_custom_api()
    if not custom_api:
        return None
    try:
        cr = custom_api.get_namespaced_custom_object(
            group="mob.io",
            version="v1",
            namespace=get_settings().kubernetes_namespace,
            plural="sessions",
            name=f"s-{session_id[:8]}",
        )
        return cr.get("status", {})
    except Exception:
        return _CR_NOT_FOUND


def get_session_live_status_sync(session_id: str) -> dict:
    """Read live status from the Session CR (synchronous, not the DB)."""
    custom_api = _try_get_k8s_custom_api()
    if not custom_api:
        return {}
    try:
        cr = custom_api.get_namespaced_custom_object(
            group="mob.io",
            version="v1",
            namespace=get_settings().kubernetes_namespace,
            plural="sessions",
            name=f"s-{session_id[:8]}",
        )
        return cr.get("status", {})
    except Exception:
        return {}


async def get_session_live_status(session_id: str) -> dict:
    """Read live status from the Session CR (not the DB)."""
    return await asyncio.to_thread(get_session_live_status_sync, session_id)


async def stop_session(session: AsyncSession, session_id: str) -> Session:
    sess = await session.get(Session, session_id)
    if not sess:
        raise ServiceError("Session not found", 404)

    if sess.state in (SessionState.FINISHED, SessionState.FAILED):
        raise ServiceError(
            f"Session is already in terminal state: {sess.state}", 400
        )

    # Delete the CR — operator's finalizer will clean up the pod
    custom_api = _try_get_k8s_custom_api()
    if custom_api:
        try:
            custom_api.delete_namespaced_custom_object(
                group="mob.io",
                version="v1",
                namespace=get_settings().kubernetes_namespace,
                plural="sessions",
                name=f"s-{str(sess.id)[:8]}",
            )
            logger.info(f"Deleted Session CR s-{str(sess.id)[:8]}")
        except Exception as e:
            logger.warning(f"Failed to delete Session CR: {e}")

    sess.state = SessionState.FAILED
    sess.error_message = "Stopped by user"
    await session.commit()
    await session.refresh(sess)
    return sess


async def update_session_state(
    session: AsyncSession, session_id: str, state: str
) -> Session:
    sess = await session.get(Session, session_id)
    if not sess:
        raise ServiceError("Session not found", 404)

    try:
        new_state = SessionState(state)
    except ValueError:
        raise ServiceError(f"Invalid state: {state}", 400)

    # Enforce state transition guards
    allowed = VALID_TRANSITIONS.get(sess.state, set())
    if new_state not in allowed:
        raise ServiceError(
            f"Invalid state transition: {sess.state.value} -> {new_state.value}", 409
        )

    sess.state = new_state
    await session.commit()
    await session.refresh(sess)
    return sess


def _try_get_k8s_core_api():
    """Try to get a cached Kubernetes CoreV1Api client. Returns None if unavailable."""
    global _k8s_core_api
    if _k8s_core_api is not None:
        return _k8s_core_api
    try:
        from kubernetes import client as k8s_client
        _load_k8s_config()
        _k8s_core_api = k8s_client.CoreV1Api()
        return _k8s_core_api
    except Exception:
        return None


def _get_pod_ip_sync(pod_name: str) -> str:
    """Look up the cluster IP of a pod by name (synchronous)."""
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


def _get_http_client() -> httpx.AsyncClient:
    """Get a reusable HTTP client for agent pod communication."""
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=5.0, read=120.0, write=5.0, pool=5.0)
        )
    return _http_client


def _get_free_port() -> int:
    """Find an available local port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


async def _send_via_port_forward(
    pod_name: str, message: str, headers: dict
) -> dict:
    """Send a message to an agent pod via kubectl port-forward (for local mode)."""
    settings = get_settings()
    local_port = _get_free_port()

    # Start port-forward as a background subprocess
    pf_proc = await asyncio.create_subprocess_exec(
        "kubectl", "port-forward",
        f"pod/{pod_name}", f"{local_port}:{AGENT_HTTP_PORT}",
        "-n", settings.kubernetes_namespace,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        # Wait briefly for port-forward to establish
        await asyncio.sleep(1)

        if pf_proc.returncode is not None:
            stderr = await pf_proc.stderr.read()
            raise ServiceError(
                f"Port-forward failed: {stderr.decode().strip()}", 502
            )

        # Send message through the tunnel
        client = _get_http_client()
        try:
            resp = await client.post(
                f"http://127.0.0.1:{local_port}/message",
                json={"message": message},
                headers=headers,
            )
        except httpx.ConnectError:
            raise ServiceError("Agent is unreachable via port-forward", 502)
        except httpx.TimeoutException:
            raise ServiceError("Agent request timed out", 504)

        if resp.status_code == 409:
            data = resp.json()
            raise ServiceError(data.get("error", "Agent is busy"), 409)
        if resp.status_code == 401:
            raise ServiceError("Agent authentication failed", 502)
        if resp.status_code != 200:
            raise ServiceError("Agent returned an error", 502)

        return resp.json()

    finally:
        pf_proc.terminate()
        await pf_proc.wait()


async def send_message(
    session: AsyncSession, session_id: str, message: str
) -> dict:
    sess = await session.get(Session, session_id)
    if not sess:
        raise ServiceError("Session not found", 404)

    # Check live CR status to verify agent is running
    live_status = await get_session_live_status(str(sess.id))
    cr_state = live_status.get("state", "")
    if cr_state not in ("Idle", "Busy"):
        raise ServiceError(
            f"Agent is not running (state: {cr_state or 'unknown'})", 409
        )

    # Get pod name from CR status
    pod_name = live_status.get("podName")
    if not pod_name:
        raise ServiceError("Agent pod name not available", 502)

    # Build auth headers
    headers = {}
    auth_token = getattr(get_settings(), "agent_auth_token", None)
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    # Route based on mode: local uses port-forward, dev/remote uses pod IP directly
    if is_local_mode():
        return await _send_via_port_forward(pod_name, message, headers)

    # Dev/remote mode: direct pod IP access
    pod_ip = await asyncio.to_thread(_get_pod_ip_sync, pod_name)

    try:
        client = _get_http_client()
        resp = await client.post(
            f"http://{pod_ip}:{AGENT_HTTP_PORT}/message",
            json={"message": message},
            headers=headers,
        )
    except httpx.ConnectError:
        raise ServiceError("Agent is unreachable", 502)
    except httpx.TimeoutException:
        raise ServiceError("Agent request timed out", 504)

    if resp.status_code == 409:
        data = resp.json()
        raise ServiceError(data.get("error", "Agent is busy"), 409)

    if resp.status_code == 401:
        raise ServiceError("Agent authentication failed", 502)

    if resp.status_code != 200:
        raise ServiceError("Agent returned an error", 502)

    return resp.json()
