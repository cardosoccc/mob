---
title: "refactor: Rename agent-run/agent-runs to session/sessions"
type: refactor
status: completed
date: 2026-03-27
---

# refactor: Rename agent-run/agent-runs to session/sessions

## Overview

Rename all references to `agent-run` and `agent-runs` to `session` and `sessions` across the entire codebase — CLI commands, Python models, Pydantic schemas, service layer, API routes, Rust Kubernetes operator, CRD definitions, RBAC manifests, environment variables, K8s labels/finalizers, tests, and documentation. After completion, zero references to the old names should remain.

## Problem Statement / Motivation

The current naming (`agent-run`) is verbose and doesn't match the evolving mental model of the platform. `session` is shorter, clearer, and more intuitive for users interacting with the CLI and API.

## Naming Decisions

These decisions must be locked before implementation begins:

| Context | Old Name | New Name |
|---------|----------|----------|
| Python model class | `AgentRun` | `Session` |
| Python state enum | `AgentRunState` | `SessionState` |
| DB table | `agent_runs` | `sessions` |
| Python module files | `agent_run.py`, `agent_runs.py` | `session.py`, `sessions.py` |
| Python functions | `create_agent_run()`, `list_agent_runs()`, etc. | `create_session()`, `list_sessions()`, etc. |
| Pydantic schemas | `AgentRunCreate`, `AgentRunResponse`, `AgentRunSendMessage` | `SessionCreate`, `SessionResponse`, `SessionSendMessage` |
| CLI commands | `mob agent-run`, `mob agent-runs` | `mob session`, `mob sessions` |
| API prefix | `/api/v1/agent-runs` | `/api/v1/sessions` |
| API tag | `"agent-runs"` | `"sessions"` |
| Local backend routes | `/agent-runs` patterns | `/sessions` patterns |
| Resolver resource key | `"agent_run"` | `"session"` |
| Resolver list path | `"/agent-runs"` | `"/sessions"` |
| Rust CRD kind | `AgentRun` | `Session` |
| Rust CRD structs | `AgentRunSpec`, `AgentRunStatus` | `SessionSpec`, `SessionStatus` |
| Rust module files | `agent_run.rs`, `agent_run_controller.rs` | `session.rs`, `session_controller.rs` |
| K8s CRD name | `agentruns.mob.io` | `sessions.mob.io` |
| K8s CRD plural | `agentruns` | `sessions` |
| K8s CRD singular | `agentrun` | `session` |
| K8s CRD shortname | `ar` | `sess` |
| K8s CRD YAML file | `crds/agentrun.yaml` | `crds/session.yaml` |
| CR name prefix | `ar-{id[:8]}` | `s-{id[:8]}` |
| K8s label | `mob.io/agent-run` | `mob.io/session` |
| K8s finalizer | `mob.io/agent-run-cleanup` | `mob.io/session-cleanup` |
| Env var | `AGENT_RUN_ID` | `SESSION_ID` |
| RBAC resources | `agentruns`, `agentruns/status`, `agentruns/finalizers` | `sessions`, `sessions/status`, `sessions/finalizers` |
| Relationship on `Task` | `task.agent_run` | `task.session` |
| Relationship on `Agent` | `agent.runs` | `agent.sessions` |
| Pod name pattern | `mob-agent-ar-XXXXXXXX` | `mob-agent-s-XXXXXXXX` |

**Unchanged:**
- `mob.io/agent-state` annotation — refers to the agent process state, not the session entity
- `mob.io/agent-name` label — refers to the agent, not the session
- `AGENT_NAME`, `AGENT_SYSTEM_PROMPT`, `AGENT_POD_NAME`, `AGENT_NAMESPACE` env vars — agent-specific, not session-specific

**SQLAlchemy `Session` collision note:** The model class can safely be named `Session` because the codebase universally imports `AsyncSession` from SQLAlchemy, never bare `Session`. No collision exists.

## Technical Approach

### Architecture

This is a mechanical rename with no behavioral changes. The execution order matters to keep the codebase buildable at each phase. The Python side and Rust side can be done in parallel since they don't share compilation, but they share the K8s CRD contract.

### Implementation Phases

#### Phase 1: Database Layer (Python models + migration)

**Files to modify:**

1. **Rename file** `src/mob/models/agent_run.py` → `src/mob/models/session.py`
   - `AgentRunState` → `SessionState`
   - `AgentRun` → `Session`
   - `__tablename__ = "agent_runs"` → `__tablename__ = "sessions"`
   - Update `__repr__` to `<Session(...)>`
   - Update `back_populates` references

