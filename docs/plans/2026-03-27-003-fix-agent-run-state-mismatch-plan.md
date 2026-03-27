---
title: "fix: Agent run list state does not reflect live K8s pod state"
type: fix
status: completed
date: 2026-03-27
---

# fix: Agent run list state does not reflect live K8s pod state

## Overview

When listing agent-runs via `mob agent-runs` or `GET /api/v1/agent-runs`, the `state` field is always stale — typically stuck at `pending` — even though the agent pod has progressed to `idle`, `busy`, or other states. This is because the list endpoint reads exclusively from the database, and the database state is **never updated after creation**.

## Problem Statement

The system has **three independent sources of state** for an agent run:

1. **Database** (`agent_runs.state` column) — set to `pending` at creation, never updated by the operator
2. **K8s CR status** (`AgentRun` CRD `.status.state`) — updated every 15s by the Rust operator
3. **Pod annotation** (`mob.io/agent-state`) — set by the agent process itself

The listing endpoint (`list_agent_runs()` in `src/mob/services/agent_runs.py:68-82`) only reads source #1. The operator only writes to source #2. There is no bridge between them.

**Reproduction:**
1. `mob agent create --name test --agent-template pydantic-ai`
2. `mob agent-run create --agent test`
3. Wait for pod to become ready (~30s)
4. `mob agent-runs` → state shows `pending` (should be `idle`)
5. `mob agent-run logs <run-id>` → status shows `Idle` (reads from CR, works correctly)

**Additionally broken:** `--state idle` filter returns zero results because the SQL `WHERE state = 'idle'` matches nothing (all rows are `pending`). The `GET /agent-runs/{id}` single-run endpoint has the same staleness issue.

## Approach Analysis

Two approaches are presented for decision. **Recommendation: Approach A.**

---

### Approach A: Live K8s State Enrichment (Recommended)

**How it works:** After fetching runs from the DB, batch-read all AgentRun CR statuses from K8s in a single API call, then merge the live state into each response before returning.

**Pros:**
- No changes to the Rust operator — it remains a pure K8s reconciler
- Follows existing patterns: `send_message()` and `get_agent_run_logs()` already read live CR status
- K8s API infrastructure exists (`_try_get_k8s_custom_api()`, RBAC for `mob-api` SA)
- Graceful degradation: falls back to DB state when K8s is unavailable (local dev, API down)
- Single source of truth for runtime state (the CR, managed by the operator)
- No new network dependencies or auth between components

**Cons:**
- Adds K8s API call to every list request (mitigated by batch listing)
- State filtering (`--state idle`) requires post-enrichment filtering in Python, not SQL
- DB remains stale (cosmetic concern — DB is not the authority for runtime state)

**Variant A+: Write-back on read.** After enriching, write the live state back to the DB as a side effect. This self-heals the DB over time and makes SQL state filtering work naturally. The write-back is safe because states only move forward through `VALID_TRANSITIONS`. This adds a DB write to list calls but eliminates the filtering problem.

**Key implementation details:**
- Use `list_namespaced_custom_object()` to batch-fetch all CRs in one K8s API call
- Build a `dict[cr_name, status]` map, keyed by `ar-{run_id[:8]}`
- Normalize CR title-case states (`Idle`) to DB lowercase (`idle`) via explicit mapping
- Skip enrichment for terminal-state runs (`finished`, `failed`) — their CRs/pods are being cleaned up
- For non-terminal runs with no matching CR: mark as `failed` with error "CR not found"
- Wrap K8s calls in `asyncio.to_thread()` since the `kubernetes` Python client is synchronous

**Files to modify:**
| File | Change |
|------|--------|
| `src/mob/services/agent_runs.py` | Add `_enrich_runs_with_live_state()`, add batch CR listing, add case mapping, update `list_agent_runs()` and `get_agent_run()` |
| `src/mob/api/routes/agent_runs.py` | Update `get_agent_run` route to enrich single run |
| `tests/unit/test_api_agent_runs.py` | Add tests for state enrichment, graceful degradation, case mapping |

---

### Approach B: Operator-Driven DB Sync via API Callback

**How it works:** The Rust operator calls `PUT /api/v1/agent-runs/{id}/state` whenever it transitions a CR's state. This keeps the database in sync as the source of truth.

