---
title: "feat: Add LiteLLM proxy server as a mob infrastructure component"
type: feat
status: completed
date: 2026-03-30
---

# feat: Add LiteLLM proxy server as a mob infrastructure component

## Overview

Add LiteLLM proxy as a first-class Kubernetes component in mob. The proxy centralizes LLM provider access — agent pods call the proxy instead of calling providers directly. Model endpoints using the `litellm:<model-id>` prefix route through the in-cluster proxy. Supported in dev, staging, and production modes. Not supported in local mode.

## Problem Statement / Motivation

Currently, each agent pod connects directly to LLM providers (Anthropic, OpenAI, etc.) using API keys injected via `mob-agent-secrets`. This creates several issues:

1. **Key sprawl**: Every agent pod has access to all provider API keys, increasing blast radius if a pod is compromised
2. **No centralized routing**: No way to load-balance, set fallbacks, or alias models across agents
3. **No observability**: No single point to monitor LLM usage, costs, or latency across all agents
4. **No rate limiting**: Individual agents compete for provider rate limits without coordination

A LiteLLM proxy in the cluster solves all of these by acting as the single gateway between agent pods and LLM providers.

## Proposed Solution

Deploy LiteLLM proxy as a Kubernetes Deployment + Service in the `mob` namespace, managed via Kustomize (matching existing patterns). The agent entrypoint detects the `litellm:` prefix in `MODEL_ENDPOINT` and routes through the proxy using pydantic-ai's `OpenAIProvider` with the proxy's base URL.

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  mob namespace (Kubernetes)                                  │
│                                                              │
│  ┌──────────┐   litellm:claude-sonnet   ┌──────────────┐   │
│  │ Agent Pod │ ───────────────────────→  │  LiteLLM     │   │
│  │ (8081)    │   OpenAI-compatible API   │  Proxy (4000)│   │
│  └──────────┘                            └──────┬───────┘   │
│  ┌──────────┐                                   │           │
│  │ Agent Pod │ ─────────────────────────────────→│           │
│  └──────────┘                                   │           │
│                                                  │           │
└──────────────────────────────────────────────────┼───────────┘
                                                   │
                                    ┌──────────────┼──────────────┐
                                    ▼              ▼              ▼
                              Anthropic API   OpenAI API    Azure OpenAI
```

### Key Design Decisions

1. **`litellm:<model-id>` prefix**: Parsed by the agent entrypoint. The `<model-id>` is sent as the `model` parameter to the LiteLLM proxy. It must match a `model_name` in the proxy's `model_list` config.

2. **Docker image only (no PyPI)**: LiteLLM PyPI package is quarantined since March 24, 2026 due to a supply chain attack (versions v1.82.7 and v1.82.8 were compromised). Pin to Docker image `ghcr.io/berriai/litellm:main-v1.82.6` — the last known safe version. Docker images were NOT affected by the attack.

3. **Proxy auth via master key**: The proxy uses `LITELLM_MASTER_KEY` to gate inbound requests. Agent pods receive `LITELLM_API_KEY` via `mob-agent-secrets` to authenticate to the proxy.

4. **Separate secrets**: Provider API keys (ANTHROPIC_API_KEY, OPENAI_API_KEY) live in `mob-litellm-secrets`, mounted only on the LiteLLM pod. Agent pods do NOT get provider keys when using `litellm:` endpoints. For backward compatibility, agents using direct `openai:*` or `anthropic:*` endpoints still use `mob-agent-secrets`.

5. **Not supported in local mode**: LiteLLM Deployment is excluded from `deploy/overlays/local/`. The CLI warns when creating an agent with `litellm:` prefix while in local mode.

6. **Kustomize, not Helm**: Follows the project's existing Kustomize base + overlay pattern.

## Technical Approach

### Phase 1: Kubernetes Manifests (LiteLLM Deployment)

Add LiteLLM resources under `deploy/base/litellm/`:

#### `deploy/base/litellm/deployment.yaml`

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mob-litellm
  namespace: mob
  labels:
    app.kubernetes.io/component: litellm
spec:
  replicas: 1
  selector:
    matchLabels:
      app.kubernetes.io/component: litellm
  template:
    metadata:
      labels:
        app.kubernetes.io/component: litellm
    spec:
      containers:
        - name: litellm
          image: ghcr.io/berriai/litellm:main-v1.82.6
          imagePullPolicy: IfNotPresent
          args: ["--config", "/app/config.yaml", "--port", "4000"]
          ports:
            - containerPort: 4000
              name: http
          envFrom:
            - secretRef:
                name: mob-litellm-secrets
                optional: false
          env:
            - name: LITELLM_MASTER_KEY
              valueFrom:
                secretKeyRef:
                  name: mob-litellm-secrets
                  key: LITELLM_MASTER_KEY
            - name: LITELLM_MODE
              value: "PRODUCTION"
            - name: LITELLM_LOG
              value: "ERROR"
          livenessProbe:
            httpGet:
              path: /health/liveliness
              port: 4000
            initialDelaySeconds: 30
            periodSeconds: 15
            failureThreshold: 3
          readinessProbe:
            httpGet:
              path: /health/readiness
              port: 4000
            initialDelaySeconds: 30
            periodSeconds: 15
            failureThreshold: 3
          resources:
            requests:
              cpu: 250m
              memory: 512Mi
            limits:
              cpu: "2"
              memory: 2Gi
          volumeMounts:
            - name: config
              mountPath: /app/config.yaml
              subPath: litellm_config.yaml
              readOnly: true
      volumes:
        - name: config
          configMap:
            name: mob-litellm-config
```

