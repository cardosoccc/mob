---
title: "Default Pydantic-AI Agent Image for MOB K8s Agent Orchestration"
category: integration-issues
date: 2026-03-24
tags:
  - pydantic-ai
  - kubernetes
  - fastapi
  - kind
  - docker
  - rbac
  - operator-pattern
  - async-python
  - rust-operator
severity: high
components:
  - src/mob/agent/ (FastAPI agent entrypoint, pydantic-ai integration)
  - operator/src/resources/pod.rs (Rust operator pod builder)
  - src/mob/services/sessions.py (send_message service)
  - deploy/base/ (K8s RBAC manifests, kustomization)
  - Dockerfile.agent (agent container image)
  - scripts/dev-setup.sh (Kind cluster bootstrap)
symptoms:
  - Agent pod CrashLoopBackOff due to missing API key at module-level Agent() init
  - ImagePullBackOff in Kind cluster for operator and agent images
  - kube-proxy CrashLoopBackOff from exhausted inotify watches
  - API pod 403 Forbidden when creating Session custom resources
  - HTTP 200 returned for error responses instead of 409/502
  - Raw Python exception details leaked to clients in LLM error paths
  - Async event loop blocked by synchronous K8s API calls
  - Conversation history lost between successive agent messages
related:
  - docs/plans/2026-03-24-004-feat-default-pydantic-ai-agent-image-plan.md
  - docs/plans/2026-03-23-001-fix-wire-agent-orchestration-loop-plan.md
  - docs/ideation/2026-03-23-open-ideation.md (Idea #7)
---

# Default Pydantic-AI Agent Image for MOB K8s Orchestration

## Problem Description

Building a default pydantic-ai agent Docker image for MOB, a Kubernetes agent orchestration platform. The agent runs FastAPI on port 8081 inside K8s pods, receives messages via HTTP from the MOB API, processes them with an LLM via pydantic-ai, and reports state (`idle`/`busy`/`finished`/`failed`) via pod annotations that the Rust operator observes during reconciliation. The implementation surfaced 10 distinct issues across Python, Rust, Kubernetes, and Docker.

## Root Cause Analysis

Six primary root causes were identified:

### 1. FastAPI returns Pydantic models as 200 regardless of intent

Returning an `ErrorResponse` model from a handler yields HTTP 200. FastAPI serializes any Pydantic model as a successful response body. The `responses={409: ...}` annotation is documentation-only for OpenAPI — it does not change the actual status code.

### 2. pydantic-ai Agent() validates API keys at construction time

Instantiating `Agent("openai:gpt-4o")` at module level crashes the process immediately if no API key environment variable is set. The container exits before the health check can even start, causing CrashLoopBackOff.

### 3. Kind clusters cannot pull `:latest` from Docker Hub

The default `imagePullPolicy: Always` causes image pull failures for images loaded directly into the Kind node with `kind load docker-image`. Kind uses containerd which cannot reach Docker Hub for locally-built images.

### 4. Synchronous K8s Python client blocks the asyncio event loop

The `kubernetes` library is entirely synchronous. Calling `core_api.read_namespaced_pod()` inside an `async def` handler freezes all concurrent request processing. Under load, this serializes all requests.

### 5. Pod-to-pod HTTP requires running inside the cluster

The `send_message()` service POSTs to pod cluster IPs (`10.244.x.x`), which are only routable from within the K8s network. This works in dev mode (API deployed in-cluster) but not from the host machine in local mode. (auto memory [claude])

### 6. Sharing ServiceAccounts grants excessive permissions

Using the operator's ClusterRole for the API pod gave the API create/delete access to all pods and CRDs cluster-wide. A dedicated namespace-scoped Role with minimal permissions is required.

## Working Solution

### Fix 1: Use JSONResponse for non-200 status codes

```python
from fastapi.responses import JSONResponse

@app.post("/message")
async def handle_message(req: MessageRequest):
    if _state != "idle":
        return JSONResponse(
            status_code=409,
            content={"error": "Agent is busy", "state": _state},
        )
    # ... process message
```

### Fix 2: Lazy-initialize the pydantic-ai Agent

```python
_ai_agent = None

def _get_agent():
    global _ai_agent
    if _ai_agent is None:
        _ai_agent = Agent(MODEL_ENDPOINT, instructions=SYSTEM_PROMPT)
    return _ai_agent
```

### Fix 3: Set imagePullPolicy in Rust operator pod spec

```rust
image_pull_policy: Some("IfNotPresent".into()),
```

### Fix 4: Wrap synchronous K8s calls in asyncio.to_thread()

```python
# Cache the K8s client as a singleton
_core_api = None

def _get_core_api():
    global _core_api
    if _core_api is not None:
        return _core_api
    k8s_config.load_incluster_config()
    _core_api = k8s_client.CoreV1Api()
    return _core_api

# In async handler — offload blocking call to thread pool
pod_ip = await asyncio.to_thread(_get_pod_ip_sync, pod_name)
```

### Fix 5: Maintain pydantic-ai conversation history

```python
_message_history = None

async def handle_message(req):
    global _message_history
    result = await asyncio.wait_for(
        _get_agent().run(req.message, message_history=_message_history),
        timeout=120,
    )
    _message_history = result.all_messages()
```

### Fix 6: Dedicated RBAC per component

Created three separate ServiceAccounts with namespace-scoped Roles:
- `mob-operator` — pod CRUD, CRD management, finalizers
- `mob-api` — agentrun CRUD, pod get (for IP lookup)
- `mob-agent` — pod get/patch (self-annotation only)

### Fix 7: Inject secrets via envFrom with optional: true

```rust
env_from: Some(vec![EnvFromSource {
    secret_ref: Some(SecretEnvSource {
        name: "mob-agent-secrets".into(),
        optional: Some(true),
    }),
    ..Default::default()
}]),
```

## Investigation Steps

1. Agent pod entered CrashLoopBackOff — `docker run` revealed import-time crash on missing API key
2. After lazy init fix, ImagePullBackOff — Kind couldn't pull `:latest` from Docker Hub
3. After imagePullPolicy fix, kube-proxy CrashLoop — inotify limits too low (`max_user_instances=128`)
4. After sysctl fix, API returned 403 on CR creation — default SA had no RBAC
5. After RBAC fix, `send_message` returned 200 for busy agents — FastAPI status code bug
6. Code review identified: sync K8s blocking event loop, no conversation history, leaked exceptions, shared SA privileges
7. All fixes applied, verified with end-to-end test: create agent → run → send message → get LLM response → verify multi-turn memory

## Prevention Strategies

### Before You Deploy Checklist

```
IMAGES & REGISTRY
[ ] All images loaded into Kind: kind load docker-image <image>:<tag>
[ ] Every container spec has explicit imagePullPolicy
[ ] No :latest tag without imagePullPolicy: IfNotPresent

HOST PREREQUISITES (dev/CI)
[ ] inotify limits raised (max_user_watches >= 524288, max_user_instances >= 512)
[ ] kubectl context points to correct cluster

SECRETS & CONFIGURATION
[ ] Required secrets created in namespace (mob-agent-secrets)
[ ] API keys NOT baked into images
[ ] Agent SDK clients lazily initialized, not at import time
[ ] envFrom.secretRef has optional: true for graceful degradation

RBAC
[ ] Each component has its own ServiceAccount
[ ] Roles use minimum-privilege verbs (no wildcards)
[ ] kubectl auth can-i audit passes for each SA

ASYNC CORRECTNESS
[ ] No synchronous blocking calls in async handlers
[ ] K8s client calls wrapped in asyncio.to_thread()
[ ] HTTP clients reused across requests (connection pooling)

HTTP RESPONSE CORRECTNESS
[ ] All error returns use JSONResponse(status_code=...) or raise HTTPException
[ ] No bare dict/model returns with error semantics
[ ] Response status codes tested for every error path
```

### Key Rules

1. **Never return a plain Pydantic model for non-200 responses** — always use `JSONResponse` or `HTTPException`
2. **Never instantiate SDK clients at module scope** if they validate credentials on init
3. **Never call synchronous I/O in async handlers** — use `asyncio.to_thread()`
4. **One ServiceAccount per component role** — never share operator and API permissions
5. **Always set `imagePullPolicy: IfNotPresent`** for locally-loaded Kind images

## Verification

1. Build and load images: `make build-agent && kind load docker-image mob-agent-pydantic:latest`
2. Create secrets: `kubectl create secret generic mob-agent-secrets --from-literal=ANTHROPIC_API_KEY=<key>`
3. Create agent and run via API
4. Confirm pod starts and reaches `Idle` state: `kubectl get sessions`
5. Send message: `POST /sessions/{id}/send` returns 200 with LLM response
6. Send while busy: returns 409 (not 200)
7. Multi-turn test: agent remembers context from previous messages
8. LLM timeout: returns 504 after configured timeout

## Cross-References

- **Plan:** `docs/plans/2026-03-24-004-feat-default-pydantic-ai-agent-image-plan.md`
- **Predecessor:** `docs/plans/2026-03-23-001-fix-wire-agent-orchestration-loop-plan.md` (deferred `send_message` — now implemented)
- **Ideation:** `docs/ideation/2026-03-23-open-ideation.md` Idea #7 (Agent Runtime Entrypoint — now implemented)
- **CLI restructure:** `docs/plans/2026-03-24-002-feat-agent-run-commands-restructure-plan.md` (`session send` command)
