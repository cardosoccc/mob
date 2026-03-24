# mob

AI Agent Orchestration Platform — cloud-native, provider agnostic.

Run AI agents as Kubernetes pods. Chat with them. Watch them think.

## Philosophy

mob treats AI agents as first-class infrastructure. Each agent is a container. Each conversation is a pod. The Kubernetes operator watches over them, tracking state transitions through a reconciliation loop — the same pattern that makes Kubernetes itself reliable.

**Design principles:**

- **Cloud-native** — Agents run as K8s pods with full lifecycle management. The operator handles creation, monitoring, and cleanup.
- **Provider agnostic** — Use any LLM provider (OpenAI, Anthropic, local models). Agents are Docker images — bring your own or use the default pydantic-ai image.
- **Works anywhere** — Local development with Kind + SQLite. Production with EKS/GKE + PostgreSQL. Same CLI, same workflow.
- **Multi-tenant** — Organizations contain domains. Domains contain agents. Groups control access. Built for teams from day one.
- **Operator pattern** — A Rust controller reconciles desired state (AgentRun CRDs) with actual state (pod annotations). State is never guessed — it's observed.

## Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (package manager)
- Docker
- [Kind](https://kind.sigs.k8s.io/) (local Kubernetes)
- kubectl

### Install

```bash
git clone https://github.com/cardosoccc/mob.git
cd mob
make setup      # Install dependencies
make install    # Install the mob CLI
```

### Initialize

```bash
mob init local    # Set up local environment (SQLite + Kind)
mob migrate       # Create database tables
```

### Start the cluster

```bash
make dev-up       # Creates Kind cluster, builds images, deploys everything
```

### Create and chat with an agent

```bash
# Set up organization structure
mob org create --identifier myorg --name "My Org"
mob domain create --identifier dev --name "Development" --org 1

# Create an agent
mob agent create \
  --name "assistant" \
  --template "mob-agent-pydantic:latest" \
  --domain 1 \
  --system-prompt "You are a helpful assistant. Be concise." \
  --model-endpoint "anthropic:claude-haiku-4-5-20251001"

# Run the agent (creates a pod)
mob agent run 1

# Wait for it to become idle
mob agent-runs

# Chat
mob agent-run send 1 --message "What is the capital of France?"
# → Paris.

mob agent-run send 1 --message "And of Germany?"
# → Berlin.
# (conversation history is maintained)

# Stop the agent
mob agent-run stop 1
```

## Architecture

```
                    ┌─────────────────────────────┐
                    │         mob CLI              │
                    │  (Python/Click)              │
                    └──────────┬──────────────────┘
                               │
              ┌────────────────┼────────────────┐
              │ local mode     │                │ remote mode
              │ (direct DB)    │                │ (HTTP)
              ▼                │                ▼
     ┌────────────┐           │       ┌────────────────┐
     │  SQLite DB  │           │       │  mob API       │
     └────────────┘           │       │  (FastAPI:8080) │
                               │       └───────┬────────┘
                               │               │
                               │               ▼
                               │       ┌────────────────┐
                               │       │  PostgreSQL     │
                               │       └────────────────┘
                               │
                               ▼
                    ┌─────────────────────────────┐
                    │     Kubernetes Cluster       │
                    │                              │
                    │  ┌────────────────────────┐  │
                    │  │  mob Operator (Rust)    │  │
                    │  │  watches AgentRun CRDs  │  │
                    │  │  reconciles pod state   │  │
                    │  └───────────┬────────────┘  │
                    │              │                │
                    │     ┌────────┼────────┐       │
                    │     ▼        ▼        ▼       │
                    │  ┌──────┐ ┌──────┐ ┌──────┐  │
                    │  │Agent │ │Agent │ │Agent │  │
                    │  │Pod 1 │ │Pod 2 │ │Pod N │  │
                    │  │:8081 │ │:8081 │ │:8081 │  │
                    │  └──────┘ └──────┘ └──────┘  │
                    └─────────────────────────────┘
```

### Components

| Component | Language | Purpose |
|-----------|----------|---------|
| **CLI** | Python/Click | User interface. Routes to local DB or remote API. |
| **API** | Python/FastAPI | REST API server (port 8080). Manages resources, forwards messages. |
| **Operator** | Rust/kube-rs | Kubernetes controller. Watches CRDs, creates pods, syncs state. |
| **Agent Pod** | Python/pydantic-ai | FastAPI server (port 8081) inside each agent pod. Processes messages with LLM. |
| **Database** | SQLite or PostgreSQL | Stores organizations, domains, agents, runs, tasks, skills. |

### Message Flow

```
mob agent-run send REF --message "hello"
  → CLI resolves REF to run_id
  → API looks up AgentRun CR status (state, pod name)
  → API gets pod IP from K8s API
  → API POSTs to http://<pod_ip>:8081/message
  → Agent sets annotation mob.io/agent-state=busy
  → Agent calls LLM via pydantic-ai
  → Agent sets annotation mob.io/agent-state=idle
  → Agent returns response
  → Response flows back to CLI
```

### Agent State Machine

```
pending → starting → idle ↔ busy → finished
                       ↓
                     failed
```

| State | Meaning |
|-------|---------|
| `pending` | AgentRun created, waiting for pod |
| `starting` | Pod created, container initializing |
| `idle` | Ready to accept messages |
| `busy` | Processing a message |
| `finished` | Completed gracefully |
| `failed` | Error or crash |

State is tracked at three levels:
1. **Pod annotations** — Agent writes `mob.io/agent-state` via K8s API
2. **CR status** — Operator reads annotations, updates AgentRun CR `.status.state`
3. **Database** — API reads CR status for live state

## CLI Reference

All resources can be referenced by **name**, **position number** (from list output), or **UUID**.

### Organizations

```bash
mob orgs                                    # List
mob org create --identifier acme --name "Acme Corp"
mob org show 1                              # By position
mob org edit acme --name "Acme Inc"         # By name
mob org delete 1                            # With confirmation
```

### Domains

```bash
mob domains                                 # List all
mob domains --org 1                         # Filter by org
mob domain create --identifier eng --name "Engineering" --org 1
mob domain show 1
mob domain edit 1 --name "Platform Engineering"
mob domain delete 1
```

### Agents

```bash
mob agents                                  # List all
mob agents --domain 1                       # Filter by domain
mob agent create \
  --name "researcher" \
  --template "mob-agent-pydantic:latest" \
  --domain 1 \
  --system-prompt "You are a research assistant." \
  --model-endpoint "anthropic:claude-sonnet-4-20250514"
mob agent show researcher                   # By name
mob agent edit 1 --model-endpoint "openai:gpt-4o"
mob agent delete 1
```

### Agent Runs

```bash
mob agent run researcher                     # Start an agent
mob agent run 1 --name "my-session"          # With custom name
mob agent-runs                               # List all runs
mob agent-runs --agent researcher            # Filter by agent
mob agent-runs --state idle                  # Filter by state
mob agent-run show 1                         # Show details
mob agent-run logs 1 --tail 50              # View pod logs
mob agent-run send 1 --message "Hello!"     # Send message
mob agent-run stop 1                         # Stop the agent
```

### Users & Groups

```bash
mob users
mob user create --email alice@acme.com --name "Alice"
mob groups --org 1
mob group create --name "engineers" --org 1
mob user grant alice --group 1              # Add to group
mob user revoke alice --group 1             # Remove from group
```

### Skills & Tasks

```bash
mob skills
mob skill create --name "web-search" --description "Search the web"
mob agent create --name "searcher" --template img --domain 1 --skill 1

mob task create --instruction "Find recent news about AI" --agent 1
```

### Configuration

```bash
mob init                    # Interactive setup (all environments)
mob init local              # Setup local only
mob configs                 # Show all config
mob config get env          # Get current environment
mob config set env dev      # Switch to dev environment
```

## Configuration

### Environments

| Environment | Mode | Database | API |
|-------------|------|----------|-----|
| `local` | local | SQLite (`~/.mob/mob.db`) | None (direct DB access) |
| `dev` | remote | PostgreSQL (localhost) | `http://localhost:8080` |
| `stg` | remote | PostgreSQL (remote) | Configurable |
| `prd` | remote | PostgreSQL (remote) | Configurable |

**Local mode** calls the service layer directly — no API server needed. **Remote mode** sends HTTP requests to the API.

### Environment Variables

All settings can be overridden with `MOB_` prefix:

| Variable | Default | Purpose |
|----------|---------|---------|
| `MOB_DATABASE_URL` | `sqlite+aiosqlite:///~/.mob/mob.db` | Database connection |
| `MOB_MODE` | `local` | `local` or `remote` |
| `MOB_API_BASE_URL` | `http://localhost:8080` | API URL (remote mode) |
| `MOB_KUBERNETES_NAMESPACE` | `mob` | K8s namespace |
| `MOB_DEBUG` | `false` | Debug logging |

### Config File

Stored at `~/.mob/config.json`. Override location with `MOB_CONFIG_FILE`.

## Agent System

### Default Agent Image

MOB ships with `mob-agent-pydantic:latest`, a default agent powered by [pydantic-ai](https://ai.pydantic.dev/). It runs a FastAPI server on port 8081 with:

- `GET /health` — Readiness check
- `POST /message` — Receive and process messages with LLM
- Conversation history across messages
- Bearer token authentication (via `AGENT_AUTH_TOKEN` env var)
- LLM timeout protection (default 120s)
- State reporting via K8s pod annotations

### Custom Agent Images

Any Docker image can be an agent. The contract:

1. **Listen on port 8081** with at least `GET /health` and `POST /message`
2. **Read environment variables:**
   - `AGENT_RUN_ID` — Run identifier
   - `AGENT_NAME` — Agent name
   - `AGENT_SYSTEM_PROMPT` — System prompt (if set)
   - `MODEL_ENDPOINT` — LLM endpoint (if set)
   - `AGENT_POD_NAME` — Own pod name (Downward API)
   - `AGENT_NAMESPACE` — K8s namespace (Downward API)
3. **Patch pod annotation** `mob.io/agent-state` with: `idle`, `busy`, `finished`, or `failed`
4. **Handle SIGTERM** gracefully

### LLM API Keys

Create a K8s secret for API keys:

```bash
kubectl -n mob create secret generic mob-agent-secrets \
  --from-literal=ANTHROPIC_API_KEY=sk-ant-... \
  --from-literal=OPENAI_API_KEY=sk-...
```

Agent pods automatically mount this secret as environment variables (optional — pods start even without it).

## Kubernetes Resources

### AgentRun CRD

```yaml
apiVersion: mob.io/v1
kind: AgentRun
metadata:
  name: ar-abc12345
spec:
  agentId: "uuid"
  agentName: "researcher"
  agentTemplate: "mob-agent-pydantic:latest"
  systemPrompt: "You are a research assistant."
  modelEndpoint: "anthropic:claude-haiku-4-5-20251001"
status:
  state: Idle
  podName: mob-agent-ar-abc12345
  lastTransitionTime: "2026-03-24T07:00:00Z"
```

### RBAC

Three separate service accounts with least-privilege roles:

| Service Account | Permissions | Scope |
|-----------------|-------------|-------|
| `mob-operator` | Manage CRDs, pods, events | ClusterRole |
| `mob-api` | Read pods, CRUD agentruns | Namespace Role |
| `mob-agent` | Get/patch pods (self-annotate) | Namespace Role |

### Deployments

Managed via Kustomize with overlays for each environment:

```bash
kubectl apply -k deploy/overlays/dev/        # Local Kind
kubectl apply -k deploy/overlays/staging/     # Staging
kubectl apply -k deploy/overlays/production/  # Production
```

## Development

### Setup

```bash
make setup                 # Install Python dependencies
make install               # Install mob CLI
mob init local             # Initialize config
mob migrate                # Create DB tables
```

### Local Cluster

```bash
make dev-up                # Start Kind + PostgreSQL + deploy everything
make dev-status            # Check pod status
make dev-logs              # Tail API logs
make dev-kind-psql         # Open PostgreSQL shell
make dev-kind-rebuild      # Rebuild API + redeploy
make dev-kind-rebuild-agent # Rebuild agent image + load to Kind
make dev-kind-reset        # Destroy + recreate everything
make dev-down              # Stop everything
```

### Building Images

```bash
make build                 # mob-api:latest
make build-agent           # mob-agent-pydantic:latest
cd operator && docker build -t mob-operator:latest .
```

### Testing

```bash
make test                  # Run all tests
make lint                  # flake8 + mypy
make format                # black formatter
```

### Project Structure

```
mob/
├── src/mob/
│   ├── cli/               # CLI commands (Click)
│   ├── api/               # REST API routes (FastAPI)
│   ├── services/          # Business logic
│   ├── models/            # SQLAlchemy ORM models
│   ├── agent/             # Default agent entrypoint
│   ├── k8s/               # Kubernetes manager
│   ├── config.py          # Configuration system
│   ├── database.py        # DB setup + migrations
│   └── schemas.py         # Pydantic request/response schemas
├── operator/
│   └── src/
│       ├── main.rs         # Controller entrypoint
│       ├── crd/            # AgentRun CRD definition
│       ├── controller/     # Reconciliation logic
│       └── resources/      # Pod builder
├── deploy/
│   ├── base/              # K8s manifests (CRDs, RBAC, deployments)
│   └── overlays/          # Environment-specific patches
├── infra/                 # Terraform (AWS, GCP)
├── tests/                 # pytest suite
├── Dockerfile             # API image
├── Dockerfile.agent       # Agent image
└── Makefile               # 30+ targets
```

## Deployment

### Production (AWS)

```bash
make infra-init-aws ENV=prd
make infra-plan-aws ENV=prd
make infra-apply-aws ENV=prd
make deploy-production
```

### Production (GCP)

```bash
make infra-init-gcp ENV=prd
make infra-plan-gcp ENV=prd
make infra-apply-gcp ENV=prd
make deploy-production
```

## Technology Stack

| Layer | Technology |
|-------|------------|
| CLI | Python 3.11+, Click |
| API | FastAPI, Uvicorn |
| ORM | SQLAlchemy (async) |
| Database | SQLite (local), PostgreSQL 16 (remote) |
| Agent Runtime | pydantic-ai 1.0+ |
| Operator | Rust, kube-rs 0.98 |
| Container | Docker, Kind (dev) |
| Orchestration | Kubernetes 1.31+ |
| Config Management | Kustomize |
| Infrastructure | Terraform (AWS, GCP) |
| Package Manager | uv |

## License

MIT