#### `deploy/base/litellm/service.yaml`

```yaml
apiVersion: v1
kind: Service
metadata:
  name: mob-litellm
  namespace: mob
spec:
  type: ClusterIP
  selector:
    app.kubernetes.io/component: litellm
  ports:
    - port: 4000
      targetPort: 4000
      protocol: TCP
      name: http
```

#### `deploy/base/litellm/configmap.yaml`

Base config with a minimal model_list (overridden per environment):

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: mob-litellm-config
  namespace: mob
data:
  litellm_config.yaml: |
    model_list:
      - model_name: claude-sonnet
        litellm_params:
          model: anthropic/claude-sonnet-4-20250514
          api_key: os.environ/ANTHROPIC_API_KEY

      - model_name: claude-haiku
        litellm_params:
          model: anthropic/claude-haiku-4-5-20251001
          api_key: os.environ/ANTHROPIC_API_KEY

      - model_name: gpt-4o
        litellm_params:
          model: openai/gpt-4o
          api_key: os.environ/OPENAI_API_KEY

    litellm_settings:
      drop_params: true
      num_retries: 2
      request_timeout: 120
      json_logs: true

    general_settings:
      master_key: os.environ/LITELLM_MASTER_KEY
```

#### `deploy/base/litellm/secret.yaml`

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: mob-litellm-secrets
  namespace: mob
type: Opaque
stringData:
  LITELLM_MASTER_KEY: "sk-mob-litellm-change-me"
  ANTHROPIC_API_KEY: ""
  OPENAI_API_KEY: ""
```

#### `deploy/base/litellm/kustomization.yaml`

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - deployment.yaml
  - service.yaml
  - configmap.yaml
  - secret.yaml
```

#### Update `deploy/base/kustomization.yaml`

Add `litellm/` to the resources list:

```yaml
resources:
  # ... existing resources ...
  - litellm/
```

### Phase 2: Environment Overlays

#### Dev overlay — `deploy/overlays/dev/patches/litellm-configmap.yaml`

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: mob-litellm-config
data:
  litellm_config.yaml: |
    model_list:
      - model_name: claude-sonnet
        litellm_params:
          model: anthropic/claude-sonnet-4-20250514
          api_key: os.environ/ANTHROPIC_API_KEY

      - model_name: claude-haiku
        litellm_params:
          model: anthropic/claude-haiku-4-5-20251001
          api_key: os.environ/ANTHROPIC_API_KEY

      - model_name: gpt-4o
        litellm_params:
          model: openai/gpt-4o
          api_key: os.environ/OPENAI_API_KEY

    litellm_settings:
      drop_params: true
      num_retries: 2
      request_timeout: 120
      set_verbose: true
      json_logs: true

    general_settings:
      master_key: os.environ/LITELLM_MASTER_KEY
```

