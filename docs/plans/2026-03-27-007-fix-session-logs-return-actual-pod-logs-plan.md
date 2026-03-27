---
title: "fix: session logs should return actual pod stdout/stderr"
type: fix
status: completed
date: 2026-03-27
---

# fix: session logs should return actual pod stdout/stderr

## Overview

`mob session logs <ref>` always returns empty logs because it reads from the Session CR `.status` field, which has no `logs` key. Meanwhile, `kubectl logs <pod_id>` returns actual container stdout/stderr. The fix wires the existing `read_namespaced_pod_log` K8s API call into the session logs pipeline.

## Problem Statement

The `mob session logs` command produces no output while `kubectl logs <pod_id>` for the same session's pod returns real logs. The entire logs pipeline is broken:

| Aspect | `mob session logs` | `kubectl logs <pod>` |
|--------|-------------------|---------------------|
| Data source | Session CR `.status.logs` (does not exist) | Kubelet container stdout/stderr |
| API used | `CustomObjectsApi.get_namespaced_custom_object` | `CoreV1Api.read_namespaced_pod_log` |
| Result | Always `[]` | Actual container output |

**Root cause call chain:**

```
mob session logs <ref>
  -> api_get("/sessions/{id}/logs")
    -> get_session_live_status(session_id)
      -> CustomObjectsApi.get_namespaced_custom_object(...)
        -> cr.get("status", {})  # Returns {state, podName, errorMessage, lastTransitionTime}
  -> status.get("logs", [])     # "logs" key never exists -> returns []
```

The CR status struct (Rust operator `SessionStatus`) has no `logs` field and the operator never writes pod logs to it. This is correct — logs should be fetched on demand from the kubelet, not stored in the CR.

## Proposed Solution

After reading the CR status (which provides `podName`), call `CoreV1Api.read_namespaced_pod_log()` to fetch actual container logs and include them in the response. Use the inline K8s client pattern (`_try_get_k8s_core_api()`) already established in `sessions.py`.

## Technical Considerations

### K8s client pattern

`sessions.py` uses inline cached clients (`_try_get_k8s_core_api()`, `_try_get_k8s_custom_api()`), not `K8sManager`. The fix should follow this existing pattern rather than introducing `K8sManager` into the service, which would create a second K8s client initialization path.

### Response contract: string vs list

`K8sManager.get_pod_logs()` returns a raw `str`. The CLI (`session.py:84-87`) iterates `for line in logs` expecting a list. The API and local backend must call `.splitlines()` on the raw log string to maintain the list contract.

### `tail` parameter passthrough

- **API route** (`sessions.py` API): `tail` query param is declared but currently applied to an always-empty list. Must pass it to `read_namespaced_pod_log(tail_lines=tail)`.
- **Local backend** (`local_backend.py:253-258`): `params` dict containing `tail` is completely ignored. Must extract `params.get("tail", 100)` and pass through.

### Error handling for missing/pending pods

- Pod not yet scheduled (`podName` absent or empty): return `logs: []` with status showing current state.
- Pod deleted after `stop_session` (CR deleted): fall back to `session.pod_name` from the DB if the CR is gone, then attempt log retrieval. If pod is also gone, return `logs: []`.
- K8s `ApiException` (404 etc): catch and return `logs: []` rather than propagating a 500.

### Container name

`create_agent_pod` names the container `"agent"`. Pass `container="agent"` explicitly to `read_namespaced_pod_log` to avoid ambiguity if sidecars are ever added.

## Acceptance Criteria

- [ ] `mob session logs <ref>` returns the same log output as `kubectl logs <pod_name>` for a running session
- [ ] `mob session logs <ref> --tail N` correctly limits output to the last N lines (both API and local mode)
- [ ] When the pod is pending/not-yet-created, returns empty logs with the session status (no error/crash)
- [ ] When the pod has been deleted (session stopped), gracefully returns empty logs (no 500 error)
- [ ] Both remote API mode and local mode produce identical behavior
- [ ] Logs are returned as a list of strings (one per line), consistent with the CLI's iteration pattern

## Implementation Plan

### Files to Modify

#### 1. `src/mob/services/sessions.py`

Add a helper function (similar to existing `_get_pod_ip_sync`) that fetches pod logs using `_try_get_k8s_core_api()`:

```python
# src/mob/services/sessions.py
def _get_pod_logs(pod_name: str, namespace: str, tail_lines: int = 100) -> list[str]:
    """Fetch pod logs via CoreV1Api, returns list of log lines."""
    core_api = _try_get_k8s_core_api()
    if not core_api or not pod_name:
        return []
    try:
        log_str = core_api.read_namespaced_pod_log(
            name=pod_name,
            namespace=namespace,
            tail_lines=tail_lines,
            container="agent",
        )
        return log_str.splitlines() if log_str else []
    except ApiException:
        return []
```

Modify `get_session_live_status` (or create a new function like `get_session_logs`) to call this helper using `podName` from the CR status.

#### 2. `src/mob/api/routes/sessions.py`

Update the `/sessions/{session_id}/logs` endpoint to fetch actual pod logs using the pod name from the status and the `tail` query parameter:

```python
# src/mob/api/routes/sessions.py — /logs endpoint
status = await session_svc.get_session_live_status(session_id)
pod_name = status.get("podName", "")
logs = _get_pod_logs(pod_name, namespace, tail_lines=tail)
return {"logs": logs, "status": status}
```

#### 3. `src/mob/cli/local_backend.py`

Update the local backend route for `/sessions/{id}/logs` to:
- Read `tail` from `params.get("tail", 100)`
- Call the same pod log retrieval as the API route

#### 4. `src/mob/cli/commands/session.py`

No changes needed if the response contract (list of strings) is maintained. Verify the `for line in logs` display loop works with the new data.

### Edge Cases

| Scenario | Expected behavior |
|----------|------------------|
| Pod running, logs available | Returns log lines matching `kubectl logs --tail=N` |
| Pod pending (no container yet) | Returns `logs: []`, status shows state |
| Pod completed/terminated (still exists) | Returns logs (K8s retains terminated pod logs) |
| Pod deleted (CR also deleted) | Falls back to `session.pod_name` from DB; if pod gone, returns `logs: []` |
| K8s unreachable | Returns `logs: []` (existing error handling in `_try_get_k8s_core_api()`) |
| `--tail 0` or very large tail | Pass through to K8s API; 0 means all lines |

## Out of Scope

- **Log streaming** (`kubectl logs -f` equivalent) — separate feature, not blocked by this fix
- **Writing logs to CR status** — logs should be fetched on demand, not persisted in the CR
- **Refactoring `K8sManager` vs inline clients** — use existing inline pattern for consistency; unify later if desired

## Sources & References

- `src/mob/services/sessions.py:394-396` — current `get_session_live_status` (reads CR only)
- `src/mob/k8s/manager.py:120-127` — existing `get_pod_logs` method (unused in this path, reference for API call pattern)
- `src/mob/api/routes/sessions.py:52-58` — API endpoint
- `src/mob/cli/local_backend.py:253-258` — local backend route
- `src/mob/cli/commands/session.py:64-87` — CLI command
- `operator/src/crd/session.rs` — `SessionStatus` struct (no `logs` field, confirming CR cannot provide logs)