2. **`src/mob/models/__init__.py`** — Update imports from `session` module, export `Session`, `SessionState`

3. **`src/mob/models/agent.py`** — Rename `runs` relationship to `sessions`, update `back_populates="agent"` (stays same), update type annotation from `AgentRun` to `Session`

4. **`src/mob/models/task.py`** — Rename `agent_run` relationship to `session`, update `back_populates` from `"agent_run"` to `"session"`, update type annotation

5. **`src/mob/database.py`** — Add `_rename_agent_runs_table()` function:
   ```python
   async def _rename_agent_runs_table(engine):
       """Rename legacy agent_runs table to sessions."""
       async with engine.begin() as conn:
           # Check if old table exists and new doesn't
           if engine.url.drivername.startswith("sqlite"):
               result = await conn.execute(text(
                   "SELECT name FROM sqlite_master WHERE type='table' AND name='agent_runs'"
               ))
           else:
               result = await conn.execute(text(
                   "SELECT tablename FROM pg_tables WHERE tablename='agent_runs'"
               ))
           if result.first():
               await conn.execute(text("ALTER TABLE agent_runs RENAME TO sessions"))
   ```
   Call this before `create_all` in `init_db()`.

**Success criteria:**
- [ ] `Session` model maps to `sessions` table
- [ ] `SessionState` enum works identically to old `AgentRunState`
- [ ] Existing `agent_runs` table gets renamed on startup
- [ ] `Agent.sessions` and `Task.session` relationships work
- [ ] `models/__init__.py` exports `Session`, `SessionState`

---

#### Phase 2: Pydantic Schemas

**Files to modify:**

1. **`src/mob/schemas.py`**
   - `AgentRunCreate` → `SessionCreate`
   - `AgentRunResponse` → `SessionResponse`
   - `AgentRunSendMessage` → `SessionSendMessage`

**Success criteria:**
- [ ] All schema classes renamed
- [ ] Validation rules unchanged

---

#### Phase 3: Service Layer

**Files to modify:**

1. **Rename file** `src/mob/services/agent_runs.py` → `src/mob/services/sessions.py`
   - All function names: `list_agent_runs` → `list_sessions`, `create_agent_run` → `create_session`, `get_agent_run` → `get_session`, `stop_agent_run` → `stop_session`, `update_agent_run_state` → `update_session_state`, `send_message` (stays), `get_agent_run_live_status` → `get_session_live_status`, `get_agent_run_live_status_sync` → `get_session_live_status_sync`
   - Internal helpers: `_enrich_runs_with_live_state` → `_enrich_sessions_with_live_state`, `_list_cr_statuses_sync` (stays — describes CR, not session), `_get_single_cr_status_sync` (stays), `_send_via_port_forward` (stays), `_get_pod_ip_sync` (stays)
   - CR name prefix: `f"ar-{run_id[:8]}"` → `f"s-{run_id[:8]}"` (affects lines ~112, 196-200, 219, 279, 298, 328, 330)
   - K8s CRD plural: `plural="agentruns"` → `plural="sessions"` in all `_k8s_custom_api` calls
   - Variable names: `run` → `session` (or `sess` where short), `run_id` → `session_id`, `runs` → `sessions`
   - Import updates: `from mob.models.session import Session, SessionState`
   - Schema imports: `SessionCreate`, `SessionResponse`

2. **`src/mob/services/__init__.py`** (if exists) — Update any re-exports

**Success criteria:**
- [ ] All service functions renamed
- [ ] CR name prefix changed to `s-`
- [ ] K8s API calls use `plural="sessions"`
- [ ] All imports updated

---

#### Phase 4: API Routes

**Files to modify:**

1. **Rename file** `src/mob/api/routes/agent_runs.py` → `src/mob/api/routes/sessions.py`
   - Import: `from mob.services import sessions as session_service`
   - All handler functions: `list_agent_runs` → `list_sessions`, `create_agent_run` → `create_session`, `get_agent_run` → `get_session`, `get_agent_run_logs` → `get_session_logs`, `stop_agent_run` → `stop_session`, `update_agent_run_state` → `update_session_state`, `send_to_agent_run` → `send_to_session`
   - Service call names updated to match Phase 3

2. **`src/mob/api/app.py`**
   - Import: `from mob.api.routes import sessions`
   - Router registration: `prefix="/api/v1/sessions"`, `tags=["sessions"]`

**Success criteria:**
- [ ] All API endpoints serve at `/api/v1/sessions`
- [ ] Route handler names updated
- [ ] OpenAPI tag changed to `"sessions"`