Add to `deploy/overlays/dev/kustomization.yaml`:
```yaml
patches:
  # ... existing patches ...
  - path: patches/litellm-configmap.yaml
  - path: patches/litellm-secret.yaml
```

#### Dev overlay — `deploy/overlays/dev/patches/litellm-secret.yaml`

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: mob-litellm-secrets
stringData:
  LITELLM_MASTER_KEY: "sk-mob-dev-litellm"
  ANTHROPIC_API_KEY: ""
  OPENAI_API_KEY: ""
```

#### Local overlay — exclude LiteLLM

Add a patch to `deploy/overlays/local/` that scales LiteLLM to 0 replicas:

`deploy/overlays/local/patches/litellm-deployment.yaml`:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mob-litellm
spec:
  replicas: 0
```

Add to `deploy/overlays/local/kustomization.yaml`:
```yaml
patches:
  - path: patches/deployment.yaml
  - path: patches/litellm-deployment.yaml
```

#### Staging overlay — `deploy/overlays/staging/patches/litellm-configmap.yaml`

Same structure, different model list or settings as needed.

#### Production overlay

- 2+ replicas for HA
- Stricter resource limits
- `LITELLM_MODE: PRODUCTION`
- Production API keys via real secret management

`deploy/overlays/production/patches/litellm-deployment.yaml`:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mob-litellm
spec:
  replicas: 2
  template:
    spec:
      containers:
        - name: litellm
          resources:
            requests:
              cpu: "1"
              memory: 1Gi
            limits:
              cpu: "4"
              memory: 4Gi
```

### Phase 3: Agent Entrypoint — `litellm:` Prefix Routing

Modify `src/mob/agent/entrypoint.py` to detect `litellm:` prefix and route through the proxy.

#### Current code (`_get_agent()`, line 73):
```python
_ai_agent = Agent(
    MODEL_ENDPOINT,
    instructions=full_prompt,
)
```

#### New code:
```python
LITELLM_BASE_URL = os.environ.get("LITELLM_BASE_URL", "http://mob-litellm:4000/v1")
LITELLM_API_KEY = os.environ.get("LITELLM_API_KEY", "")

def _build_model(endpoint: str):
    """Parse MODEL_ENDPOINT and return a pydantic-ai model, handling litellm: prefix."""
    if endpoint.startswith("litellm:"):
        model_name = endpoint[len("litellm:"):]
        from pydantic_ai.models.openai import OpenAIModel
        from pydantic_ai.providers.openai import OpenAIProvider
        return OpenAIModel(
            model_name,
            provider=OpenAIProvider(
                base_url=LITELLM_BASE_URL,
                api_key=LITELLM_API_KEY,
            ),
        )
    return endpoint  # pass-through for openai:*, anthropic:*, etc.

# In _get_agent():
_ai_agent = Agent(
    _build_model(MODEL_ENDPOINT),
    instructions=full_prompt,
)
```

**Environment variables required:**
- `LITELLM_BASE_URL` — injected via `mob-config` ConfigMap or operator. Default: `http://mob-litellm:4000/v1`
- `LITELLM_API_KEY` — injected via `mob-agent-secrets`. The proxy's master key.

### Phase 4: Operator — Inject LiteLLM URL

Modify `operator/src/resources/pod.rs` to inject `LITELLM_BASE_URL` as an env var in agent pods when the model endpoint starts with `litellm:`.

In `build_agent_pod()`, after the `MODEL_ENDPOINT` injection (line 50-56):

```rust
// Inject LiteLLM proxy URL when model endpoint uses litellm: prefix
if spec.model_endpoint.as_ref().is_some_and(|me| me.starts_with("litellm:")) {
    env.push(EnvVar {
        name: "LITELLM_BASE_URL".into(),
        value: Some("http://mob-litellm:4000/v1".into()),
        ..Default::default()
    });
}
```

Alternatively, inject `LITELLM_BASE_URL` unconditionally from the `mob-config` ConfigMap — this is simpler and allows any agent to switch to LiteLLM without operator changes. The entrypoint only uses it when the prefix is `litellm:`.

