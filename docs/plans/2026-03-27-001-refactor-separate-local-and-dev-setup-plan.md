---
title: "refactor: Separate local and dev environment setup scripts and Makefile targets"
type: refactor
status: completed
date: 2026-03-27
---

# refactor: Separate local and dev environment setup scripts and Makefile targets

## Overview

Split the monolithic `scripts/dev-setup.sh` and its Makefile targets into two distinct setup paths: **local mode** (SQLite + Kind cluster, no PostgreSQL) and **dev mode** (Kind cluster + PostgreSQL via Docker Compose). Currently, the single `dev-setup.sh` always starts PostgreSQL and deploys the full API stack, even though local mode doesn't need either.

## Problem Statement / Motivation

The current setup conflates two distinct workflows:

1. **Local mode** — CLI talks directly to the service layer with SQLite. Only needs a Kind cluster for the operator and agent pods. No HTTP API, no PostgreSQL.
2. **Dev mode** — CLI talks to the API over HTTP. API runs in Kind, backed by PostgreSQL in Docker Compose. Full stack.

Running `make dev-up` for local mode wastes time building the API image, starting PostgreSQL, patching endpoints, and deploying unnecessary K8s resources. There's no way to stand up just the Kind + operator infrastructure for local development.

## Proposed Solution

1. Create a new `scripts/local-setup.sh` for local mode (Kind cluster + operator + agent infrastructure only).
2. Refactor `scripts/dev-setup.sh` to remain focused on the full dev stack (Kind + PostgreSQL + API).
3. Extract shared logic (Kind cluster management, image building) into `scripts/lib.sh`.
4. Create a new Kustomize overlay at `deploy/overlays/local/` that deploys only the operator stack (CRDs, operator, agent RBAC, namespace).
5. Add `local-*` Makefile targets alongside existing `dev-*` targets.
6. Add mode-conflict detection so users can't accidentally layer local on top of dev (or vice versa).

## Technical Approach

### Architecture Decision: Local mode does NOT deploy the API to Kind

In local mode, the CLI bypasses HTTP entirely — `local_backend.py` routes all API-style calls to service functions with a SQLite session. The only reason to have a Kind cluster in local mode is for the **operator** (which watches AgentRun CRs and creates agent pods) and the **agent pods** themselves.

This means:
- No API deployment, service, ingress, configmap, or database secret needed in the local K8s overlay.
- No API Docker image needs to be built or loaded.
- No PostgreSQL container or Docker network needed.
- The host CLI creates AgentRun CRs directly via `kubeconfig` (already works — `_try_get_k8s_custom_api()` uses `load_kube_config()`).

**Agent messaging in local mode**: Pod IPs (`10.244.x.x`) inside Kind are not directly routable from the host. To enable `mob agent-run send` in local mode, the `send_message` service function will detect local mode and use `kubectl port-forward` to create a temporary tunnel to the agent pod, sending the HTTP request through `localhost` instead of the pod IP. This is transparent to the user — the same `mob agent-run send` command works in both modes.

### File Changes

#### New files

| File | Purpose |
|------|---------|
| `scripts/local-setup.sh` | Local mode setup/teardown (Kind + operator only) |
| `scripts/lib.sh` | Shared functions: prerequisites check, Kind cluster management, image build/load |
| `deploy/overlays/local/kustomization.yaml` | Local K8s overlay — operator stack only |
| `deploy/overlays/local/patches/operator-deployment.yaml` | Local-specific operator patches (IfNotPresent, reduced resources) |

#### Modified files

| File | Change |
|------|--------|
| `Makefile` | Add `local-*` targets, reorganize `dev-*` targets, add `help` target |
| `scripts/dev-setup.sh` | Source `scripts/lib.sh`, remove duplicated logic, add mode-conflict guard |
| `src/mob/services/agent_runs.py` | Add `_send_via_port_forward()`, route `send_message()` based on mode |

### Implementation Details

#### Phase 1: Extract shared logic into `scripts/lib.sh`

