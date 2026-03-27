---
title: "feat: Create agents via YAML definition"
type: feat
status: completed
date: 2026-03-27
---

# feat: Create agents via YAML definition

## Overview

Add YAML-based agent creation to the mob CLI. Users author an `agent.yaml` file describing their agent — name, template, domain, system prompt, model endpoint, skills, environment variables, and custom settings — then apply it with `mob agent apply agent.yaml`. Env vars defined in the YAML have defaults that can be overridden at session launch via `mob agent run --env KEY=VALUE`.

## Problem Statement / Motivation

Currently agents are created exclusively via CLI flags (`mob agent create --name ... --template ... --domain ... --system-prompt ... --model-endpoint ... --skill ...`). This works for one-off creation but falls short for:

- **Reproducibility** — agent definitions aren't version-controllable
- **Complex configuration** — long system prompts and multiple env vars are unwieldy as flags
- **GitOps workflows** — no declarative way to manage agent fleet
- **Template customization** — no mechanism to pass template-specific settings (temperature, max_tokens) or extra env vars beyond the hardcoded set

## YAML Schema

```yaml
# agent.yaml
name: assistant
agent_template: mob-agent-pydantic:latest
domain: dev                                    # resolved by identifier
system_prompt: |
  You are a helpful research assistant.
  Be concise and cite sources.
model_endpoint: "anthropic:claude-haiku-4-5-20251001"
skills:                                        # resolved by name
  - code-review
  - testing
env:
  LLM_TIMEOUT: "120"                          # default value
  ANTHROPIC_API_KEY: ""                        # empty = required at runtime
  CUSTOM_HEADER: "X-Custom: true"
custom:
  temperature: "0.7"
  max_tokens: "4096"
```

**Field mapping:**

| YAML field | Existing model field | Notes |
|------------|---------------------|-------|
| `name` | `Agent.name` | Required |
| `agent_template` | `Agent.agent_template` | Required |
| `domain` | `Agent.domain_id` | Resolved from identifier to UUID |
| `system_prompt` | `Agent.system_prompt` | Optional |
| `model_endpoint` | `Agent.model_endpoint` | Optional |
| `skills` | `AgentSkill` join table | Resolved from names to UUIDs |
| `env` | `Agent.env_defaults` (NEW) | JSON column, `dict[str, str]` |
| `custom` | `Agent.custom_config` (NEW) | JSON column, `dict[str, str]` |

## Architectural Decisions

### D1: Storage — `env` and `custom` as JSON columns on Agent

Add two new nullable JSON columns to the `Agent` model:
- `env_defaults: Text (JSON)` — default env vars as `{"KEY": "value", ...}`
- `custom_config: Text (JSON)` — custom template settings as `{"key": "value", ...}`

**Why JSON columns, not separate tables:** These are simple key-value maps that are always read/written as a unit with the agent. A join table adds complexity for no benefit. JSON columns work in both SQLite and PostgreSQL.

### D2: Env var propagation — through Session CR to pod

The full path: Agent DB row -> Session creation merges defaults + overrides -> Session CR `envVars` field -> Rust operator builds pod with extra env vars.

1. Add `envVars: Option<BTreeMap<String, String>>` to `SessionSpec` in the Rust CRD
2. Update `build_agent_pod()` to iterate over `envVars` and append to the pod's env list
3. Update `create_session()` in Python to merge agent's `env_defaults` + `custom_config` (prefixed with `AGENT_CUSTOM_`) + runtime overrides into the CR

### D3: `custom` settings — injected as prefixed env vars

The `custom` block is injected into the pod as env vars with `AGENT_CUSTOM_` prefix:
- `custom.temperature: "0.7"` → `AGENT_CUSTOM_TEMPERATURE=0.7`
- `custom.max_tokens: "4096"` → `AGENT_CUSTOM_MAX_TOKENS=4096`

This requires no new infrastructure beyond what D2 establishes. Agent templates read these env vars.

