---
date: 2026-03-23
topic: open
focus: open-ended ideation for young AI agent orchestration platform
---

# Ideation: mob — Open-Ended Improvement Ideas

## Codebase Context

**Project:** mob — "A tool for orchestrating AI agents — cloud-native, provider agnostic"

- **Stack:** Python 3.11+ / FastAPI (async) / SQLAlchemy (async) / PostgreSQL / Kubernetes
- **CLI:** Click-based with dual-mode: local SQLite backend vs remote HTTP API client
- **Infra:** Kind for local dev, Kustomize deploys (dev/staging/prod), Terraform (AWS EKS/RDS/VPC, GCP stub)
- **Domain models:** agents, tasks, skills, domains, groups, organizations, users, agent_runs
- **Maturity:** 5 commits on main, no README, no CI, no documentation
- **Key gaps:** auth/ and cluster/ modules are empty stubs; Alembic dep installed but never bootstrapped; lint tools referenced in Makefile but missing from dev deps; K8sManager fully implemented but never called from services
- **No prior learnings** in docs/solutions/

## Ranked Ideas

### 1. Close the Core Orchestration Loop

**Description:** Wire `K8sManager.create_agent_pod()` into `create_agent_run()`, add a background reconciler that watches pod phase and drives `AgentRun.state` transitions, enforce a state transition guard matrix at the service layer, and connect the `agent logs`/`agent attach` CLI stubs to the existing `K8sManager.get_pod_logs()`/`exec_in_pod()` methods.

**Rationale:** This is the entire value proposition of mob. Every model, route, and infra component exists to support pod-based agent execution — which currently doesn't happen. `create_agent_run` writes a DB row in PENDING and stops. `K8sManager` is fully implemented but imported by nothing in the service layer. Runs sit in PENDING forever with no pod, no logs, no observable behavior.

**Downsides:** Large surface area — touches services, K8s layer, CLI, and requires deciding between callback-based vs watch-based reconciliation. The reconciler introduces a background process that needs lifecycle management.

**Confidence:** 95%
**Complexity:** High
**Status:** Unexplored

### 2. Bootstrap Alembic Migrations

**Description:** Run `alembic init`, generate the initial migration from existing models, replace `Base.metadata.create_all` in the app lifespan and CLI with `alembic upgrade head`. Add an init-container to the dev Kind overlay for automatic migration on deploy.

**Rationale:** `create_all` doesn't ALTER existing tables — the first schema change will silently leave existing databases with a stale schema, producing cryptic SQLAlchemy errors at query time. Alembic is already a production dependency (`>=1.13.0`) but was never initialized. Starting now when the schema is young means zero migration debt.

**Downsides:** Small upfront effort. Requires discipline to generate migrations for every future schema change.

**Confidence:** 90%
**Complexity:** Low
**Status:** Unexplored

### 3. Fix Dev Toolchain + CI Pipeline

**Description:** Add flake8/mypy/black (or consolidate to ruff + mypy) to `pyproject.toml` dev dependencies so `make lint` and `make format` work on a clean checkout. Create a GitHub Actions workflow running lint + test on every push/PR.

**Rationale:** `make lint` fails immediately on a fresh clone because the tools aren't installed. The test suite has thorough unit tests for every API resource plus integration tests — but they only run when a developer manually invokes `make test`. Without CI, broken builds merge silently and the existing test infrastructure is wasted value.

**Downsides:** Minimal — standard infrastructure work. May surface existing lint violations that need a cleanup pass.

**Confidence:** 95%
**Complexity:** Low
**Status:** Unexplored

### 4. Unify CLI Backend Architecture

**Description:** Eliminate the 300-line hand-rolled regex router in `local_backend.py` — either by using `httpx.AsyncClient(transport=ASGITransport(app=app))` (pattern already proven in `tests/conftest.py`) or by extracting a typed `Backend` protocol with `LocalBackend` (direct service calls) and `RemoteBackend` (HTTP). Fix the `asyncio.run()` per-command pattern that creates and destroys the event loop on every CLI invocation.

