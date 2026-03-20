"""Kubernetes manager for agent runs."""

import logging
from typing import Any

from mob.config import get_settings

logger = logging.getLogger(__name__)


class K8sManager:
    """Manages Kubernetes resources for agent runs."""

    def __init__(self, namespace: str | None = None, kubeconfig: str | None = None):
        self.namespace = namespace or get_settings().kubernetes_namespace
        self.kubeconfig = kubeconfig or get_settings().kubeconfig
        self._client = None
        self._core_v1 = None

    def _ensure_client(self):
        if self._client is not None:
            return
        try:
            from kubernetes import client, config

            if self.kubeconfig:
                config.load_kube_config(config_file=self.kubeconfig)
            else:
                try:
                    config.load_incluster_config()
                except config.ConfigException:
                    config.load_kube_config()
            self._client = client
            self._core_v1 = client.CoreV1Api()
        except Exception as e:
            logger.warning(f"Failed to initialize Kubernetes client: {e}")
            raise

    def create_agent_pod(
        self,
        run_id: str,
        agent_name: str,
        image: str,
        system_prompt: str | None = None,
        model_endpoint: str | None = None,
        env_vars: dict[str, str] | None = None,
    ) -> str:
        """Create a pod for an agent run. Returns the pod name."""
        self._ensure_client()

        pod_name = f"mob-agent-{run_id[:8]}"
        env = []

        if system_prompt:
            env.append(self._client.V1EnvVar(name="AGENT_SYSTEM_PROMPT", value=system_prompt))
        if model_endpoint:
            env.append(self._client.V1EnvVar(name="MODEL_ENDPOINT", value=model_endpoint))
        env.append(self._client.V1EnvVar(name="AGENT_RUN_ID", value=run_id))
        env.append(self._client.V1EnvVar(name="AGENT_NAME", value=agent_name))

        if env_vars:
            for k, v in env_vars.items():
                env.append(self._client.V1EnvVar(name=k, value=v))

        pod = self._client.V1Pod(
            metadata=self._client.V1ObjectMeta(
                name=pod_name,
                namespace=self.namespace,
                labels={
                    "app": "mob-agent",
                    "mob.io/agent-run": run_id,
                    "mob.io/agent-name": agent_name,
                },
            ),
            spec=self._client.V1PodSpec(
                containers=[
                    self._client.V1Container(
                        name="agent",
                        image=image,
                        env=env,
                        resources=self._client.V1ResourceRequirements(
                            requests={"cpu": "100m", "memory": "256Mi"},
                            limits={"cpu": "1000m", "memory": "1Gi"},
                        ),
                    )
                ],
                restart_policy="Never",
            ),
        )

        self._core_v1.create_namespaced_pod(namespace=self.namespace, body=pod)
        logger.info(f"Created pod {pod_name} for agent run {run_id}")
        return pod_name

    def delete_agent_pod(self, pod_name: str) -> None:
        """Delete an agent pod."""
        self._ensure_client()
        try:
            self._core_v1.delete_namespaced_pod(
                name=pod_name,
                namespace=self.namespace,
            )
            logger.info(f"Deleted pod {pod_name}")
        except Exception as e:
            logger.warning(f"Failed to delete pod {pod_name}: {e}")

    def get_pod_status(self, pod_name: str) -> dict[str, Any]:
        """Get the status of an agent pod."""
        self._ensure_client()
        pod = self._core_v1.read_namespaced_pod(name=pod_name, namespace=self.namespace)
        return {
            "name": pod.metadata.name,
            "phase": pod.status.phase,
            "conditions": [
                {"type": c.type, "status": c.status}
                for c in (pod.status.conditions or [])
            ],
        }

    def get_pod_logs(self, pod_name: str, tail_lines: int = 100) -> str:
        """Get logs from an agent pod."""
        self._ensure_client()
        return self._core_v1.read_namespaced_pod_log(
            name=pod_name,
            namespace=self.namespace,
            tail_lines=tail_lines,
        )

    def exec_in_pod(self, pod_name: str, command: list[str]) -> str:
        """Execute a command in an agent pod."""
        self._ensure_client()
        from kubernetes.stream import stream

        resp = stream(
            self._core_v1.connect_get_namespaced_pod_exec,
            pod_name,
            self.namespace,
            command=command,
            stderr=True,
            stdin=False,
            stdout=True,
            tty=False,
        )
        return resp