### D4: CLI commands — `apply` (upsert) + `create --file`

- `mob agent apply agent.yaml` — idempotent upsert: lookup by name+domain, create if missing, update if found
- `mob agent create --file agent.yaml` — create-only, fails if agent with same name+domain exists

### D5: Runtime env var overrides

`mob agent run assistant --env ANTHROPIC_API_KEY=sk-xxx --env LLM_TIMEOUT=300`

The `--env` flag is repeatable `KEY=VALUE`. Override precedence (highest wins):
1. Runtime overrides (`--env`)
2. Agent `custom_config` (prefixed)
3. Agent `env_defaults`
4. Hardcoded operator vars (`SESSION_ID`, `AGENT_NAME`, etc.)

### D6: Required env vars (empty values)

Env vars with empty string values in the YAML (e.g., `ANTHROPIC_API_KEY: ""`) are treated as **required at runtime**. The `mob agent run` command warns if any required env vars are not provided via `--env`, but does not block (the agent may source them from `mob-agent-secrets` K8s secret).

### D7: Skills — present means full replacement, absent means unchanged

When applying a YAML file:
- `skills` key present → full replacement (matches existing service behavior)
- `skills` key absent → leave skills unchanged

## Technical Approach

### Implementation Phases

#### Phase 1: Database + Schema (Foundation)

**Files to modify:**

1. **`src/mob/models/agent.py`** — Add two new columns:
   ```python
   env_defaults: Mapped[str | None] = mapped_column(Text, nullable=True)    # JSON
   custom_config: Mapped[str | None] = mapped_column(Text, nullable=True)   # JSON
   ```

2. **`src/mob/schemas.py`** — Update `AgentCreate` and `AgentResponse`:
   ```python
   class AgentCreate(BaseModel):
       # ... existing fields ...
       env_defaults: dict[str, str] | None = None
       custom_config: dict[str, str] | None = None

   class AgentResponse(BaseModel):
       # ... existing fields ...
       env_defaults: dict[str, str] | None
       custom_config: dict[str, str] | None
   ```

3. **`src/mob/services/agents.py`** — Update `create_agent()` and `update_agent()` to accept and store the new fields (serialize dict to JSON string for storage).

4. **`src/mob/api/routes/agents.py`** — Pass new fields through to service layer.

5. **`src/mob/cli/local_backend.py`** — Pass new fields in local mode routing.

**Success criteria:**
- [ ] `env_defaults` and `custom_config` stored and returned via API
- [ ] `mob migrate` adds columns to existing databases
- [ ] Existing agents unaffected (columns nullable)

---

#### Phase 2: YAML Parsing + CLI Commands

**Files to create/modify:**

1. **`src/mob/cli/yaml_loader.py`** (NEW) — YAML parsing and validation:
   ```python
   import yaml
   from pydantic import BaseModel, Field

   class AgentYaml(BaseModel):
       name: str
       agent_template: str
       domain: str              # identifier, not UUID
       system_prompt: str | None = None
       model_endpoint: str | None = None
       skills: list[str] | None = None   # names, not UUIDs
       env: dict[str, str] | None = None
       custom: dict[str, str] | None = None

   def load_agent_yaml(path: str) -> AgentYaml:
       with open(path) as f:
           data = yaml.safe_load(f)
       return AgentYaml(**data)
   ```

2. **`src/mob/cli/commands/agent.py`** — Add new commands:
   - `mob agent apply <file>` — upsert command
   - `mob agent create --file <file>` — add `--file` option to existing create

   The apply command:
   - Parses YAML via `load_agent_yaml()`
   - Resolves `domain` identifier to UUID via `resolve_ref("domain", yaml.domain)`
   - Resolves `skills` names to UUIDs via `resolve_ref("skill", name)` for each
   - Checks if agent with `name` exists (scoped to resolved domain)
   - If exists: PUTs to `/agents/{id}` with updated fields
   - If not: POSTs to `/agents` to create