```bash
# scripts/lib.sh — Shared functions for setup scripts

KIND_CLUSTER="mob-local"
KIND_CONFIG="kind-config.yaml"
KIND_NODE="${KIND_CLUSTER}-control-plane"
NAMESPACE="mob"
KUBE_CTX="kind-${KIND_CLUSTER}"
MODE_FILE="/tmp/.mob-env-mode"

log()  { echo "==> $*"; }
info() { echo "    $*"; }

check_prerequisites() {
  # docker, kind, kubectl checks
}

cluster_exists() {
  kind get clusters 2>/dev/null | grep -q "^${KIND_CLUSTER}$"
}

create_kind_cluster() {
  # Idempotent — reuses existing cluster
}

delete_kind_cluster() {
  kind delete cluster --name "${KIND_CLUSTER}" 2>/dev/null || true
}

build_and_load_image() {
  # $1=image_name, $2=tag, $3=dockerfile, $4=context
  # Builds and loads into Kind
}

check_mode_conflict() {
  # $1=desired_mode ("local" or "dev")
  # Reads MODE_FILE, fails if different mode is active
}

set_active_mode() {
  # $1=mode — writes to MODE_FILE
}

clear_active_mode() {
  rm -f "${MODE_FILE}"
}
```

#### Phase 2: Create local Kustomize overlay

`deploy/overlays/local/kustomization.yaml` cherry-picks only the resources needed:

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: mob

resources:
  - ../../base/namespace.yaml
  - ../../base/crds/agentrun.yaml
  - ../../base/operator/serviceaccount.yaml
  - ../../base/operator/rbac.yaml
  - ../../base/operator/deployment.yaml
  - ../../base/agent-rbac.yaml

commonLabels:
  app.kubernetes.io/name: mob
  app.kubernetes.io/instance: local
  app.kubernetes.io/managed-by: kustomize

patches:
  - path: patches/operator-deployment.yaml
```

`deploy/overlays/local/patches/operator-deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mob-operator
  namespace: mob
spec:
  template:
    spec:
      containers:
        - name: mob-operator
          imagePullPolicy: IfNotPresent
          resources:
            requests:
              cpu: 25m
              memory: 32Mi
            limits:
              cpu: 100m
              memory: 128Mi
```

**Why cherry-pick instead of restructuring base?** The base kustomization bundles API and operator resources together. Kustomize doesn't support subtracting resources from a base. Restructuring `deploy/base/` into separate `api/` and `operator/` subdirectories would be cleaner architecturally, but it touches many files and risks breaking the existing dev/staging/production overlays. Cherry-picking specific resources in the local overlay is lower-risk and achieves the same result.

#### Phase 3: Create `scripts/local-setup.sh`

```bash
#!/usr/bin/env bash
# local-setup.sh — Bootstrap a Kind cluster with the operator for local mode
#
# Local mode: CLI -> service layer -> SQLite. Kind runs only the operator
# and agent pods for agent-run lifecycle management.
#
# Usage:
#   ./scripts/local-setup.sh          # Setup
#   ./scripts/local-setup.sh teardown # Destroy
#   ./scripts/local-setup.sh status   # Show status
#   ./scripts/local-setup.sh reset    # Teardown + setup

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib.sh"

OPERATOR_IMAGE="mob-operator"
OPERATOR_TAG="latest"
AGENT_IMAGE="mob-agent-pydantic"
AGENT_TAG="latest"

cmd_setup() {
  check_prerequisites
  check_mode_conflict "local"

  # Create Kind cluster (shared kind-config.yaml, port mapping unused but harmless)
  create_kind_cluster

  # Build and load only operator + agent images (no API image needed)
  build_and_load_image "${OPERATOR_IMAGE}" "${OPERATOR_TAG}" "./operator/Dockerfile" "./operator/"
  build_and_load_image "${AGENT_IMAGE}" "${AGENT_TAG}" "Dockerfile.agent" "."

  # Deploy operator stack only (no API, no PostgreSQL)
  log "Deploying operator stack to Kind cluster..."
  kubectl --context "${KUBE_CTX}" apply -k deploy/overlays/local/

  # Wait for operator
  log "Waiting for operator deployment to be ready..."
  kubectl --context "${KUBE_CTX}" -n "${NAMESPACE}" rollout status deployment/mob-operator --timeout=120s

  set_active_mode "local"

  # Summary
  echo
  log "Local environment is ready!"
  echo
  info "Mode:       local (CLI -> SQLite)"
  info "Database:   ~/.mob/mob.db (SQLite)"
  info "Kind:       ${KIND_CLUSTER} (operator + agent pods)"
  info "Kubectl:    kubectl --context ${KUBE_CTX} -n ${NAMESPACE} ..."
  echo
  info "Useful commands:"
  info "  make local-status          — Show pod/service status"
  info "  make local-rebuild-operator — Rebuild and redeploy the operator"
  info "  make local-rebuild-agent   — Rebuild and reload the agent image"
  info "  make local-down            — Tear down the Kind cluster"
  echo
  info "Note: 'mob agent-run send' uses kubectl port-forward in local mode"
  info "      (pod IPs are not directly routable from host)."
}

