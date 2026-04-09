# mob — AI Agent Orchestration for Kubernetes

Run AI agents as pods. Chat with them. Let Kubernetes manage their lifecycle.

---

## What it does

mob turns AI agents into infrastructure. You define an agent, `mob agent run` creates a Kubernetes pod, and you talk to it via CLI. The operator watches state transitions; the agent patches its own annotations. State is never guessed — it's observed.

```
mob agent run researcher
mob session send researcher "Summarize this PR."
mob session stop researcher
```

---

## Install

```bash
git clone https://github.com/cardosoccc/mob.git
cd mob
make setup && make install
mob init local
mob migrate
make dev-up
```

**Requirements:** Python 3.11+, uv, Docker, Kind, kubectl

---

## Core concepts

**Agent** — a Docker image with a FastAPI server on port 8081. Can be the default pydantic-ai image or your own.

**Session** — a running agent pod. Created by `mob agent run`, tracked via a Kubernetes CRD.

**Operator** — a Rust controller that reconciles Session CRDs with pod state.

**Skill** — a markdown document (SKILL.md) injected into pods at `/skills/`. Follows [AgentSkills.io](https://agentskills.io) format.

---

## State machine

```
pending → starting → idle ↔ busy → finished
                       ↓
                     failed
```

State lives in three places: pod annotations → CRD status → database. The operator keeps them in sync.

---

## Quick example

```bash
# Bootstrap
mob org create --identifier acme --name "Acme"
mob domain create --identifier eng --name "Engineering" --org 1

# Create an agent
mob agent create \
  --name assistant \
  --template mob-agent-pydantic:latest \
  --domain 1 \
  --system-prompt "You are a helpful assistant." \
  --model-endpoint "anthropic:claude-haiku-4-5-20251001"

# Run and chat
mob agent run assistant
mob session send 1 --message "What is 2+2?"
mob session stop 1
```

---

## Agent YAML

```yaml
# agent.yaml
name: researcher
agent_template: mob-agent-pydantic:latest
domain: eng
system_prompt: "You are a research assistant."
model_endpoint: "anthropic:claude-sonnet-4-6"
skills:
  - code-review
env:
  ANTHROPIC_API_KEY: ""
```

```bash
mob agent apply agent.yaml
```

---

## Skills

```bash
# Import from a SKILL.md file
mob skill import ./brand-voice/

# Attach in YAML
skills:
  - brand-voice
```

Skills are packed into a ConfigMap and mounted at `/skills/` when the session starts.

---

## Architecture

```
CLI ──────────────────────────────────────────────────┐
 │ local mode (direct DB)       remote mode (HTTP)    │
 ▼                              ▼                      │
SQLite                        mob API (FastAPI:8080)   │
                                 │                     │
                              PostgreSQL               │
                                                       ▼
                          Kubernetes Cluster
                           ┌──────────────┐
                           │  Operator    │  ← watches Session CRDs
                           └──────┬───────┘
                          ┌───────┼───────┐
                          ▼       ▼       ▼
                        Agent   Agent   Agent
                        Pod     Pod     Pod
                        :8081   :8081   :8081
```

---

## Components

| Component | Language | Role |
|-----------|----------|------|
| CLI | Python / Click | User interface |
| API | Python / FastAPI | REST API (port 8080) |
| Operator | Rust / kube-rs | CRD controller |
| Agent Pod | Python / pydantic-ai | LLM server (port 8081) |
| Database | SQLite or PostgreSQL | Persistent state |

---

## Included agent images

| Image | Runtime | Built for |
|-------|---------|-----------|
| `mob-agent-pydantic` | pydantic-ai | General LLM chat |
| `mob-agent-social` | pydantic-ai | WhatsApp, Telegram, LinkedIn, Instagram |
| `mob-agent-pi` | Pi | Coding, shell, browser |
| `mob-agent-openclaw` | OpenClaw | Coding, shell, browser, skills |

```bash
make build-agent
make build-agent-social
make build-agent-pi
make build-agent-openclaw
```

---

## Custom agents

Any image works. The contract:

1. Serve `GET /health` and `POST /message` on port 8081
2. Read env: `SESSION_ID`, `AGENT_NAME`, `AGENT_SYSTEM_PROMPT`, `MODEL_ENDPOINT`
3. Patch pod annotation `mob.io/agent-state` → `idle | busy | finished | failed`
4. Handle `SIGTERM`

---

## CLI reference

```bash
# Orgs & Domains
mob orgs && mob org create --identifier acme --name "Acme"
mob domains && mob domain create --identifier eng --name "Eng" --org 1

# Agents
mob agents && mob agent create ... && mob agent apply agent.yaml
mob agent show researcher && mob agent edit 1 --model-endpoint "openai:gpt-4o"

# Sessions
mob agent run researcher
mob sessions --state idle
mob session send 1 --message "Hello"
mob session logs 1 --tail 50
mob session stop 1

# Skills
mob skills && mob skill import ./my-skill/ && mob skill show brand-voice

# Users & Groups
mob users && mob user create --email alice@example.com --name "Alice"
mob groups --org 1 && mob group create --name engineers --org 1
mob user grant alice --group 1
```

---

## Environments

| Env | Mode | Database | API |
|-----|------|----------|-----|
| `local` | direct | SQLite (`~/.mob/mob.db`) | — |
| `dev` | remote | PostgreSQL (localhost) | `localhost:8080` |
| `stg` / `prd` | remote | PostgreSQL | configurable |

```bash
mob config set env dev
mob config get env
```

---

## Development

```bash
make dev-up               # Kind + PostgreSQL + deploy
make dev-status           # Pod status
make dev-logs             # API logs
make dev-kind-rebuild     # Rebuild API + redeploy
make dev-kind-reset       # Nuke + recreate

make test                 # pytest
make lint                 # flake8 + mypy
make format               # black
```

---

## Deploy to production

```bash
# AWS
make infra-init-aws ENV=prd && make infra-apply-aws ENV=prd && make deploy-production

# GCP
make infra-init-gcp ENV=prd && make infra-apply-gcp ENV=prd && make deploy-production
```

---

## License

MIT
