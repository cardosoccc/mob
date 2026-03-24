---
title: "feat: Default pydantic-ai agent Docker image with chat support"
type: feat
status: completed
date: 2026-03-24
---

# feat: Default pydantic-ai agent Docker image with chat support

## Overview

Create a fully functional default agent Docker image powered by pydantic-ai that integrates with MOB's Kubernetes-native orchestration. The agent runs an HTTP server inside its pod, receives messages via `mob agent-run send`, processes them with an LLM via pydantic-ai, and reports state transitions through pod annotations that the Rust operator observes during reconciliation.

## Problem Statement / Motivation

Today, MOB has no default agent image. Users must build their own container from scratch, understand the pod annotation protocol, and wire up state reporting manually. The `agent-run send` command exists in the CLI and API but returns 501 because no message delivery mechanism exists. This makes the entire chat-with-agent workflow non-functional.

A default pydantic-ai agent image solves three problems at once:
1. Provides a working reference implementation for agent authors
2. Completes the `agent-run send` → agent → LLM → response pipeline end-to-end
3. Demonstrates the full annotation-based state protocol with the operator

## Proposed Solution

### Architecture

```
mob agent-run send REF --message "hello"
  │
  ▼
CLI → POST /api/v1/agent-runs/{run_id}/send
  │
  ▼
API Service (send_message)
  │  1. Verify agent is Idle via CR status
  │  2. Get pod IP from K8s API
  │  3. POST http://<pod_ip>:8081/message
  │
  ▼
Agent Pod (pydantic-ai + FastAPI on :8081)
  │  1. Patch annotation → busy
  │  2. Call LLM via pydantic-ai
  │  3. Patch annotation → idle
  │  4. Return response
  │
  ▼
Operator (reconcile every 15s)
  │  Reads mob.io/agent-state annotation
  │  Updates AgentRun CR .status.state
```

### Implementation Phases

#### Phase 1: Agent Pod Infrastructure (Operator + K8s manifests)

These changes enable agent pods to self-annotate and receive HTTP traffic.

**1.1 Agent RBAC (ServiceAccount + Role + RoleBinding)**

Create K8s manifests so agent pods can patch their own annotations.

```
deploy/base/agent-rbac.yaml
```

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: mob-agent
  namespace: mob
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: mob-agent-self-annotate
  namespace: mob