**Rationale:** The regex router is already diverging from FastAPI routes (missing task DELETE, no AgentSendMessage handler). Every new endpoint must be manually duplicated. The `asyncio.run()` pattern compounds this by re-initializing DB connections on every call. `conftest.py` already demonstrates the ASGITransport approach that would eliminate the duplication entirely.

**Downsides:** Requires choosing an approach. ASGITransport is elegant but changes how local mode initializes. A Backend protocol is more explicit but more code.

**Confidence:** 85%
**Complexity:** Medium
**Status:** Unexplored

### 5. Make Skills Runtime-Effective

**Description:** When launching agent pods, query `AgentSkill` associations, serialize `skills_md` content, and inject it into the pod as ConfigMap volumes or environment variables. Currently skills are stored in the DB but never reach running containers — `K8sManager.create_agent_pod()` accepts only `system_prompt`, `model_endpoint`, and `env_vars` with no skills parameter.

**Rationale:** Skills are the only compositional unit for varying agent behavior without rebuilding images. The `AgentSkill` join table, CRUD API, and CLI all exist and work — but the data is purely decorative with zero runtime effect. Should ship alongside #1 to avoid touching K8sManager twice.

**Downsides:** Requires deciding the injection mechanism (env vars vs ConfigMap volumes vs startup API call). Large skill documents may exceed env var limits.

**Confidence:** 80%
**Complexity:** Medium
**Status:** Unexplored

### 6. Complete the CLI Surface

**Description:** Add the missing `tasks` command group to the CLI (tasks have a full API, service, model, and schema but zero CLI presence — `main.py` registers no task commands). Fix `services/agents.py:send_message()` which returns `{"status": "sent"}` without doing anything — either implement actual pod communication or raise `NotImplementedError` with a clear message.

**Rationale:** Tasks are a first-class domain object representing the work agents execute. Omitting them from the CLI makes the tool feel incomplete on first use. The `send_message` stub is worse — it silently fakes success, which is a broken user-facing contract that erodes trust.

**Downsides:** Straightforward work. The tasks CLI follows existing patterns exactly. `send_message` implementation depends on deciding the pod communication protocol.

**Confidence:** 90%
**Complexity:** Low
**Status:** Unexplored

### 7. Agent Runtime Entrypoint

**Description:** Add a `mob agent-entrypoint` subcommand that runs inside agent pods — polls for tasks via the remote API, executes work, and reports state transitions back to the control plane. This makes `mob` itself the agent binary rather than requiring separate unvalidated Docker images specified via the opaque `agent_template` string field.

**Rationale:** Currently `agent_template` is a `String(500)` with no connection to anything in the codebase. `K8sManager` passes it as the pod image but nothing validates it. If mob is the agent runtime, the control plane and agents share the same binary, the existing Dockerfile works as-is, and the `AGENT_RUN_ID` env var already injected into pods has a consumer.

**Downsides:** Bold architectural bet that limits agent image flexibility. Requires the core loop (#1) to be working first. May constrain future multi-language agent support.

**Confidence:** 65%
**Complexity:** High
**Status:** Unexplored

## Rejection Summary

| # | Idea | Reason Rejected |
|---|------|-----------------|
| 1 | Implement auth module (Keycloak/JWT) | Premature — no real users or tenants; heavy integration for a 5-commit project |
| 2 | Add pagination to list endpoints | Zero production traffic; premature optimization |
| 3 | Agent template registry/validation | Simple format validation suffices; full registry is pre-product |
| 4 | AgentRun event log (state history table) | Blocked by Alembic bootstrap; no consumers exist yet |
| 5 | Per-agent resource profiles | Hardcoded defaults are fine until real workloads prove otherwise |
| 6 | Structured definition_of_done | Product design question requiring an LLM evaluation protocol that doesn't exist |
| 7 | Auto-migration in dev rebuild | Trivial follow-on once Alembic is bootstrapped; not standalone |
| 8 | Tenant isolation at query layer | No auth, no tenants, no data; add org-scoping when auth lands |

## Session Log

- 2026-03-23: Initial open-ended ideation — 48 raw ideas generated across 6 sub-agents, deduped to 21 unique candidates, 7 survived adversarial filtering
