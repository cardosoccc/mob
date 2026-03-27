# Agent Template Contract

Every Docker image used as an `agent_template` in MOB must implement the following contract. The Rust operator and Python API depend on these requirements.

## HTTP Endpoints

The agent must run an HTTP server on **port 8081** with these endpoints:

### `GET /health`

Returns the agent's health and current state.

**Response:**
```json
{
  "status": "ok",
  "state": "idle"
}
```

The operator's readiness probe sends `GET /health:8081` starting 3 seconds after pod creation, every 5 seconds.

### `POST /message`

Receives a message and returns the agent's response.

**Request:**
```json
{
  "message": "Your prompt here"
}
```

**Response (200):**
```json
{
  "response": "Agent's reply",
  "state": "idle"
}
```

**Error responses:**
- `409` — Agent is busy or not ready
- `502` — Internal error processing message
- `504` — LLM call timed out

## State Management

The agent must report its state via a Kubernetes pod annotation:

**Annotation key:** `mob.io/agent-state`

**Valid values:**
| State | Meaning |
|-------|---------|
| `idle` | Ready to receive messages |
| `busy` | Currently processing a message |
| `finished` | Graceful shutdown complete |
| `failed` | Unrecoverable error |

The agent writes this annotation using the Kubernetes API. The pod's service account (`mob-agent`) has permission to patch its own annotations.

## Environment Variables

The operator injects these environment variables into every agent pod:

| Variable | Source | Description |
|----------|--------|-------------|
| `SESSION_ID` | CR name | Unique session identifier |
| `AGENT_NAME` | Agent model | Human-readable agent name |
| `AGENT_SYSTEM_PROMPT` | Agent model | System prompt for the LLM |
| `MODEL_ENDPOINT` | Agent model | LLM provider and model (e.g., `anthropic:claude-sonnet-4-6-20260320`) |
| `AGENT_POD_NAME` | Downward API | The pod's own name (for self-annotation) |
| `AGENT_NAMESPACE` | Downward API | The pod's namespace |
| `AGENT_AUTH_TOKEN` | Optional | Bearer token for authenticating `/message` requests |
| `AGENT_CUSTOM_*` | Custom config | Agent-specific settings prefixed with `AGENT_CUSTOM_` |

Additionally, the Kubernetes Secret `mob-agent-secrets` (if it exists) is mounted as environment variables via `envFrom`.

## Lifecycle

1. **Startup:** Pod starts, agent initializes, sets annotation to `idle`
2. **Message processing:** On `POST /message`, set annotation to `busy`, process, set back to `idle`
3. **Shutdown:** On `SIGTERM`, set annotation to `finished`, clean up, exit

The pod has `restartPolicy: Never` — it will not be restarted on failure.

## Skills Directory

If the agent has skills attached, they are mounted as a ConfigMap volume at `/skills/`:

```
/skills/
├── skill-name-1.md
├── skill-name-2.md
```

Each file contains the skill's SKILL.md content (AgentSkills.io format). The agent should read these at startup and incorporate them into its behavior (e.g., append to system prompt, register as tools).

## Resource Limits

Default resource limits (overridable per template):

| Resource | Request | Limit |
|----------|---------|-------|
| CPU | 100m | 1000m |
| Memory | 256Mi | 1Gi |

## Reference Implementation

The default pydantic-ai agent at `src/mob/agent/entrypoint.py` is the reference implementation of this contract.

## Building a Custom Template

To create a custom agent template:

1. Implement the HTTP endpoints above on port 8081
2. Read environment variables for configuration
3. Report state via pod annotations
4. Handle SIGTERM gracefully
5. Build as a Docker image and register with `mob template create`

For non-Python runtimes (e.g., Pi, OpenClaw), use an adapter pattern: a thin HTTP server that wraps the runtime and exposes the MOB contract.
