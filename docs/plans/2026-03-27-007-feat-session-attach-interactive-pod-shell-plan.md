---
title: "feat: add mob session attach for interactive pod shell"
type: feat
status: completed
date: 2026-03-27
---

# feat: add mob session attach for interactive pod shell

## Overview

Add a `mob session attach` command that drops the user into an interactive shell on the session's pod, equivalent to `kubectl exec -it <pod> -n <ns> -c agent -- /bin/sh`. This is the first CLI command that bypasses the API layer to exec directly via kubectl.

## Motivation

Users currently need to manually look up the pod name (via `mob session show`) and then run `kubectl exec` themselves. `mob session attach` streamlines this to a single command, consistent with the existing `mob session logs/send/stop` subcommand family.

## Proposed Solution

Use `os.execvp("kubectl", ...)` to replace the CLI process with an interactive `kubectl exec` call. This avoids all PTY plumbing — kubectl handles terminal I/O natively. Signal handling and exit code propagation are free since `execvp` replaces the process entirely.

### Command signature

```
mob session attach <ref> [--agent <agent_ref>] [--domain <domain_id>] [-- <command...>]
```

- `ref` — session name, position number, or UUID (existing `resolve_ref` pattern)
- `--agent` / `--domain` — scope filters, consistent with all other session subcommands
- Trailing args after `--` override the default shell (`/bin/sh`)
- Example: `mob session attach 1 -- /bin/bash`

## Technical Considerations

### Bypasses the API layer

This is the first CLI command that doesn't route through `api_get`/`api_post` for its main action. It uses `api_get` only to resolve the session and get the pod name, then shells out directly. This is inherent to the interactive nature of the command.

### State validation

Only sessions in `idle` or `busy` state should be attachable — these indicate the pod is actually running. For `pending`/`starting`, the pod may not exist or the container may not be ready. For `finished`/`failed`, the pod is likely gone.

### kubectl pre-flight check

`os.execvp` raises `OSError` (raw traceback) if kubectl isn't on `PATH`. Use `shutil.which("kubectl")` first and raise a `click.ClickException` for a clean error message.

### kubeconfig passthrough

If `settings.kubeconfig` is set, pass `--kubeconfig <path>` to kubectl so the command targets the correct cluster. Note: the existing `_send_via_port_forward` in `sessions.py:514` has the same gap but fixing that is out of scope.

### Container name

The pod container is named `"agent"` (set in `create_agent_pod`). Pass `-c agent` explicitly to kubectl to avoid ambiguity if sidecars are ever added. Define as a constant rather than a magic string.

## Acceptance Criteria

- [ ] `mob session attach <ref>` opens an interactive shell on the session's pod
- [ ] `mob session attach <ref> -- /bin/bash` uses the specified command instead of `/bin/sh`
- [ ] `--agent` and `--domain` filter options work, consistent with other session subcommands
- [ ] Error message when session is in non-running state (pending, starting, finished, failed)
- [ ] Error message when session has no pod name assigned
- [ ] Error message when kubectl is not installed (`shutil.which` check)
- [ ] `settings.kubeconfig` is passed to kubectl when set
- [ ] `settings.kubernetes_namespace` is passed as `-n` to kubectl
- [ ] Works in both local mode (Kind cluster) and dev/remote mode

## Implementation Plan

### File to modify: `src/mob/cli/commands/session.py`

Add a new `attach` subcommand to the `session` group:

```python
# src/mob/cli/commands/session.py

AGENT_CONTAINER_NAME = "agent"

@session.command("attach")
@click.argument("ref")
@click.option("--agent", "agent_ref", help="Scope by agent (name or position)")
@agent_filters
@click.argument("command", nargs=-1, type=click.UNPROCESSED)
def session_attach(ref, agent_ref, domain_id, command):
    """Attach to a running session's pod. REF is a name or position number.

    Pass a custom command after --: mob session attach 1 -- /bin/bash
    """
    import os
    import shutil
    from mob.config import get_settings

    # Pre-flight: kubectl must be installed
    if not shutil.which("kubectl"):
        raise click.ClickException("kubectl is not installed or not on PATH")

    # Resolve session and get pod name
    agent_id = _resolve_agent_filter(agent_ref, domain_id)
    session_id = resolve_ref("session", ref, agent_id=agent_id)
    data = api_get(f"/sessions/{session_id}")

    # Validate state
    state = data.get("state", "")
    if state not in ("idle", "busy"):
        raise click.ClickException(
            f"Cannot attach: session is in '{state}' state (must be idle or busy)"
        )

    # Validate pod name
    pod_name = data.get("pod_name")
    if not pod_name:
        raise click.ClickException("Session has no pod assigned yet")

    # Build kubectl exec command
    settings = get_settings()
    args = ["kubectl", "exec", "-it", pod_name,
            "-n", settings.kubernetes_namespace,
            "-c", AGENT_CONTAINER_NAME]

    if settings.kubeconfig:
        args.extend(["--kubeconfig", settings.kubeconfig])

    args.append("--")
    args.extend(command if command else ["/bin/sh"])

    os.execvp("kubectl", args)
```

### No other files need changes

- No API route needed (interactive command, bypasses API)
- No local backend route needed
- No service layer changes
- CLI registration is automatic (subcommand of existing `session` group)

### Edge Cases

| Scenario | Behavior |
|----------|----------|
| Session running, pod exists | Interactive shell opens |
| Session pending/starting | Clean error: "session is in 'pending' state" |
| Session finished/failed | Clean error: "session is in 'failed' state" |
| Pod deleted but state stale | kubectl fails with "pod not found" (kubectl's own error) |
| kubectl not installed | Clean error: "kubectl is not installed or not on PATH" |
| Custom kubeconfig in settings | `--kubeconfig` passed to kubectl |
| Trailing args: `-- /bin/bash` | Uses `/bin/bash` instead of `/bin/sh` |
| No trailing args | Defaults to `/bin/sh` |

## Out of Scope

- Log streaming (`kubectl logs -f`) — separate feature
- Python-native PTY handling via `kubernetes.stream` — unnecessary complexity when kubectl handles this
- `--container` flag — only one container (`agent`) exists today
- `--namespace` override flag — consistent with other commands that use config
- Fixing kubeconfig gap in `_send_via_port_forward` — separate issue

## Sources & References

- `src/mob/cli/commands/session.py:64-87` — existing `session logs` subcommand (pattern to follow)
- `src/mob/cli/resolver.py` — `resolve_ref` and `agent_filters`
- `src/mob/k8s/manager.py:77` — container name `"agent"` in pod spec
- `src/mob/config.py` — `get_settings()` for namespace/kubeconfig
- `src/mob/services/sessions.py:514` — existing `kubectl port-forward` subprocess usage
