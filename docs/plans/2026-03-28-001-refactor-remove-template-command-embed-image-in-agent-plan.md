---
title: "refactor: Remove template command, embed image reference in agent"
type: refactor
status: active
date: 2026-03-28
---

# refactor: Remove template command, embed image reference in agent

## Overview

The `template` concept adds an unnecessary indirection layer. The agent already stores the Docker image reference as a plain `agent_template` string column. The Template table, CLI commands, API routes, and service layer should be removed entirely. Resource limits (the only useful data beyond the image string) should move to the Agent model.

## Problem Statement

- Templates exist as a separate entity (table, CRUD, CLI) but agents already store the resolved image string directly — there's no FK
- `_resolve_template()` does a lookup that's a no-op in practice — all YAML files and tests use raw Docker image refs
- Resource limits are fetched via a reverse lookup (`Template.image == agent.agent_template`) at session creation, which is fragile and indirect
- The template concept adds cognitive overhead and code surface for no real benefit

## Proposed Solution

1. Add `resource_cpu_limit` and `resource_memory_limit` columns to the `agents` table
2. Delete the entire Template entity (model, service, routes, CLI, schemas, tests)
3. Remove `_resolve_template()` — `agent_template` is always a Docker image ref
4. Session creation reads resource limits from Agent directly
5. Agent CLI/API/YAML gains optional resource limit fields

## Acceptance Criteria

- [ ] `mob template` and `mob templates` commands no longer exist
- [ ] `/api/v1/templates` routes no longer exist
- [ ] Agent model has `resource_cpu_limit` and `resource_memory_limit` nullable columns
- [ ] `mob agent create --template <image>` still works (stores image string directly)
- [ ] `mob agent show` displays the image reference inline (already does)
- [ ] Session creation uses agent's resource limits for the pod spec
- [ ] Agent YAML supports `resource_cpu_limit` and `resource_memory_limit` fields
- [ ] All existing tests pass (template-specific tests deleted)
- [ ] `mob migrate` handles adding the new columns to existing databases

## MVP

### Files to delete

| File | What it is |
|------|-----------|
| `src/mob/models/template.py` | Template SQLAlchemy model |
| `src/mob/services/templates.py` | Template CRUD service |
| `src/mob/api/routes/templates.py` | Template REST routes |
| `src/mob/cli/commands/template.py` | Template CLI commands |
| `tests/unit/test_api_templates.py` | Template API tests |
| `tests/unit/test_models_template.py` | Template model tests |

### Files to edit

#### 1. `src/mob/models/agent.py` — add resource limit columns

```python
resource_cpu_limit: Mapped[str | None] = mapped_column(String(50), nullable=True)
resource_memory_limit: Mapped[str | None] = mapped_column(String(50), nullable=True)
```

#### 2. `src/mob/models/__init__.py` — remove Template import

Remove `from mob.models.template import Template` and any `__all__` reference.

#### 3. `src/mob/services/agents.py` — remove `_resolve_template()`

- Delete `_resolve_template()` function entirely
- In `create_agent()`: store `agent_template` directly (no resolution), accept `resource_cpu_limit` and `resource_memory_limit` params
- In `update_agent()`: same — remove resolution call, accept resource limit params

#### 4. `src/mob/services/sessions.py` (~lines 264-274) — read limits from agent

Replace:
```python
from mob.models.template import Template
result = await session.execute(
    select(Template).where(Template.image == agent.agent_template)
)
tmpl = result.scalar_one_or_none()
if tmpl:
    resource_cpu_limit = tmpl.resource_cpu_limit
    resource_memory_limit = tmpl.resource_memory_limit
```

With:
```python
resource_cpu_limit = agent.resource_cpu_limit
resource_memory_limit = agent.resource_memory_limit
```

#### 5. `src/mob/schemas.py` — remove Template schemas, add resource limits to Agent schemas

- Delete `TemplateCreate`, `TemplateUpdate`, `TemplateResponse`
- Add `resource_cpu_limit: str | None = None` and `resource_memory_limit: str | None = None` to `AgentCreate`, `AgentUpdate`, `AgentResponse`

#### 6. `src/mob/api/app.py` — remove templates router

Remove the `templates` router import and `include_router` call.

#### 7. `src/mob/cli/main.py` — remove template commands

Remove `templates` and `template` imports and `add_command` calls.

#### 8. `src/mob/cli/local_backend.py` — remove template routing

Remove `TemplateResponse` import, `template_svc` import, and the `/templates` routing block.

#### 9. `src/mob/cli/resolver.py` — remove template resource config

Remove `"template"` entry from `_RESOURCE_CONFIG`.

#### 10. `src/mob/cli/yaml_loader.py` — add resource limits to AgentYaml

Add optional `resource_cpu_limit` and `resource_memory_limit` fields to the `AgentYaml` Pydantic model.

#### 11. `src/mob/cli/commands/agent.py` — add resource limit flags

Add `--cpu-limit` and `--memory-limit` options to `agent create` and `agent edit`.

#### 12. `src/mob/api/routes/agents.py` — pass resource limits through

Ensure `create_agent` and `update_agent` route handlers pass resource limit fields to the service.

#### 13. `tests/unit/test_api_agents.py` — update if needed

Ensure agent tests don't reference templates. Add test for resource limits on agents.

#### 14. `tests/unit/test_api_sessions.py` — update template lookup removal

Remove any mocking of Template lookups in session tests.

## Technical Considerations

- **Schema migration**: The `_add_missing_columns()` auto-migration handles column additions to SQLite. The two new nullable columns will be picked up by `mob migrate`. Column deletions (dropping the `templates` table) are NOT handled automatically — the orphaned table will remain in existing databases but is harmless.
- **No breaking change to operator**: The Rust operator only sees the Session CR spec fields (`agentTemplate`, `resourceCpuLimit`, `resourceMemoryLimit`) — these remain unchanged.
- **Backward compat for YAML**: Existing YAML files with `agent_template: mob-agent-pi` continue to work as-is. New optional fields are additive.

## Sources

- Agent model: `src/mob/models/agent.py`
- Template resolution: `src/mob/services/agents.py:13-34`
- Session resource limit lookup: `src/mob/services/sessions.py:264-274`
- Learning: `docs/solutions/database-issues/sqlite-schema-evolution-missing-columns.md` — `_add_missing_columns()` handles additions only
