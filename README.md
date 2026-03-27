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
- **Operator pattern** — A Rust controller reconciles desired state (Session CRDs) with actual state (pod annotations). State is never guessed — it's observed.

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
mob sessions

# Chat
mob session send 1 --message "What is the capital of France?"
# → Paris.

mob session send 1 --message "And of Germany?"
# → Berlin.
# (conversation history is maintained)

# Stop the agent
mob session stop 1
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
                    │  │  watches Session CRDs   │  │
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
| **Database** | SQLite or PostgreSQL | Stores organizations, domains, agents, sessions, tasks, skills. |

### Message Flow

```
mob session send REF --message "hello"
  → CLI resolves REF to session_id
  → API looks up Session CR status (state, pod name)
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
| `pending` | Session created, waiting for pod |
| `starting` | Pod created, container initializing |
| `idle` | Ready to accept messages |
| `busy` | Processing a message |
| `finished` | Completed gracefully |
| `failed` | Error or crash |

State is tracked at three levels:
1. **Pod annotations** — Agent writes `mob.io/agent-state` via K8s API
2. **CR status** — Operator reads annotations, updates Session CR `.status.state`
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

#### YAML Agent Definitions

Agents can be defined in YAML files for version control and reproducibility:

```yaml
# agent.yaml
name: researcher
agent_template: mob-agent-pydantic:latest
domain: dev
system_prompt: "You are a research assistant."
model_endpoint: "anthropic:claude-haiku-4-5-20251001"
skills:
  - code-review
env:
  ANTHROPIC_API_KEY: ""    # required at runtime
  LLM_TIMEOUT: "120"      # default value
custom:
  temperature: "0.7"
```

```bash
mob agent apply agent.yaml                   # Create or update
mob agent create --file agent.yaml           # Create only
```

### Sessions

```bash
mob agent run researcher                     # Start a session
mob agent run 1 --name "my-session"          # With custom name
mob agent run 1 --env ANTHROPIC_API_KEY=sk-ant-...  # With env override
mob sessions                                 # List all sessions
mob sessions --agent researcher              # Filter by agent
mob sessions --state idle                    # Filter by state
mob session show 1                           # Show details
mob session logs 1 --tail 50                # View pod logs
mob session send 1 --message "Hello!"       # Send message
mob session stop 1                           # Stop the session
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

### Templates

Agent templates are registered Docker images with declared capabilities and resource limits.

```bash
mob templates                               # List all templates

mob template create \
  --name mob-agent-social \
  --image mob-agent-social:latest \
  --runtime pydantic-ai \
  --description "Social agent with messaging and social media" \
  --capabilities "whatsapp,telegram,linkedin,instagram"

mob template create \
  --name mob-agent-pi \
  --image mob-agent-pi:latest \
  --runtime pi \
  --description "Pi coding agent with shell tools" \
  --capabilities "coding,shell,browser" \
  --cpu-limit 2000m \
  --memory-limit 2Gi

mob template show mob-agent-social          # Show details
mob template edit 1 --capabilities "whatsapp,telegram"
mob template delete 1
```

When creating an agent, `agent_template` resolves against the registry:

```yaml
# agent.yaml — "mob-agent-social" resolves to "mob-agent-social:latest"
agent_template: mob-agent-social
```

Raw Docker image references (containing `:` or `/`) are also accepted for backward compatibility.

### Skills