**Recommended approach**: Add `LITELLM_BASE_URL` to the `mob-config` ConfigMap and inject it via `envFrom` on agent pods (add a second `envFrom` entry in `pod.rs` for the ConfigMap). This is simpler and follows the existing pattern.

### Phase 5: CLI Warning for Local Mode

In `src/mob/cli/yaml_loader.py` and `src/mob/cli/commands/agent.py`, add a warning when a `litellm:` model endpoint is used while in local mode:

```python
from mob.config import is_local_mode

if model_endpoint and model_endpoint.startswith("litellm:") and is_local_mode():
    click.echo("Warning: litellm: model endpoints are not supported in local mode. "
               "The LiteLLM proxy is only available in dev/staging/production.", err=True)
```

### Phase 6: Makefile Targets

Add LiteLLM-specific targets to the Makefile:

```makefile
LITELLM_IMAGE := ghcr.io/berriai/litellm:main-v1.82.6

## dev-litellm-logs: tail LiteLLM proxy logs
dev-litellm-logs:
	kubectl --context $(KIND_CTX) -n mob logs -f -l app.kubernetes.io/component=litellm

## dev-litellm-restart: restart LiteLLM proxy deployment
dev-litellm-restart:
	kubectl --context $(KIND_CTX) -n mob rollout restart deployment/mob-litellm

## dev-load-litellm: pull and load LiteLLM image into Kind
dev-load-litellm:
	docker pull $(LITELLM_IMAGE)
	kind load docker-image $(LITELLM_IMAGE) --name $(KIND_CLUSTER)
```

The LiteLLM image is pulled from a registry (not built locally), so the target is `dev-load-litellm` rather than `dev-rebuild-litellm`.

### Phase 7: Dev Setup Script Update

Update `scripts/dev-setup.sh` to:
1. Pull and load the LiteLLM Docker image into Kind during `make dev-up`
2. Populate `mob-litellm-secrets` with actual API keys from the environment (same pattern as existing secrets injection)

## System-Wide Impact

### Interaction Graph

- **Agent pod startup** → reads `MODEL_ENDPOINT` env var → if `litellm:` prefix, constructs `OpenAIProvider` pointing at `mob-litellm:4000` → LLM calls route through proxy → proxy calls provider API
- **Operator** → injects `LITELLM_BASE_URL` env var into pod spec → no behavioral change to reconciliation loop
- **LiteLLM pod** → reads `mob-litellm-config` ConfigMap for model routing → reads `mob-litellm-secrets` for provider keys → exposes OpenAI-compatible API on port 4000

### Error Propagation

- LiteLLM proxy down → agent gets connection refused → entrypoint catches Exception → returns 502 to caller → agent state returns to "idle"
- Provider API error (rate limit, auth) → LiteLLM returns OpenAI-compatible error → pydantic-ai raises exception → same 502 path
- Invalid model name → LiteLLM returns 404/400 → same error path

### State Lifecycle Risks

- No new persistent state. LiteLLM proxy is stateless (no database configured in base).
- ConfigMap changes require pod restart to take effect (LiteLLM does not hot-reload config files). Rolling restart is safe.

### API Surface Parity

- The `model_endpoint` field in Agent model, CLI, YAML loader, API, CRD, and operator all pass strings through unchanged. The only new behavior is in the agent entrypoint which interprets the `litellm:` prefix. No changes needed to the data model or API.

## Acceptance Criteria

### Functional Requirements

- [ ] LiteLLM proxy Deployment + Service created in `mob` namespace via `make deploy-dev`
- [ ] Agent with `model_endpoint: "litellm:claude-sonnet"` routes LLM calls through the proxy
- [ ] LiteLLM model list is configurable per environment via Kustomize overlay patches
- [ ] Provider API keys are in `mob-litellm-secrets` (not in agent pods)
- [ ] `mob-agent-secrets` contains `LITELLM_API_KEY` for proxy authentication
- [ ] Local mode: LiteLLM Deployment scaled to 0 replicas
- [ ] CLI warns when `litellm:` endpoint is used in local mode
- [ ] Direct endpoints (`openai:*`, `anthropic:*`) continue to work unchanged

### Non-Functional Requirements