cmd_teardown() {
  delete_kind_cluster
  clear_active_mode
  log "Local environment torn down."
}

cmd_status() {
  if ! cluster_exists; then
    log "Kind cluster '${KIND_CLUSTER}' does not exist."
    return
  fi
  log "Kind cluster: ${KIND_CLUSTER}"
  kubectl --context "${KUBE_CTX}" -n "${NAMESPACE}" get pods -o wide 2>/dev/null || info "Namespace '${NAMESPACE}' not found yet."
  echo
  log "Services:"
  kubectl --context "${KUBE_CTX}" -n "${NAMESPACE}" get svc 2>/dev/null || true
}

case "${1:-setup}" in
  setup)    cmd_setup ;;
  teardown) cmd_teardown ;;
  status)   cmd_status ;;
  reset)    cmd_teardown; cmd_setup ;;
  *)        echo "Usage: $0 {setup|teardown|status|reset}" >&2; exit 1 ;;
esac
```

#### Phase 4: Enable `send_message` in local mode via `kubectl port-forward`

Modify `src/mob/services/agent_runs.py` to detect local mode and tunnel through `kubectl port-forward` instead of connecting to the pod IP directly.

**Changes to `send_message()`:**

After obtaining `pod_name` and before making the HTTP request, check if we're in local mode:

```python
# src/mob/services/agent_runs.py

import subprocess
import socket