---

#### Phase 5: CLI Layer

**Files to modify:**

1. **Rename file** `src/mob/cli/commands/agent_run.py` → `src/mob/cli/commands/session.py`
   - `@click.command("agent-runs")` → `@click.command("sessions")`
   - `def agent_runs(...)` → `def sessions(...)`
   - `@click.group("agent-run")` → `@click.group("session")`
   - `def agent_run(...)` → `def session(...)`
   - All `resolve_ref("agent_run", ref)` → `resolve_ref("session", ref)`
   - All `api_get("/agent-runs")` → `api_get("/sessions")`
   - All `api_post("/agent-runs/...")` → `api_post("/sessions/...")`
   - All help text and display strings updated

2. **`src/mob/cli/main.py`**
   - Import: `from mob.cli.commands.session import session, sessions`
   - `cli.add_command(sessions)`
   - `cli.add_command(session)`

3. **`src/mob/cli/resolver.py`**
   - Resource config: `"session": ("/sessions", "name", "agent_id")`
   - Remove old `"agent_run"` entry

4. **`src/mob/cli/local_backend.py`**
   - Import: `from mob.services import sessions as session_svc`
   - All route patterns: `/agent-runs` → `/sessions` in string literals and regexes
   - Service calls: `run_svc.list_agent_runs` → `session_svc.list_sessions`, etc.