3. **`src/mob/cli/commands/agent.py`** — Add `--env` flag to `agent run`:
   ```python
   @click.option("--env", "env_overrides", multiple=True, help="Env override KEY=VALUE")
   ```

**Success criteria:**
- [ ] `mob agent apply agent.yaml` creates a new agent from YAML
- [ ] `mob agent apply agent.yaml` updates existing agent (idempotent)
- [ ] `mob agent create --file agent.yaml` creates agent from YAML
- [ ] Validation errors (bad YAML, missing fields, unresolved skills/domain) give clear messages
- [ ] `mob agent run assistant --env KEY=VALUE` accepts env overrides

---

#### Phase 3: Session CR + Operator (Env Var Propagation)

**Files to modify:**

1. **`operator/src/crd/session.rs`** — Add `envVars` to `SessionSpec`:
   ```rust
   #[serde(rename = "envVars", default, skip_serializing_if = "Option::is_none")]
   pub env_vars: Option<std::collections::BTreeMap<String, String>>,
   ```

2. **`deploy/base/crds/session.yaml`** — Add `envVars` to CRD schema:
   ```yaml
   envVars:
     type: object
     additionalProperties:
       type: string
   ```

3. **`operator/src/resources/pod.rs`** — In `build_agent_pod()`, append custom env vars from CR spec:
   ```rust
   if let Some(extra_env) = &spec.env_vars {
       for (key, value) in extra_env {
           env.push(EnvVar {
               name: key.clone(),
               value: Some(value.clone()),
               ..Default::default()
           });
       }
   }
   ```

4. **`src/mob/services/sessions.py`** — In `create_session()`, merge env vars into CR:
   - Load agent's `env_defaults` and `custom_config` from DB
   - Prefix `custom_config` keys with `AGENT_CUSTOM_`
   - Merge: defaults <- custom (prefixed) <- runtime overrides
   - Filter out empty-value entries (required-but-not-provided)
   - Add merged dict to CR body as `envVars`

5. **`src/mob/schemas.py`** — Add `env_overrides` to `SessionCreate`:
   ```python
   class SessionCreate(BaseModel):
       agent_id: str
       task_id: str | None = None
       name: str | None = None
       env_overrides: dict[str, str] | None = None
   ```

6. **`src/mob/api/routes/sessions.py`** — Pass `env_overrides` through to service.

7. **`src/mob/cli/local_backend.py`** — Pass `env_overrides` in local mode routing.

**Success criteria:**
- [ ] `cargo build && cargo test` passes with new CRD field
- [ ] Session CR includes `envVars` when agent has env_defaults
- [ ] Operator injects custom env vars into pod
- [ ] Runtime `--env` overrides take precedence
- [ ] Existing sessions without env vars work unchanged

---

#### Phase 4: Tests

**Files to create/modify:**

1. **`tests/unit/test_yaml_loader.py`** (NEW) — YAML parsing tests:
   - Valid YAML with all fields
   - Minimal YAML (name + template + domain only)
   - Invalid YAML syntax
   - Missing required fields
   - Invalid field types

2. **`tests/unit/test_api_sessions.py`** — Add env var propagation tests:
   - Create session with env_overrides
   - Verify env vars in CR mock

3. **`tests/unit/test_api_agents.py`** (or existing agent test file) — Add tests:
   - Create agent with env_defaults and custom_config
   - Update agent env_defaults via PUT
   - Verify env_defaults returned in response

4. **`tests/integration/test_cli_integration.py`** — Add:
   - `test_agent_apply_yaml` — create and update via YAML
   - `test_agent_run_with_env_overrides`

5. **Rust tests in `operator/src/resources/pod.rs`** — Add test for pod with custom env vars

**Success criteria:**
- [ ] `uv run pytest` passes
- [ ] `cargo test` passes
- [ ] YAML parsing edge cases covered

---

#### Phase 5: Documentation

