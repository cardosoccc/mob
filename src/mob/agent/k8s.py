"""Kubernetes helpers for agent self-annotation."""

import asyncio
import logging
import os

logger = logging.getLogger(__name__)

_core_api = None


def _get_pod_identity() -> tuple[str, str]:
    """Return (pod_name, namespace) from Downward API env vars."""
    pod_name = os.environ.get("AGENT_POD_NAME")
    namespace = os.environ.get("AGENT_NAMESPACE")
    if not pod_name or not namespace:
        raise RuntimeError(
            "AGENT_POD_NAME and AGENT_NAMESPACE env vars are required "
            "(injected via Kubernetes Downward API)"
        )
    return pod_name, namespace


def _get_core_api():
    """Get a cached CoreV1Api client."""
    global _core_api
    if _core_api is not None:
        return _core_api

    from kubernetes import client as k8s_client, config as k8s_config

    try:
        k8s_config.load_incluster_config()
    except k8s_config.ConfigException:
        k8s_config.load_kube_config()

    _core_api = k8s_client.CoreV1Api()
    return _core_api


def patch_own_annotation(state: str) -> None:
    """Patch this pod's mob.io/agent-state annotation (synchronous)."""
    pod_name, namespace = _get_pod_identity()
    v1 = _get_core_api()
    body = {"metadata": {"annotations": {"mob.io/agent-state": state}}}

    try:
        v1.patch_namespaced_pod(name=pod_name, namespace=namespace, body=body)
        logger.info("Patched pod annotation mob.io/agent-state=%s", state)
    except Exception:
        logger.exception("Failed to patch pod annotation to %s", state)
        raise


async def patch_own_annotation_async(state: str) -> None:
    """Patch this pod's mob.io/agent-state annotation (non-blocking)."""
    await asyncio.to_thread(patch_own_annotation, state)