rules:
  - apiGroups: [""]
    resources: ["pods"]
    verbs: ["get", "patch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: mob-agent-self-annotate
  namespace: mob
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: mob-agent-self-annotate
subjects:
  - kind: ServiceAccount
    name: mob-agent
    namespace: mob
```

**1.2 Update `build_agent_pod()` in `operator/src/resources/pod.rs`**

- Set `service_account_name: Some("mob-agent".into())` in PodSpec
- Add `AGENT_POD_NAME` env var via Downward API (`fieldRef: metadata.name`)
- Add `AGENT_NAMESPACE` env var via Downward API (`fieldRef: metadata.namespace`)
- Add `container_port: 8081` to the container spec
- Add readiness probe: `httpGet /health` on port 8081, `initialDelaySeconds: 3`, `periodSeconds: 5`

**1.3 Update kustomization**

Add `agent-rbac.yaml` to `deploy/base/kustomization.yaml` resources.

#### Phase 2: Default Agent Image (pydantic-ai + FastAPI)

**2.1 Agent entrypoint (`src/mob/agent/entrypoint.py`)**

The agent process that runs inside the pod:

```python
# Startup:
# 1. Read env vars: AGENT_RUN_ID, AGENT_NAME, AGENT_SYSTEM_PROMPT,
#    MODEL_ENDPOINT, AGENT_POD_NAME, AGENT_NAMESPACE
# 2. Initialize pydantic-ai agent with system_prompt and model_endpoint
# 3. Initialize K8s client (in-cluster config)
# 4. Start FastAPI server on 0.0.0.0:8081
# 5. Patch own pod annotation mob.io/agent-state=idle

# Endpoints:
# GET  /health        → 200 {"status": "ok", "state": "<current_state>"}
# POST /message       → Accept message, process with LLM, return response
```

**2.2 Agent HTTP contract**

Request (`POST /message`):
```json
{"message": "What is the capital of France?"}
```

Response (success, 200):
```json
{"response": "The capital of France is Paris.", "state": "idle"}
```

Response (busy, 409):
```json
{"error": "Agent is busy processing another message", "state": "busy"}
```

**2.3 State lifecycle inside the agent**

```
Start → patch annotation "idle" → wait for messages
  │
  POST /message received
  │
  ├─ If busy → return 409
  │
  ├─ If idle:
  │   1. Set internal state = busy
  │   2. Patch annotation → busy
  │   3. Call pydantic-ai agent.run(message)
  │   4. Patch annotation → idle
  │   5. Return LLM response
  │
  ├─ On unrecoverable error:
  │   1. Patch annotation → failed
  │   2. Exit process (pod phase → Failed)
  │
  └─ On graceful shutdown (SIGTERM):
      1. Patch annotation → finished
      2. Exit cleanly (pod phase → Succeeded)
```

**2.4 K8s self-annotation helper (`src/mob/agent/k8s.py`)**

```python
# patch_own_annotation(state: str) → None
#   Uses AGENT_POD_NAME + AGENT_NAMESPACE env vars
#   Calls K8s API: PATCH /api/v1/namespaces/{ns}/pods/{name}
#   Body: {"metadata": {"annotations": {"mob.io/agent-state": state}}}
```

**2.5 Dockerfile.agent**

```dockerfile
FROM python:3.11-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

FROM base AS builder
RUN pip install --no-cache-dir uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src/ src/
RUN uv sync --frozen --no-dev

FROM base AS runtime
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8081
ENTRYPOINT ["python", "-m", "mob.agent.entrypoint"]
```

**2.6 Add pydantic-ai dependency to `pyproject.toml`**

Add `pydantic-ai>=0.1.0` to the dependencies list.

#### Phase 3: Message Delivery (API Service Layer)

**3.1 Implement `send_message()` in `src/mob/services/agent_runs.py`**

```python
# send_message(session, run_id, message) → dict:
#   1. Get AgentRun from DB
#   2. Verify run is active via CR status (get_agent_run_live_status)
#      - If state not in (Idle, Busy): raise ServiceError("Agent is not running", 409)
#   3. Get pod name from CR status (status.podName)
#   4. Get pod IP via K8s CoreV1Api: read_namespaced_pod(pod_name).status.pod_ip
#   5. POST http://{pod_ip}:8081/message with {"message": message}
#      - Connect timeout: 5s, read timeout: 120s
#   6. If agent returns 409 (busy): raise ServiceError("Agent is busy", 409)
#   7. Return agent response dict
```

**3.2 Add pod IP lookup helper**

Add a function to `src/mob/services/agent_runs.py` (or a shared K8s utility):

```python
# _get_pod_ip(pod_name: str) → str:
#   Uses K8s CoreV1Api to read pod, extract status.pod_ip
#   Raises ServiceError if pod not found or IP not assigned
```

**3.3 Update CLI to display agent response**

In `src/mob/cli/commands/agent_run.py`, update `agent_run_send`:

```python
# Change from:
#   api_post(f"/agent-runs/{run_id}/send", {"message": message})
#   print_success("Message sent.")
# To:
#   result = api_post(f"/agent-runs/{run_id}/send", {"message": message})
#   if result.get("response"):
#       click.echo(result["response"])
#   else:
#       print_success("Message sent.")
```

#### Phase 4: Build System + Integration

**4.1 Makefile targets**

```makefile
AGENT_IMAGE := mob-agent-pydantic
AGENT_TAG := latest

## build-agent: build the default pydantic-ai agent Docker image
build-agent:
	docker build -t $(AGENT_IMAGE):$(AGENT_TAG) -f Dockerfile.agent .

## dev-kind-rebuild-agent: rebuild agent image and load to Kind
dev-kind-rebuild-agent: build-agent
	kind load docker-image $(AGENT_IMAGE):$(AGENT_TAG) --name $(KIND_CLUSTER)
```

**4.2 Default agent_template value**

Consider making `mob-agent-pydantic:latest` the default when creating agents without an explicit `agent_template`. This could be a configuration setting rather than a DB default, to keep flexibility.

## System-Wide Impact

### Interaction Graph

- `mob agent-run send` → API route → `send_message()` → K8s pod IP lookup → HTTP POST to agent pod → pydantic-ai → LLM provider
- Agent pod startup → K8s API PATCH (self-annotation) → Operator reconcile → CR status update
- Operator `derive_state_from_pod()` already handles the annotation values — no changes needed

### Error Propagation

- Agent LLM timeout → agent catches, returns 500 to service → service returns 502 to CLI
- Agent pod crash during processing → pod phase becomes Failed → operator detects within 15s → CR status = Failed
- Pod IP unreachable → `send_message()` gets connection error → returns 502 "Agent unreachable"
- K8s API unavailable (self-annotation fails) → agent logs warning but continues operating — state reporting degrades gracefully

### State Lifecycle Risks

- **Race window**: Agent crashes after setting `busy` annotation but before LLM completes. CR says Busy, pod is dead. `send_message()` will get connection refused. Mitigation: `send_message()` catches connection errors and returns a clear "Agent unreachable" error. Operator will detect pod failure within 15s.
- **DB state staleness**: The Python DB `AgentRun.state` stays at `pending` because nothing syncs CR status back to the DB. `send_message()` must check CR status directly (via `get_agent_run_live_status()`), not DB state.

### API Surface Parity

- `POST /agent-runs/{run_id}/send` — already exists, needs implementation
- Agent pod `POST /message` — new internal endpoint (not exposed externally)
- Agent pod `GET /health` — new internal endpoint (used by readiness probe)

## Acceptance Criteria

- [ ] `Dockerfile.agent` builds a working image with pydantic-ai
- [ ] Agent pod starts, sets annotation to `idle`, operator reflects `Idle` in CR status
- [ ] `mob agent-run send <ref> --message "hello"` delivers message to agent and prints LLM response
- [ ] Agent sets `busy` while processing, `idle` after responding — operator reflects transitions
- [ ] Agent returns 409 if a message arrives while busy
- [ ] Agent sets `failed` annotation on unrecoverable errors
- [ ] Agent handles SIGTERM gracefully (sets `finished`, exits cleanly)
- [ ] Readiness probe on `/health:8081` gates pod readiness
- [ ] Agent RBAC (ServiceAccount + Role + RoleBinding) is deployed
- [ ] `make build-agent` builds the agent image
- [ ] `make dev-kind-rebuild-agent` loads image to Kind cluster
- [ ] End-to-end test: create agent with `mob-agent-pydantic:latest` template, run it, send message, get response

## Dependencies & Risks

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| pydantic-ai version instability | Medium | Pin to a specific version in pyproject.toml |
| Pod IP routing in Kind/local dev | Low | Kind supports pod IP routing by default; document if issues arise |
| LLM provider requires API key | High | Agent must read `OPENAI_API_KEY` or equivalent from env/secret; document setup |
| 15s reconciliation delay for state sync | Low | Acceptable for v1; reduce interval later if needed |
| DB state never syncs from CR | Medium | `send_message()` reads CR status directly; DB sync deferred to future work |

## Files to Create

- `src/mob/agent/__init__.py`
- `src/mob/agent/entrypoint.py` — FastAPI server + pydantic-ai agent loop
- `src/mob/agent/k8s.py` — K8s self-annotation helper
- `Dockerfile.agent` — Agent container image
- `deploy/base/agent-rbac.yaml` — ServiceAccount + Role + RoleBinding

## Files to Modify

- `operator/src/resources/pod.rs` — Add serviceAccountName, AGENT_POD_NAME/AGENT_NAMESPACE env vars (Downward API), containerPort, readiness probe
- `src/mob/services/agent_runs.py` — Implement `send_message()` with pod IP lookup and HTTP forwarding
- `src/mob/cli/commands/agent_run.py` — Display agent response from send
- `Makefile` — Add `build-agent` and `dev-kind-rebuild-agent` targets
- `pyproject.toml` — Add `pydantic-ai` dependency
- `deploy/base/kustomization.yaml` — Include agent-rbac.yaml

## Sources & References

- Operator reconciliation: `operator/src/controller/agent_run_controller.rs`
- Pod builder: `operator/src/resources/pod.rs`
- CRD definition: `operator/src/crd/agent_run.rs`
- Service layer: `src/mob/services/agent_runs.py`
- CLI send command: `src/mob/cli/commands/agent_run.py:90-100`
- API route: `src/mob/api/routes/agent_runs.py:75-84`
- Ideation #7 (agent entrypoint): `docs/ideation/2026-03-23-open-ideation.md:96-105`
- Orchestration loop plan (deferred send_message): `docs/plans/2026-03-23-001-fix-wire-agent-orchestration-loop-plan.md:643-656`