1. **`README.md`** — Add YAML agent creation to CLI Reference section
2. **Example YAML files** — Create `examples/agent.yaml` with annotated example

## System-Wide Impact

### Interaction Graph

YAML file → CLI parser → resolver (domain/skill name→UUID) → API `POST /agents` → service `create_agent()` → DB insert (Agent + env_defaults + custom_config). Then: `mob agent run --env` → `POST /sessions` with env_overrides → service merges agent defaults + overrides → Session CR with `envVars` → operator `build_agent_pod()` → pod with custom env vars.

### Error Propagation

- YAML syntax errors: caught at CLI parse time, before any API calls
- Missing required fields: caught by Pydantic validation of `AgentYaml`
- Unresolved domain/skill names: caught by resolver, exits with clear error
- Empty required env vars at run time: warning printed, session created anyway (secret may come from K8s)

### State Lifecycle Risks

- New JSON columns are nullable, so existing agents are unaffected
- If the operator is deployed before the CRD is updated, it will ignore the `envVars` field (serde `default` + `skip_serializing_if`)
- If the CRD is updated before the operator, the field exists but is never read — no harm

### API Surface Parity

- CLI `mob agent create --file` / `mob agent apply` → new surface
- CLI `mob agent run --env` → new flag
- API `POST /agents` body → gains `env_defaults`, `custom_config` fields
- API `POST /sessions` body → gains `env_overrides` field
- Local backend must route new fields in both paths

### Integration Test Scenarios

1. Create agent via YAML → run session → verify pod has custom env vars
2. Apply YAML twice → second is an update, not a duplicate
3. Apply YAML with unknown skill → clear error before any DB changes
4. Run session with `--env` override → override takes precedence over default
5. Run session without `--env` for required var → warning but session created

## Acceptance Criteria

- [ ] `mob agent apply agent.yaml` creates an agent from YAML definition
- [ ] `mob agent apply agent.yaml` updates existing agent idempotently
- [ ] `mob agent create --file agent.yaml` creates agent from YAML (create-only)
- [ ] Domain and skill names in YAML are resolved to UUIDs automatically
- [ ] `env` block stored as `env_defaults` on Agent model
- [ ] `custom` block stored as `custom_config` on Agent model
- [ ] `mob agent run assistant --env KEY=VALUE` passes overrides to session
- [ ] Custom env vars flow through Session CR to pod (operator injects them)
- [ ] `custom` settings injected as `AGENT_CUSTOM_*` prefixed env vars
- [ ] Empty env values treated as required-at-runtime (warn if not provided)
- [ ] YAML validation errors give clear, actionable messages
- [ ] All existing CLI commands and tests continue to work unchanged

## Dependencies & Risks

- **Database migration** — New columns require `mob migrate` on existing databases. The `_add_missing_columns` mechanism handles this automatically.
- **CRD + Operator deployment** — The `envVars` field must be added to both the CRD YAML and the Rust operator. Deploy CRD first, then operator. The field is optional so rollout order is safe.
- **PyYAML** — Already a dependency (`pyyaml>=6.0.0` in `pyproject.toml`), just unused until now.

## Sources & References

### Internal References

- Agent model: `src/mob/models/agent.py`
- Agent CLI: `src/mob/cli/commands/agent.py`
- Agent service: `src/mob/services/agents.py`
- Agent schemas: `src/mob/schemas.py:102-129`
- Session service: `src/mob/services/sessions.py` (CR creation at line ~196)
- Rust CRD: `operator/src/crd/session.rs`
- Rust pod builder: `operator/src/resources/pod.rs`
- K8s CRD manifest: `deploy/base/crds/session.yaml`
- Learnings: `docs/solutions/integration-issues/pydantic-ai-agent-image-k8s-orchestration.md` — env var injection patterns, lazy SDK init, Secret-based secrets
- Learnings: `docs/solutions/database-issues/sqlite-schema-evolution-missing-columns.md` — new columns need migration
