---
title: "feat: Add agent-runs list and agent-run command group"
type: feat
status: completed
date: 2026-03-24
---

# feat: Add `agent-runs` list and `agent-run` command group

## Overview

Restructure agent run CLI commands to follow the established plural/singular pattern used by every other resource. Add a `name` field to agent runs for human-friendly referencing. Move run-lifecycle subcommands (`stop`, `logs`, `attach`, `send`) from the `agent` group into a new `agent-run` group that accepts run REFs (name, position, or UUID).

## Problem Statement / Motivation

Currently, run-lifecycle commands (`stop`, `logs`, `attach`, `send`) live under the `agent` group and accept raw UUIDs — they are the only commands in the CLI that bypass the resolver pattern. There is no `agent-runs` list command, so users cannot discover runs or use positional references. This breaks the consistency of the CLI and makes agent runs harder to work with than every other resource.

## Proposed Solution

1. Add a `name` field to the `AgentRun` model (auto-generated as `{agent_name}-{random_8_char}`).
2. Create `mob agent-runs` — list command with `--agent` and `--state` filters.
3. Create `mob agent-run` — command group with `show`, `stop`, `logs`, `attach`, `send` subcommands, all accepting a REF argument resolved via the existing resolver.
4. Move `send` endpoint from `POST /agents/{id}/send` to `POST /agent-runs/{id}/send` (the run already carries the `agent_id`).
5. Remove `stop`, `logs`, `attach`, `send` from the `agent` group.
6. Keep `mob agent run REF` where it is (creating a run is an agent action), add `--name` option.

### UX After Implementation

```
# List runs (with filters)
mob agent-runs
mob agent-runs --agent my-agent
mob agent-runs --state idle

# Create a run (stays under agent)
mob agent run my-agent
mob agent run my-agent --name my-custom-run

# Operate on runs (new agent-run group)
mob agent-run show my-agent-a3f8b2c1
mob agent-run stop 1                      # positional from agent-runs list
mob agent-run logs my-run --tail 50
mob agent-run attach my-run
mob agent-run send my-run --message "do X"
```

## Technical Approach

### Phase 1: Model & Schema Changes

**Add `name` field to AgentRun model**

`src/mob/models/agent_run.py`:
```python
name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
```

- Globally unique constraint (8-char random suffix gives ~4 billion combinations per agent name prefix)
- Not nullable — every run gets a name

**Update Pydantic schemas**

`src/mob/schemas.py`:
```python
class AgentRunCreate(BaseModel):
    agent_id: str
    task_id: str | None = None
    name: str | None = None  # optional, auto-generated if omitted

class AgentRunResponse(BaseModel):
    id: str
    name: str  # add
    agent_id: str
    state: str
    pod_name: str | None
    task_id: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
```

**Update service layer to generate default name**

`src/mob/services/agent_runs.py` — `create_agent_run()`:
```python
import secrets

async def create_agent_run(
    session: AsyncSession, agent_id: str, task_id: str | None = None, name: str | None = None
) -> AgentRun:
    agent = await session.get(Agent, agent_id)
    if not agent:
        raise ServiceError("Agent not found", 404)

    if not name:
        suffix = secrets.token_hex(4)  # 8 hex chars
        name = f"{agent.name}-{suffix}"

    run = AgentRun(
        agent_id=agent_id,
        name=name,
        state=AgentRunState.PENDING,
        task_id=task_id,
    )
    # ... rest unchanged
```

**Files touched:**
- `src/mob/models/agent_run.py` — add `name` column
- `src/mob/schemas.py` — update `AgentRunCreate`, `AgentRunResponse`
- `src/mob/services/agent_runs.py` — add `name` param, auto-generation logic

### Phase 2: API & Local Backend Changes

**Move send endpoint from agents to agent-runs**

`src/mob/api/routes/agent_runs.py` — add:
```python
@router.post("/{run_id}/send")
async def send_to_agent_run(run_id: str, data: AgentRunSendMessage, session=Depends(get_session)):
    # resolve agent_id from run, delegate to service
```