Skills follow the [AgentSkills.io](https://agentskills.io) standard. Import them from `SKILL.md` files or create them via CLI.

#### Import from SKILL.md

Create a skill directory with a `SKILL.md` file:

```
brand-voice/
└── SKILL.md
```

```markdown
---
name: brand-voice
description: Maintain consistent brand voice across all communications.
license: MIT
metadata:
  author: my-team
  version: "1.0"
---

# Brand Voice Guidelines

## Tone
- Professional but approachable
- Concise — prefer short sentences

## Platform-Specific
- **LinkedIn**: Thought leadership, 1-3 paragraphs max
- **WhatsApp/Telegram**: Conversational, quick responses
```

Import it:

```bash
mob skill import ./brand-voice/             # From directory (looks for SKILL.md)
mob skill import ./brand-voice/SKILL.md     # From file directly
```

#### Manage skills

```bash
mob skills                                  # List all
mob skill show brand-voice                  # Show details + full SKILL.md content
mob skill create \
  --name "code-review" \
  --description "Reviews code for quality and patterns." \
  --skill-md "# Code Review\n\nCheck for..."
mob skill edit 1 --description "Updated description"
mob skill delete 1
```

#### Attach skills to agents

Skills are attached to agents via YAML or CLI:

```yaml
# agent.yaml
skills:
  - brand-voice
  - social-media-guidelines
```

When a session starts, skills are packed into a Kubernetes ConfigMap and mounted at `/skills/` inside the agent pod. The agent reads them at startup and incorporates them into its behavior.

### Tasks

```bash
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

### Agent Template Images

MOB ships with four agent template images:

| Template | Image | Runtime | Capabilities |
|----------|-------|---------|-------------|
| `mob-agent-pydantic` | `mob-agent-pydantic:latest` | pydantic-ai | Base LLM chat |
| `mob-agent-social` | `mob-agent-social:latest` | pydantic-ai | WhatsApp, Telegram, LinkedIn, Instagram |
| `mob-agent-pi` | `mob-agent-pi:latest` | pi | Coding, shell, browser |
| `mob-agent-openclaw` | `mob-agent-openclaw:latest` | openclaw | Coding, shell, browser, skills |

Build them:

```bash
make build-agent               # mob-agent-pydantic
make build-agent-social        # mob-agent-social (extends pydantic)
make build-agent-pi            # mob-agent-pi (Node.js + adapter)
make build-agent-openclaw      # mob-agent-openclaw (Python + adapter)
make build-webhook-gateway     # mob-webhook-gateway
```

Load into Kind:

```bash
make local-rebuild-agent
make local-rebuild-agent-social
make local-rebuild-agent-pi
make local-rebuild-agent-openclaw
make local-rebuild-webhook-gateway
```

### Custom Agent Images

Any Docker image can be an agent. The contract:

1. **Listen on port 8081** with at least `GET /health` and `POST /message`
2. **Read environment variables:**
   - `SESSION_ID` — Session identifier
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

## Walkthrough: Social Media Agent with Skills

End-to-end example: register templates, import skills, create a social media agent, and chat with it.

### 1. Register templates

```bash
mob template create \
  --name mob-agent-social \
  --image mob-agent-social:latest \
  --runtime pydantic-ai \
  --description "Social agent with WhatsApp, Telegram, LinkedIn, Instagram" \
  --capabilities "whatsapp,telegram,linkedin,instagram"
```

### 2. Import skills from SKILL.md files

```bash
# Create skill directories with AgentSkills.io format
mkdir -p skills/brand-voice
cat > skills/brand-voice/SKILL.md << 'EOF'
---
name: brand-voice
description: Maintain consistent brand voice across all communications.
license: MIT
metadata:
  author: my-team
  version: "1.0"
---

# Brand Voice Guidelines
- Professional but approachable
- LinkedIn: thought leadership, 1-3 paragraphs
- WhatsApp/Telegram: conversational, quick responses
EOF

mob skill import skills/brand-voice/
# → Skill 'brand-voice' imported.
```

### 3. Create the agent via YAML

```yaml
# social-agent.yaml
name: social-bot
agent_template: mob-agent-social    # resolves to mob-agent-social:latest
domain: demo-dev
system_prompt: |
  You are a social media assistant.
  You can send messages via WhatsApp and Telegram,
  and post content on LinkedIn and Instagram.
model_endpoint: "anthropic:claude-sonnet-4-6-20260320"
skills:
  - brand-voice                     # resolved by name to UUID
env:
  ANTHROPIC_API_KEY: ""             # required at runtime
  TELEGRAM_BOT_TOKEN: ""
custom:
  whatsapp_enabled: "true"
  telegram_enabled: "true"
  linkedin_enabled: "true"
  instagram_enabled: "false"
```

```bash
mob agent apply social-agent.yaml
# → Agent 'social-bot' created.
# → agent_template: mob-agent-social:latest  (resolved from registry)
```

### 4. Start a session with API key

```bash
mob agent run social-bot --env ANTHROPIC_API_KEY=sk-ant-...
# → Session 'social-bot-c51a9731' created (state: pending).
```

### 5. Verify skills are mounted

```bash
# Check the skills ConfigMap
kubectl -n mob get configmap
# → mob-skills-social-bot-c51a9731   1   30s

# Verify inside the pod
kubectl -n mob exec mob-agent-s-cff6d43e -- ls /skills/
# → brand-voice.md

# Check integration env vars
kubectl -n mob exec mob-agent-s-cff6d43e -- env | grep AGENT_CUSTOM
# → AGENT_CUSTOM_WHATSAPP_ENABLED=true
# → AGENT_CUSTOM_TELEGRAM_ENABLED=true
# → AGENT_CUSTOM_LINKEDIN_ENABLED=true
# → AGENT_CUSTOM_INSTAGRAM_ENABLED=false
```

### 6. Chat

```bash
mob session send social-bot-c51a9731 \
  --message "Draft a LinkedIn post about AI agent orchestration."
# → The agent responds following brand-voice guidelines,
#   with LinkedIn and WhatsApp tools available.

mob session send social-bot-c51a9731 \
  --message "Now post that to LinkedIn."
# → Agent calls post_to_linkedin tool (requires valid LINKEDIN_ACCESS_TOKEN)

mob session stop social-bot-c51a9731
```

## Messaging & Social Integrations

### Platform Tools

When an agent uses the `mob-agent-social` template, these tools are registered based on `custom` config flags:

| Tool | Enabled by | Credentials needed |
|------|-----------|-------------------|
| `send_whatsapp_message` | `whatsapp_enabled: "true"` | `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID` |
| `send_telegram_message` | `telegram_enabled: "true"` | `TELEGRAM_BOT_TOKEN` |
| `get_telegram_updates` | `telegram_enabled: "true"` | `TELEGRAM_BOT_TOKEN` |
| `post_to_linkedin` | `linkedin_enabled: "true"` | `LINKEDIN_ACCESS_TOKEN`, `LINKEDIN_PERSON_URN` |
| `post_to_instagram` | `instagram_enabled: "true"` | `INSTAGRAM_ACCESS_TOKEN`, `INSTAGRAM_BUSINESS_ACCOUNT_ID` |

### Webhook Gateway

For receiving inbound messages from WhatsApp and Telegram, deploy the webhook gateway:

```bash
make build-webhook-gateway
kubectl apply -f deploy/base/webhook-gateway.yaml
```

The gateway runs on port 8082 and routes incoming webhooks to agent pods:

```
WhatsApp/Telegram → https://<domain>/webhooks/<platform>/<session-id>
                  → Webhook Gateway (:8082)
                  → Agent Pod (:8081/message)
                  → Response sent back via platform API
```

**Webhook URLs:**
- Telegram: `https://<domain>/webhooks/telegram/<session-id>`
- WhatsApp: `https://<domain>/webhooks/whatsapp/<session-id>`

**Security:** The gateway verifies Telegram's `X-Telegram-Bot-Api-Secret-Token` header and WhatsApp's `X-Hub-Signature-256` HMAC signature.

## Kubernetes Resources

### Session CRD

```yaml
apiVersion: mob.io/v1
kind: Session
metadata:
  name: s-abc12345
spec:
  agentId: "uuid"
  agentName: "researcher"
  agentTemplate: "mob-agent-pydantic:latest"
  systemPrompt: "You are a research assistant."
  modelEndpoint: "anthropic:claude-haiku-4-5-20251001"
status:
  state: Idle
  podName: mob-agent-s-abc12345
  lastTransitionTime: "2026-03-24T07:00:00Z"
```

### RBAC

Three separate service accounts with least-privilege roles:

| Service Account | Permissions | Scope |
|-----------------|-------------|-------|
| `mob-operator` | Manage CRDs, pods, events | ClusterRole |
| `mob-api` | Read pods, CRUD sessions | Namespace Role |
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
│   ├── agent/
│   │   ├── entrypoint.py  # Default pydantic-ai agent server
│   │   ├── integrations/  # WhatsApp, Telegram, LinkedIn, Instagram tools
│   │   └── adapters/      # Pi and OpenClaw runtime adapters
│   ├── webhook/           # Webhook gateway for inbound messages
│   ├── k8s/               # Kubernetes manager
│   ├── config.py          # Configuration system
│   ├── database.py        # DB setup + migrations
│   └── schemas.py         # Pydantic request/response schemas
├── operator/
│   └── src/
│       ├── main.rs         # Controller entrypoint
│       ├── crd/            # Session CRD definition
│       ├── controller/     # Reconciliation logic
│       └── resources/      # Pod builder
├── deploy/
│   ├── base/              # K8s manifests (CRDs, RBAC, deployments)
│   └── overlays/          # Environment-specific patches
├── infra/                 # Terraform (AWS, GCP)
├── examples/              # YAML agent definitions
├── tests/                 # pytest suite
├── Dockerfile             # API image
├── Dockerfile.agent       # Base pydantic-ai agent image
├── Dockerfile.agent-social  # Social agent (messaging + social media)
├── Dockerfile.agent-pi      # Pi coding agent
├── Dockerfile.agent-openclaw # OpenClaw agent
├── Dockerfile.webhook-gateway # Webhook gateway
└── Makefile               # 40+ targets
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