5. **`src/mob/cli/commands/agent.py`**
   - `agent_run_cmd` function → `agent_run_cmd` can stay (it's the `mob agent run` command that creates a session)
   - `api_post("/agent-runs", payload)` → `api_post("/sessions", payload)`
   - Display text: any "agent run" strings → "session"

**Success criteria:**
- [ ] `mob session show/stop/logs/send` works
- [ ] `mob sessions` lists sessions
- [ ] `mob agent run` creates a session via `/sessions` API
- [ ] Local backend routes work for all session paths
- [ ] Resolver resolves `"session"` resource type

---

#### Phase 6: Agent Pod (Python)

**Files to modify:**

1. **`src/mob/agent/entrypoint.py`**
   - `AGENT_RUN_ID = os.environ.get("AGENT_RUN_ID", "unknown")` → `SESSION_ID = os.environ.get("SESSION_ID", "unknown")`
   - Update all references and log messages

**Success criteria:**
- [ ] Agent reads `SESSION_ID` from environment
- [ ] Logging uses `SESSION_ID`

---

#### Phase 7: K8s Manager (Legacy)

**Files to modify:**

1. **`src/mob/k8s/manager.py`**
   - Env var: `AGENT_RUN_ID` → `SESSION_ID`
   - Label: `mob.io/agent-run` → `mob.io/session`

**Success criteria:**
- [ ] Pod creation uses new env var and label names

---

#### Phase 8: Rust Kubernetes Operator

**Files to modify:**

1. **Rename file** `operator/src/crd/agent_run.rs` → `operator/src/crd/session.rs`
   - CRD kind: `"AgentRun"` → `"Session"`
   - CRD group: `mob.io` (unchanged)
   - CRD plural: `agentruns` → `sessions`
   - CRD singular: `agentrun` → `session`
   - CRD shortname: `ar` → `sess`
   - Struct renames: `AgentRunSpec` → `SessionSpec`, `AgentRunStatus` → `SessionStatus`, `AgentRun` → `Session`

2. **`operator/src/crd/mod.rs`**
   - `pub mod session;`
   - `pub use session::{Session, SessionSpec, SessionStatus};`

3. **Rename file** `operator/src/controller/agent_run_controller.rs` → `operator/src/controller/session_controller.rs`
   - Finalizer: `"mob.io/agent-run-cleanup"` → `"mob.io/session-cleanup"`
   - All `AgentRun` type references → `Session`
   - Variable names: `ar` → `sess` or `session`
   - Status type references: `AgentRunStatus` → `SessionStatus`

4. **`operator/src/controller/mod.rs`**
   - `pub mod session_controller;`
   - `pub use session_controller::{reconcile, error_policy, Context};`

5. **`operator/src/resources/pod.rs`**
   - Env var: `"AGENT_RUN_ID"` → `"SESSION_ID"`
   - Label: `"mob.io/agent-run"` → `"mob.io/session"`
   - Type references: `AgentRun` → `Session`, `AgentRunStatus` → `SessionStatus`
   - Import paths updated

6. **`operator/src/main.rs`**
   - CRD registration: `"agentruns.mob.io"` → `"sessions.mob.io"`
   - API type: `Api::<Session>`
   - Controller name (if any)
   - Import paths updated

7. **`operator/src/error.rs`** — Update any type references if present

**Success criteria:**
- [ ] `cargo build` succeeds
- [ ] `cargo test` passes
- [ ] CRD generates as `sessions.mob.io` with kind `Session`
- [ ] Operator watches `Session` CRs
- [ ] Pods created with `SESSION_ID` env var and `mob.io/session` label
- [ ] Finalizer uses `mob.io/session-cleanup`

---

#### Phase 9: Kubernetes Manifests

**Files to modify:**

1. **Rename file** `deploy/base/crds/agentrun.yaml` → `deploy/base/crds/session.yaml`
   - CRD name: `sessions.mob.io`
   - Kind: `Session`
   - ListKind: `SessionList`
   - Plural: `sessions`
   - Singular: `session`
   - Shortnames: `[sess]`
   - All spec/status field names stay (they're camelCase JSON: `agentId`, `agentName`, etc. — these refer to the agent, not the session)

2. **`deploy/base/kustomization.yaml`**
   - `crds/agentrun.yaml` → `crds/session.yaml`

3. **`deploy/base/api-rbac.yaml`**
   - Resources: `["agentruns"]` → `["sessions"]`
   - `agentruns/status` → `sessions/status`

4. **`deploy/base/operator/rbac.yaml`**
   - Resources: `["agentruns"]` → `["sessions"]`
   - `agentruns/status` → `sessions/status`
   - `agentruns/finalizers` → `sessions/finalizers`

**Success criteria:**
- [ ] `kubectl apply` of CRD creates `sessions.mob.io`
- [ ] RBAC allows API and operator to manage `sessions` resources
- [ ] `kubectl get sess` works (shortname)

---

#### Phase 10: Tests

**Files to modify:**

1. **Rename file** `tests/unit/test_api_agent_runs.py` → `tests/unit/test_api_sessions.py`
   - All function names: `test_create_agent_run` → `test_create_session`, etc.
   - API paths: `/api/v1/agent-runs` → `/api/v1/sessions`
   - Mock paths: `mob.services.agent_runs` → `mob.services.sessions`
   - Schema references: `AgentRunCreate` → `SessionCreate`, etc.
   - Model references: `AgentRun` → `Session`, `AgentRunState` → `SessionState`

2. **`tests/unit/test_models.py`**
   - Import: `from mob.models.session import Session, SessionState`
   - Function names: `test_create_agent_run` → `test_create_session`, `test_agent_run_states` → `test_session_states`
   - Variable names and assertions updated

3. **`tests/unit/test_resolver.py`**
   - `AGENT_RUNS` fixture → `SESSIONS`
   - `TestAgentRunResolution` → `TestSessionResolution`
   - `resolve_ref("agent_run", ...)` → `resolve_ref("session", ...)`
   - Test method names: `test_agent_run_by_name` → `test_session_by_name`, etc.

4. **`tests/unit/test_send_message_routing.py`**
   - Import: `from mob.services.sessions import ...`

5. **`tests/integration/test_cli_integration.py`**
   - `test_agent_run_lifecycle` → `test_session_lifecycle`
   - CLI invocations: `["agent-runs"]` → `["sessions"]`, `["agent-run", "show", ...]` → `["session", "show", ...]`

6. **Rust tests in `operator/src/resources/pod.rs`**
   - Update type references and assertions for `SESSION_ID` env var

**Success criteria:**
- [ ] `uv run pytest` passes all tests
- [ ] `cargo test` passes all Rust tests
- [ ] No test references old names

---

#### Phase 11: Documentation & Scripts

**Files to modify:**

1. **`README.md`** — All command examples and references
2. **`scripts/local-setup.sh`** — Documentation strings
3. **`BIGBANG.md`** — Domain model references
4. **`docs/ideation/2026-03-23-open-ideation.md`** — Domain references
5. **`docs/solutions/database-issues/sqlite-schema-evolution-missing-columns.md`** — Table name references
6. **`docs/solutions/integration-issues/pydantic-ai-agent-image-k8s-orchestration.md`** — Architecture references
7. **Existing plan files** in `docs/plans/` — These are historical documents; update only if they contain active guidance that would mislead future readers

**Success criteria:**
- [ ] `grep -r "agent.run" --include="*.md" --include="*.sh"` returns zero results (excluding `docs/plans/` historical files and this plan itself)

---

#### Phase 12: Final Verification

Run a comprehensive codebase-wide search for any remaining references:

```bash
# Must return zero results (excluding .venv, operator/target, docs/plans/ historical files)
grep -rn "agent.run\|agent_run\|AgentRun\|AGENT_RUN\|agentruns\|agentrun" \
  --include="*.py" --include="*.rs" --include="*.yaml" --include="*.yml" \
  --include="*.toml" --include="*.sh" --include="*.json" \
  --exclude-dir=.venv --exclude-dir=target \
  src/ operator/src/ deploy/ tests/ scripts/
```

**Success criteria:**
- [ ] Zero matches in source code, tests, deploy manifests, and scripts
- [ ] `uv run pytest` passes
- [ ] `cargo build && cargo test` passes
- [ ] `mob sessions` works in local mode
- [ ] `mob session show` works in local mode

## System-Wide Impact

### Interaction Graph

CLI command → resolver (`"session"`) → client (`/sessions`) → API route (`/api/v1/sessions`) → service (`sessions.create_session`) → DB (`sessions` table) + K8s API (`sessions.mob.io` CR). Operator watches `Session` CRs → creates pods with `SESSION_ID` env var → agent reads `SESSION_ID` → annotates pod with `mob.io/agent-state` → operator reads annotation → updates CR status → service enriches DB state from CR status.

### Error Propagation

No change in error handling — this is a pure rename. All error paths remain identical.

### State Lifecycle Risks

- **Database:** The `_rename_agent_runs_table()` migration must run before `create_all()` to prevent creating a duplicate empty `sessions` table while `agent_runs` still holds data.
- **K8s CRDs:** Existing `AgentRun` CRs in deployed clusters will be orphaned when the old CRD is replaced. For dev/local clusters, tear down and recreate. For production, a two-phase migration would be needed (out of scope for this refactor — this is an early-stage project).

### API Surface Parity

- CLI `mob session *` and `mob sessions` — mirrors API
- API `/api/v1/sessions` — mirrors service layer
- Local backend `/sessions` — mirrors API paths
- All three surfaces update together in this refactor

### Integration Test Scenarios

1. `mob sessions` → lists sessions from DB (local mode)
2. `mob agent run <ref>` → creates session via `POST /sessions` → operator creates pod with `SESSION_ID`
3. `mob session show <ref>` → resolves by name → `GET /sessions/{id}` → enriches with CR status
4. `mob session send <ref> --message "test"` → routes to agent pod → agent processes message
5. `mob session stop <ref>` → deletes CR with `mob.io/session-cleanup` finalizer → pod cleaned up

## Acceptance Criteria

### Functional Requirements

- [ ] All CLI commands use `session`/`sessions` naming
- [ ] All API endpoints serve at `/api/v1/sessions`
- [ ] Database table is `sessions`
- [ ] K8s CRD is `sessions.mob.io` with kind `Session`
- [ ] Rust operator compiles and manages `Session` CRs
- [ ] Agent pods receive `SESSION_ID` env var
- [ ] Pods labeled with `mob.io/session`
- [ ] Existing `agent_runs` table auto-renames to `sessions` on startup

### Non-Functional Requirements

- [ ] Zero references to old names in source code, tests, deploy manifests
- [ ] All Python tests pass
- [ ] All Rust tests pass
- [ ] No behavioral changes — only naming changes

### Quality Gates

- [ ] `grep` verification returns zero old-name matches
- [ ] `uv run pytest` green
- [ ] `cargo build && cargo test` green

## Dependencies & Risks

- **No Alembic:** The table rename relies on a custom migration function in `database.py`. This is adequate for SQLite and PostgreSQL `ALTER TABLE RENAME`.
- **K8s cluster state:** Existing clusters with `AgentRun` CRs must be torn down and recreated. This is acceptable for dev/local environments.
- **Running agent pods:** After deployment, all running agent pods must be restarted to pick up the `SESSION_ID` env var (replacing `AGENT_RUN_ID`).

## Sources & References

### Internal References

- Model: `src/mob/models/agent_run.py`
- Service: `src/mob/services/agent_runs.py`
- API routes: `src/mob/api/routes/agent_runs.py`
- CLI commands: `src/mob/cli/commands/agent_run.py`
- Rust CRD: `operator/src/crd/agent_run.rs`
- Rust controller: `operator/src/controller/agent_run_controller.rs`
- Rust pod builder: `operator/src/resources/pod.rs`
- K8s CRD manifest: `deploy/base/crds/agentrun.yaml`
- Database init: `src/mob/database.py`
- Learnings: `docs/solutions/database-issues/sqlite-schema-evolution-missing-columns.md` — documents that `_add_missing_columns` cannot handle table renames