async def _get_free_port() -> int:
    """Find an available local port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


async def _send_via_port_forward(
    pod_name: str, message: str, headers: dict
) -> dict:
    """Send a message to an agent pod via kubectl port-forward (for local mode)."""
    settings = get_settings()
    local_port = await _get_free_port()

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
        resp = await client.post(
            f"http://127.0.0.1:{local_port}/message",
            json={"message": message},
            headers=headers,
        )

        if resp.status_code == 409:
            data = resp.json()
            raise ServiceError(data.get("error", "Agent is busy"), 409)
        if resp.status_code == 401:
            raise ServiceError("Agent authentication failed", 502)
        if resp.status_code != 200:
            raise ServiceError("Agent returned an error", 502)

        return resp.json()

    finally:
        # Always clean up the port-forward process
        pf_proc.terminate()
        await pf_proc.wait()
```

**Updated `send_message()` routing logic:**

```python
async def send_message(
    session: AsyncSession, run_id: str, message: str
) -> dict:
    run = await session.get(AgentRun, run_id)
    if not run:
        raise ServiceError("Agent run not found", 404)

    # Check live CR status
    live_status = await get_agent_run_live_status(str(run.id))
    cr_state = live_status.get("state", "")
    if cr_state not in ("Idle", "Busy"):
        raise ServiceError(
            f"Agent is not running (state: {cr_state or 'unknown'})", 409
        )

    pod_name = live_status.get("podName")
    if not pod_name:
        raise ServiceError("Agent pod name not available", 502)

    # Build auth headers
    headers = {}
    auth_token = getattr(get_settings(), "agent_auth_token", None)
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    # Route based on mode: local uses port-forward, dev/remote uses pod IP directly
    if get_settings().mode == "local":
        return await _send_via_port_forward(pod_name, message, headers)

    # Dev/remote mode: direct pod IP access (existing behavior)
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
```

**Why `kubectl port-forward`?** It's the standard K8s-native way to reach pods from outside the cluster. No Docker networking hacks, no extra K8s services, no platform-specific routing. It works with any K8s cluster (Kind, minikube, remote). The overhead of spawning a subprocess is negligible for an interactive CLI operation.

#### Phase 5: Refactor `scripts/dev-setup.sh`

Refactor to source `scripts/lib.sh` and add mode-conflict detection. The core PostgreSQL + Kind + API deployment logic stays the same, but shared functions move to `lib.sh`:

```bash
#!/usr/bin/env bash
# dev-setup.sh — Bootstrap Kind + PostgreSQL for dev mode
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib.sh"

APP_IMAGE="mob-api"
APP_TAG="latest"
OPERATOR_IMAGE="mob-operator"
OPERATOR_TAG="latest"
AGENT_IMAGE="mob-agent-pydantic"
AGENT_TAG="latest"
COMPOSE_FILE="docker-compose.yaml"
DOCKER_NETWORK="mob-dev"
POSTGRES_CONTAINER="mob-postgres"

cmd_setup() {
  check_prerequisites
  check_mode_conflict "dev"

  # Start PostgreSQL
  log "Starting PostgreSQL via Docker Compose..."
  docker compose -f "${COMPOSE_FILE}" up -d
  # ... wait for healthy ...

  # Create Kind cluster
  create_kind_cluster

  # Connect Kind node to Docker network
  # ... (existing logic) ...

  # Build ALL images (API + operator + agent)
  build_and_load_image "${APP_IMAGE}" "${APP_TAG}" "Dockerfile" "."
  build_and_load_image "${OPERATOR_IMAGE}" "${OPERATOR_TAG}" "./operator/Dockerfile" "./operator/"
  build_and_load_image "${AGENT_IMAGE}" "${AGENT_TAG}" "Dockerfile.agent" "."

  # Deploy full dev overlay
  kubectl --context "${KUBE_CTX}" apply -k deploy/overlays/dev/

  # Patch Postgres endpoints
  # ... (existing logic) ...

  set_active_mode "dev"
  # ... summary ...
}

cmd_teardown() {
  delete_kind_cluster
  docker compose -f "${COMPOSE_FILE}" down -v 2>/dev/null || true
  clear_active_mode
}

# ... rest same structure as current ...
```

#### Phase 6: Update Makefile

```makefile
# ---------- Local mode targets ----------

## local-up: start local environment (Kind + operator, SQLite, no PostgreSQL)
local-up:
	./scripts/local-setup.sh setup

## local-down: tear down local environment
local-down:
	./scripts/local-setup.sh teardown

## local-status: show local environment status
local-status:
	./scripts/local-setup.sh status

## local-reset: destroy and recreate local environment
local-reset:
	./scripts/local-setup.sh reset

## local-rebuild-operator: rebuild operator image and redeploy
local-rebuild-operator:
	docker build -t mob-operator:latest ./operator/
	kind load docker-image mob-operator:latest --name $(KIND_CLUSTER)
	kubectl --context $(KIND_CTX) -n mob rollout restart deployment/mob-operator

## local-rebuild-agent: rebuild agent image and load to Kind
local-rebuild-agent: build-agent
	kind load docker-image $(AGENT_IMAGE):$(AGENT_TAG) --name $(KIND_CLUSTER)

# ---------- Dev mode targets ----------

## dev-up: start dev environment (Kind + PostgreSQL + API)
dev-up:
	./scripts/dev-setup.sh setup

## dev-down: stop dev environment
dev-down:
	./scripts/dev-setup.sh teardown

## dev-status: show dev environment status
dev-status:
	./scripts/dev-setup.sh status

## dev-logs: tail API pod logs
dev-logs:
	kubectl --context $(KIND_CTX) -n mob logs -f -l app.kubernetes.io/component=api

## dev-psql: open psql shell against local PostgreSQL
dev-psql:
	docker exec -it mob-postgres psql -U mob_admin -d mob

## dev-rebuild: rebuild API image and redeploy
dev-rebuild: build
	kind load docker-image $(APP_IMAGE):$(APP_TAG) --name $(KIND_CLUSTER)
	kubectl --context $(KIND_CTX) -n mob rollout restart deployment/mob-api
	kubectl --context $(KIND_CTX) -n mob rollout status deployment/mob-api --timeout=120s

## dev-rebuild-agent: rebuild agent image and load to Kind
dev-rebuild-agent: build-agent
	kind load docker-image $(AGENT_IMAGE):$(AGENT_TAG) --name $(KIND_CLUSTER)

## dev-reset: destroy and recreate dev environment
dev-reset:
	./scripts/dev-setup.sh reset
```

**Remove**: `dev-kind-*` targets (replaced by cleaner `dev-*` / `local-*` naming). Keep `run` as a legacy alias pointing to `dev-up` for backwards compatibility during transition.

## System-Wide Impact

- **API surface parity**: No impact — this is infrastructure-only. The CLI, API, operator, and agent code are unchanged.
- **Error propagation**: Mode-conflict detection in setup scripts prevents inconsistent K8s state.
- **State lifecycle risks**: Switching modes without teardown could leave orphaned K8s resources (e.g., API deployment crash-looping without PostgreSQL). The mode-conflict guard (`/tmp/.mob-env-mode`) mitigates this.
- **Integration test scenarios**: Tests are unaffected — they use in-memory SQLite via pytest fixtures.

## Acceptance Criteria

### Functional Requirements

- [ ] `make local-up` creates a Kind cluster and deploys only CRDs + operator + agent RBAC (no API, no PostgreSQL)
- [ ] `make local-down` deletes only the Kind cluster (does not touch Docker Compose)
- [ ] `make local-status` shows operator and agent pod status
- [ ] `make local-reset` tears down and recreates the local environment
- [ ] `make local-rebuild-operator` rebuilds and redeploys the operator image
- [ ] `make local-rebuild-agent` rebuilds and reloads the agent image into Kind
- [ ] `make dev-up` starts PostgreSQL + Kind cluster + deploys full stack (existing behavior, refactored)
- [ ] `make dev-down` tears down Kind + PostgreSQL (existing behavior)
- [ ] `make dev-rebuild` rebuilds and redeploys the API (existing behavior, renamed from `dev-kind-rebuild`)
- [ ] Running `make local-up` when dev is active (or vice versa) prints an error and exits
- [ ] After `make local-up`, the user can run `mob init local && mob migrate` and do CRUD operations via CLI against SQLite
- [ ] After `make local-up`, the user can create agent runs and the operator creates agent pods
- [ ] `mob agent-run send` works in local mode via `kubectl port-forward` tunnel
- [ ] `mob agent-run send` continues to work in dev mode via direct pod IP (existing behavior)
- [ ] After `make dev-up`, the full dev workflow works as before (CLI -> HTTP -> API -> PostgreSQL)
- [ ] No PostgreSQL container or headless service exists in the K8s cluster when running in local mode

### Non-Functional Requirements

- [ ] `make local-up` completes significantly faster than `make dev-up` (no API build, no PostgreSQL wait)
- [ ] Shared logic in `scripts/lib.sh` has no duplication with individual setup scripts
- [ ] `kind-config.yaml` is shared across both modes (port mapping unused but harmless in local mode)

## Dependencies & Risks

**Dependencies:**
- None — all changes are local infrastructure files (scripts, Makefile, K8s overlays).

**Risks:**
- **Low**: Renaming `dev-kind-*` targets to `dev-*` could break muscle memory. Mitigation: keep `run` alias, add deprecation comment for old target names.
- **Low**: The mode-conflict file at `/tmp/.mob-env-mode` is ephemeral (cleared on reboot). If the system reboots between setup and teardown, the guard won't detect the stale state. Acceptable for local dev tooling.
- **Low**: Cherry-picking base resources in the local overlay means new base resources won't automatically be included in the local overlay. This is actually desirable — new API-related resources shouldn't be in the local overlay anyway.

## Sources & References

### Internal References

- Current setup script: `scripts/dev-setup.sh`
- Current Makefile: `Makefile`
- Base kustomization: `deploy/base/kustomization.yaml`
- Dev overlay: `deploy/overlays/dev/kustomization.yaml`
- Local backend routing: `src/mob/cli/local_backend.py`
- K8s config loading: `src/mob/services/agent_runs.py` (`_try_get_k8s_custom_api`)
- Mode detection: `src/mob/config.py` (`is_local_mode`, `ENV_DEFAULTS`)

### Documented Learnings

- Pod IPs not routable from host in local mode (solved via port-forward): `docs/solutions/integration-issues/pydantic-ai-agent-image-k8s-orchestration.md`
- Kind image loading requires `imagePullPolicy: IfNotPresent`: same doc above
- inotify limits for Kind: same doc above