- [ ] Docker image pinned to `ghcr.io/berriai/litellm:main-v1.82.6` (avoids supply chain attack)
- [ ] LiteLLM pod has liveness and readiness probes
- [ ] Production overlay has 2+ replicas
- [ ] Resource requests and limits set on LiteLLM pod

### Quality Gates

- [ ] Agent entrypoint unit test: `litellm:` prefix creates OpenAIProvider with correct base_url
- [ ] Agent entrypoint unit test: non-litellm prefixes pass through unchanged
- [ ] Operator test: `LITELLM_BASE_URL` injected when model endpoint has `litellm:` prefix
- [ ] Integration test: agent pod successfully calls LLM through LiteLLM proxy in dev mode

## Security Considerations

- **Supply chain**: LiteLLM v1.82.7 and v1.82.8 on PyPI were compromised on March 24, 2026 (credential stealer). Docker images are NOT affected. We pin to `ghcr.io/berriai/litellm:main-v1.82.6`. Do NOT install from PyPI.
- **Known CVEs fixed in v1.82.6**: CVE-2025-45809 (SQL injection, fixed >= 1.74.9), CVE-2024-9606 (key leakage, fixed >= 1.44.12), CVE-2024-6587 (SSRF via api_base)
- **Proxy auth**: `LITELLM_MASTER_KEY` gates access. Without it, any pod in the namespace can make LLM calls. Agent pods authenticate via `LITELLM_API_KEY`.
- **Key isolation**: Provider keys live only in `mob-litellm-secrets`, reducing blast radius vs current `mob-agent-secrets` approach.
- **SSRF (CVE-2024-6587)**: Do not expose `api_base` parameter to untrusted users through the proxy config.

## Dependencies & Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| LiteLLM PyPI quarantine may affect Docker image availability | Cannot pull image | Pre-pull and cache image; use GHCR mirror |
| LiteLLM proxy is single point of failure | All agents fail if proxy down | Production: 2+ replicas; agents can still use direct endpoints |
| Config changes require pod restart | Brief downtime on config update | Rolling restart strategy; readiness probe gates traffic |
| pydantic-ai `OpenAIModel` API may change | Entrypoint breaks on upgrade | Pin pydantic-ai version; test in CI |

## Future Considerations

- **LiteLLM database mode**: Add PostgreSQL for virtual keys, spend tracking, and rate limiting per agent/team
- **`mob litellm models` CLI command**: List available models from the proxy's `/model/info` endpoint
- **Hot config reload**: Watch ConfigMap changes and trigger LiteLLM restart automatically
- **Cost dashboard**: Use LiteLLM's built-in spend tracking callbacks
- **Wildcard routing**: Configure `model_name: "anthropic/*"` to pass through any Anthropic model without explicit listing

## Sources & References

### Internal References

- Agent entrypoint: `src/mob/agent/entrypoint.py:73` — where model is passed to pydantic-ai
- Operator pod builder: `operator/src/resources/pod.rs:50-56` — MODEL_ENDPOINT injection
- Kustomize base: `deploy/base/kustomization.yaml`
- Dev overlay: `deploy/overlays/dev/kustomization.yaml`
- Local overlay: `deploy/overlays/local/kustomization.yaml`
- Existing learnings: `docs/solutions/integration-issues/pydantic-ai-agent-image-k8s-orchestration.md`

### External References

- [LiteLLM Security Update - March 2026 Supply Chain Attack](https://docs.litellm.ai/blog/security-update-march-2026)
- [LiteLLM Proxy Docker Deployment](https://docs.litellm.ai/docs/proxy/deploy)
- [LiteLLM Proxy Configuration](https://docs.litellm.ai/docs/proxy/configs)
- [LiteLLM Production Best Practices](https://docs.litellm.ai/docs/proxy/prod)
- [pydantic-ai OpenAI/LiteLLM Provider](https://ai.pydantic.dev/models/openai)
- [CVE-2025-45809 (SQL Injection)](https://security.snyk.io/vuln/SNYK-PYTHON-LITELLM-10598343)
- [GHSA-53gh-p8jc-7rg8 (RCE via post_call_rules)](https://github.com/advisories/GHSA-53gh-p8jc-7rg8)