**Pros:**
- DB becomes a reliable source of truth — all reads are simple SQL queries
- State filtering (`--state idle`) works natively in SQL
- No additional K8s API calls at read time
- The `update_agent_run_state` endpoint already exists (`src/mob/api/routes/agent_runs.py:65`)

**Cons:**
- **Couples operator to API:** Operator currently has zero knowledge of the Python API. Would require adding:
  - `reqwest` HTTP client dependency to operator's `Cargo.toml`
  - API URL configuration (env var or ConfigMap)
  - Authentication between operator and API
  - Retry logic with backoff for failed callbacks
- **Availability coupling:** If the API is down during a state transition, the DB goes stale — the exact same bug returns. The operator's 15-second reconcile loop would need to track and retry failed callbacks per run.
- **State transition ordering:** The existing `VALID_TRANSITIONS` guard in `update_agent_run_state()` rejects out-of-order transitions. If the API misses `pending → starting` but receives `starting → idle`, the DB still shows `pending` and the `pending → idle` transition is rejected (409). The operator would need to either send the full state (bypassing validation) or track which transitions the API has acknowledged.
- **Added complexity to a currently simple reconciler:** The operator is ~190 lines of clean Rust. Adding HTTP callbacks, retry queues, and error handling would roughly double its complexity.

**Files to modify:**
| File | Change |
|------|--------|
| `operator/Cargo.toml` | Add `reqwest` dependency |
| `operator/src/controller/agent_run_controller.rs` | Add API callback after every `update_status()` call, retry logic |
| `operator/src/main.rs` or new config module | API URL, auth token configuration |
| `src/mob/services/agent_runs.py` | Possibly relax `VALID_TRANSITIONS` to allow gap transitions |

---

## Acceptance Criteria

- [ ] `mob agent-runs` shows live state matching `mob agent-run logs` output
- [ ] `mob agent-runs --state idle` returns runs that are actually idle
- [ ] `GET /api/v1/agent-runs` returns enriched state for non-terminal runs
- [ ] `GET /api/v1/agent-runs/{id}` returns enriched state for non-terminal runs
- [ ] When K8s is unavailable, endpoints degrade gracefully to DB state (no errors)
- [ ] CR title-case states (`Idle`) are normalized to DB lowercase (`idle`) in responses
- [ ] Non-terminal runs with missing CRs are reported as `failed`
- [ ] Terminal-state runs (`finished`, `failed`) are not enriched (skip K8s lookup)
- [ ] Existing tests pass; new tests cover enrichment, degradation, and case mapping

## Technical Considerations

- **Case mapping:** DB uses lowercase (`idle`), CR uses title-case (`Idle`). An explicit `CR_STATE_TO_DB_STATE` mapping dict is needed adjacent to `VALID_TRANSITIONS`.
- **Async correctness:** The `kubernetes` Python client is synchronous. All K8s calls from async handlers must use `asyncio.to_thread()` (see learnings from `docs/solutions/integration-issues/pydantic-ai-agent-image-k8s-orchestration.md`).
- **RBAC:** The `mob-api` ServiceAccount already has agentrun CRUD and pod get permissions. `list_namespaced_custom_object` is covered by existing RBAC.
- **Performance:** A single `list_namespaced_custom_object()` call replaces N individual CR reads. Terminal runs are skipped entirely.
- **Orphan detection:** Runs in non-terminal DB state with no matching CR should be marked `failed` with an appropriate error message.

## Sources & References

- `src/mob/services/agent_runs.py:68-82` — current `list_agent_runs()` (DB-only)
- `src/mob/services/agent_runs.py:158-173` — existing `get_agent_run_live_status()` (reads CR)
- `src/mob/api/routes/agent_runs.py:15-24` — list endpoint route
- `src/mob/api/routes/agent_runs.py:39-44` — single get endpoint route (same staleness bug)
- `src/mob/models/agent_run.py:11-17` — `AgentRunState` enum (lowercase values)
- `operator/src/controller/agent_run_controller.rs` — operator reconcile loop, 15s requeue
- `operator/src/resources/pod.rs` — `derive_state_from_pod()` with title-case states
- `docs/solutions/integration-issues/pydantic-ai-agent-image-k8s-orchestration.md` — learnings on async K8s calls, RBAC boundaries
