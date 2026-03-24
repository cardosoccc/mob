"""Kubernetes helpers for agent self-annotation."""

import logging
import os

logger = logging.getLogger(__name__)


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


def patch_own_annotation(state: str) -> None:
    """Patch this pod's mob.io/agent-state annotation.

    Uses the in-cluster Kubernetes client to PATCH the pod's metadata.
    """
    from kubernetes import client as k8s_client, config as k8s_config

    pod_name, namespace = _get_pod_identity()

    try:
        k8s_config.load_incluster_config()
    except k8s_config.ConfigException:
        k8s_config.load_kube_config()

    v1 = k8s_client.CoreV1Api()
    body = {"metadata": {"annotations": {"mob.io/agent-state": state}}}

    try:
        v1.patch_namespaced_pod(name=pod_name, namespace=namespace, body=body)
        logger.info(f"Patched pod annotation mob.io/agent-state={state}")
    except Exception:
        logger.exception(f"Failed to patch pod annotation to {state}")
        raise