**Add state filter to list endpoint**

`src/mob/api/routes/agent_runs.py`:
```python
@router.get("", response_model=list[AgentRunResponse])
async def list_agent_runs(
    agent_id: str | None = None,
    state: str | None = None,  # add
    session: AsyncSession = Depends(get_session)
):
```

`src/mob/services/agent_runs.py` — `list_agent_runs()`:
```python
async def list_agent_runs(
    session: AsyncSession, agent_id: str | None = None, state: str | None = None
) -> list[AgentRun]:
    query = select(AgentRun).order_by(AgentRun.created_at.desc())
    if agent_id:
        query = query.where(AgentRun.agent_id == agent_id)
    if state:
        query = query.where(AgentRun.state == AgentRunState(state))
    # ...
```

**Update local backend**

`src/mob/cli/local_backend.py`:
- Update `POST /agent-runs` to pass `name` from data
- Add route for `POST /agent-runs/{run_id}/send`
- Remove route for `POST /agents/{agent_id}/send`
- Pass `state` param through to `list_agent_runs`

**Update schema for send**

`src/mob/schemas.py` — replace `AgentSendMessage`:
```python
class AgentRunSendMessage(BaseModel):
    message: str = Field(..., min_length=1)
```

(Drop `run_id` field — it's now a path parameter, and drop the old `AgentSendMessage`)

**Files touched:**
- `src/mob/api/routes/agent_runs.py` — add send route, state filter
- `src/mob/services/agent_runs.py` — add state filter to list, add name to create
- `src/mob/cli/local_backend.py` — update routes
- `src/mob/schemas.py` — new `AgentRunSendMessage`, remove old `AgentSendMessage`

### Phase 3: CLI Commands & Resolver

**Add `agent_run` to resolver config**

`src/mob/cli/resolver.py`:
```python
_RESOURCE_CONFIG: dict[str, tuple[str, str, str | None]] = {
    # ... existing entries ...
    "agent_run": ("/agent-runs", "name", "agent_id"),
}
```

Add filter decorator:
```python
def agent_run_filters(fn):
    """Shared filter options for agent-run-scoped commands."""
    fn = click.option("--agent", "agent_id", help="Filter by agent (name or position)")(fn)
    return fn
```

Note: The `--agent` option on `agent-run` subcommands accepts a REF that gets resolved via the agent resolver before being passed as `agent_id` to the agent-run resolver.

**Create new command file**

`src/mob/cli/commands/agent_run.py`:
```python
@click.command("agent-runs")
@click.option("--agent", "agent_ref", help="Filter by agent (name or position)")
@agent_filters  # for --domain to scope agent resolution
@click.option("--state", help="Filter by state (pending, starting, idle, busy, finished, failed)")
def agent_runs(agent_ref, domain_id, state):
    """List agent runs."""
    params = {}
    if agent_ref:
        agent_id = resolve_ref("agent", agent_ref, domain_id=domain_id)
        params["agent_id"] = agent_id
    if state:
        params["state"] = state
    data = api_get("/agent-runs", params=params)
    print_table(data, columns=["id", "name", "agent_id", "state", "pod_name", "created_at"])


@click.group("agent-run")
def agent_run():
    """Manage agent runs."""
    pass


@agent_run.command("show")
@click.argument("ref")
@click.option("--agent", "agent_ref", help="Scope by agent (name or position)")
@agent_filters
def agent_run_show(ref, agent_ref, domain_id):
    """Show details of an agent run. REF is a name or position number."""
    agent_id = _resolve_agent_filter(agent_ref, domain_id)
    run_id = resolve_ref("agent_run", ref, agent_id=agent_id)
    data = api_get(f"/agent-runs/{run_id}")
    print_detail(data)


@agent_run.command("stop")
@click.argument("ref")
@click.option("--agent", "agent_ref", help="Scope by agent (name or position)")
@agent_filters
def agent_run_stop(ref, agent_ref, domain_id):
    """Stop a running agent instance. REF is a name or position number."""
    agent_id = _resolve_agent_filter(agent_ref, domain_id)
    run_id = resolve_ref("agent_run", ref, agent_id=agent_id)
    data = api_post(f"/agent-runs/{run_id}/stop")
    print_success(f"Agent run stopped.")
    print_detail(data)


@agent_run.command("logs")
@click.argument("ref")
@click.option("--agent", "agent_ref", help="Scope by agent (name or position)")
@agent_filters
@click.option("--tail", default=100, help="Number of log lines")
def agent_run_logs(ref, agent_ref, domain_id, tail):
    """Show logs of an agent run. REF is a name or position number."""
    agent_id = _resolve_agent_filter(agent_ref, domain_id)
    run_id = resolve_ref("agent_run", ref, agent_id=agent_id)
    data = api_get(f"/agent-runs/{run_id}/logs", params={"tail": tail})
    # ... same display logic as current agent_logs


@agent_run.command("attach")
@click.argument("ref")
@click.option("--agent", "agent_ref", help="Scope by agent (name or position)")
@agent_filters
def agent_run_attach(ref, agent_ref, domain_id):
    """Attach to an agent run's pod (not yet implemented). REF is a name or position number."""
    click.echo("Error: Interactive attach is not yet implemented.", err=True)
    raise SystemExit(1)


@agent_run.command("send")
@click.argument("ref")
@click.option("--agent", "agent_ref", help="Scope by agent (name or position)")
@agent_filters
@click.option("--message", required=True, help="Message to send")
def agent_run_send(ref, agent_ref, domain_id, message):
    """Send a message to a running agent. REF is a name or position number."""
    agent_id = _resolve_agent_filter(agent_ref, domain_id)
    run_id = resolve_ref("agent_run", ref, agent_id=agent_id)
    data = api_post(f"/agent-runs/{run_id}/send", {"message": message})
    print_success("Message sent.")


def _resolve_agent_filter(agent_ref, domain_id):
    """Resolve optional --agent filter to agent_id, or return None."""
    if agent_ref:
        return resolve_ref("agent", agent_ref, domain_id=domain_id)
    return None
```

**Update `agent run` to accept `--name`**

`src/mob/cli/commands/agent.py`:
```python
@agent.command("run")
@click.argument("ref")
@agent_filters
@click.option("--task", "task_id", help="Task ID to associate with the run")
@click.option("--name", "run_name", help="Custom name for the run (default: agent-name + random suffix)")
def agent_run(ref, domain_id, task_id, run_name):
    agent_id = resolve_ref("agent", ref, domain_id=domain_id)
    payload = {"agent_id": agent_id}
    if task_id:
        payload["task_id"] = task_id
    if run_name:
        payload["name"] = run_name
    data = api_post("/agent-runs", payload)
    print_success(f"Agent run '{data['name']}' created (state: {data['state']}).")
    print_detail(data)
```

**Remove old subcommands from `agent` group**

Remove `agent_stop`, `agent_logs`, `agent_attach`, `agent_send` from `src/mob/cli/commands/agent.py`.

**Register new commands in main.py**

`src/mob/cli/main.py`:
```python
from mob.cli.commands.agent_run import agent_run, agent_runs

cli.add_command(agent_runs)
cli.add_command(agent_run)
```

**Files touched:**
- `src/mob/cli/commands/agent_run.py` — **new file**
- `src/mob/cli/commands/agent.py` — add `--name` to `run`, remove `stop`/`logs`/`attach`/`send`
- `src/mob/cli/resolver.py` — add `agent_run` to config
- `src/mob/cli/main.py` — register new commands

### Phase 4: Tests

**Unit tests for resolver with agent_run resource type**

`tests/unit/test_resolver.py` — add tests for:
- UUID passthrough for agent_run
- Positional resolution with agent_id filter
- Name-based resolution
- Ambiguity error when name matches across agents without filter

**API tests for updated endpoints**

`tests/unit/test_api_agent_runs.py`:
- Test create with explicit name
- Test create with auto-generated name
- Test name uniqueness constraint
- Test list with state filter
- Test send endpoint at new path

**CLI integration tests**

`tests/test_cli_integration.py` — add:
- `mob agent-runs` list output includes name column
- `mob agent-run show <name>` resolves correctly
- `mob agent run my-agent --name custom` creates with custom name
- `mob agent-run stop 1` resolves positional index

**Files touched:**
- `tests/unit/test_resolver.py`
- `tests/unit/test_api_agent_runs.py`
- `tests/test_cli_integration.py`

## System-Wide Impact

- **Interaction graph**: `agent run` → `POST /agent-runs` → `create_agent_run` service → DB insert + K8s CR creation → Rust operator reconcile. The only new behavior in this chain is the `name` field being set. The K8s CR name remains `ar-{id[:8]}` (not affected).
- **Error propagation**: Name uniqueness violations will raise `IntegrityError` at the DB layer. The service should catch this and raise `ServiceError("Run name already exists", 409)`.
- **State lifecycle risks**: None. The `name` field is immutable after creation. No partial-failure risk.
- **API surface parity**: The `send` endpoint moves from `/agents/{id}/send` to `/agent-runs/{id}/send`. No other interfaces expose the same functionality.

## Acceptance Criteria

- [ ] `AgentRun` model has a `name` field (String, globally unique, not null)
- [ ] `create_agent_run` auto-generates name as `{agent.name}-{random_8_hex}` when not provided
- [ ] `mob agent run REF --name custom` creates a run with the given name
- [ ] `mob agent-runs` lists runs with columns: `#`, `id`, `name`, `agent_id`, `state`, `pod_name`, `created_at`
- [ ] `mob agent-runs --agent <ref>` filters by agent (resolving REF through agent resolver)
- [ ] `mob agent-runs --state idle` filters by state
- [ ] `mob agent-run show|stop|logs|attach|send REF` resolves REF by name, position, or UUID
- [ ] `mob agent-run` subcommands accept `--agent` filter for scoping positional lookups
- [ ] `agent_run` added to `_RESOURCE_CONFIG` in resolver with `("agent-runs", "name", "agent_id")`
- [ ] `stop`, `logs`, `attach`, `send` removed from `agent` group
- [ ] Send endpoint moved to `POST /agent-runs/{run_id}/send`
- [ ] Local backend routes updated for all changes
- [ ] `AgentRunCreate` schema accepts optional `name`
- [ ] `AgentRunResponse` schema includes `name`
- [ ] Tests cover resolver, API, and CLI integration for new commands

## Dependencies & Risks

- **DB schema change**: Adding a non-null `name` column requires either a migration or handling existing rows. Since the project uses `create_all()` (no Alembic), new installs are fine. For existing data: the service can backfill on startup, or we accept that this is pre-1.0 and wipe.
- **Breaking change**: Removing `mob agent stop/logs/attach/send` breaks any existing scripts. Acceptable for pre-1.0.
- **K8s CR naming**: The CR name stays as `ar-{id[:8]}`, not the new `name` field. This is intentional — K8s names have DNS restrictions and the operator doesn't need the human-friendly name.

## Sources & References

- Existing command pattern: `src/mob/cli/commands/agent.py`
- Resolver pattern: `src/mob/cli/resolver.py`
- Agent run model: `src/mob/models/agent_run.py`
- Agent run service: `src/mob/services/agent_runs.py`
- Agent run API routes: `src/mob/api/routes/agent_runs.py`
- Local backend: `src/mob/cli/local_backend.py`
- CLI entry point: `src/mob/cli/main.py`
- Previous resolver plan: `docs/plans/2026-03-24-001-feat-cli-resource-reference-by-name-or-position-plan.md`
