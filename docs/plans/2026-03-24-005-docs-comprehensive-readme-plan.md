---
title: "docs: Comprehensive README for MOB"
type: feat
status: completed
date: 2026-03-24
---

# docs: Comprehensive README for MOB

## Overview

Create a fully-detailed README.md for the MOB project that covers every working aspect of the tool, its philosophy, goals, architecture, and usage. The README should serve as the single entry point for anyone discovering the project — from first-time users to contributors.

## Problem Statement / Motivation

MOB currently has no README.md. There is no single document that explains what the project is, how to use it, or why it exists. The project has a rich architecture (Python CLI/API + Rust operator + K8s CRDs + pydantic-ai agents) that needs clear documentation for adoption and contribution.

## Proposed Solution

Write a comprehensive `README.md` at the project root covering all aspects of the tool. The README should follow the Ankane-style template: imperative voice, concise prose, code-first examples, and standard section ordering.

## Content Plan

### Section 1: Header & Badges
- Project name, tagline: "AI Agent Orchestration Platform — cloud-native, provider agnostic"
- Version badge, Python version, license

### Section 2: Philosophy & Goals
- Why MOB exists: orchestrate AI agents at scale on Kubernetes
- Cloud-native, provider-agnostic design
- Works locally (Kind + SQLite) or at scale (EKS/GKE + PostgreSQL)
- Multi-tenant by design (organizations → domains → agents)
- Agent-as-a-pod: agents run as K8s pods with full lifecycle management
- State machine philosophy (pending → starting → idle ↔ busy → finished/failed)
- Operator pattern: reconciliation loop for reliable state tracking

### Section 3: Quick Start
- Prerequisites (Python 3.11+, uv, Docker, Kind, kubectl)
- Install CLI: `make setup && make install`
- Initialize: `mob init local`
- Run migrations: `mob migrate`
- Create org/domain/agent, run agent, send message
- Complete working example in ~10 commands

### Section 4: Architecture
- ASCII diagram showing CLI → API → Operator → Agent Pods
- Component descriptions (CLI, API, Operator, Agent, Database)
- Communication flows (message delivery, state annotation sync)
- State machine diagram

### Section 5: CLI Reference
- All commands grouped by resource (org, domain, user, group, agent, agent-run, skill, config)
- Examples for each command group
- Resource reference system (by name, position, or UUID)

### Section 6: Configuration
- Environments (local, dev, staging, production)
- Config file location (~/.mob/config.json)
- Environment variables (MOB_ prefix)
- Mode difference (local = direct DB, remote = API client)

### Section 7: Agent System
- Creating agents (template, system prompt, model endpoint, skills)
- Running agents (`mob agent run`)
- Sending messages (`mob agent-run send`)
- Agent lifecycle and state transitions
- Default pydantic-ai agent image
- Custom agent images (contract: /health on 8081, pod annotations)

### Section 8: Kubernetes Resources
- AgentRun CRD spec
- Operator behavior (reconciliation, finalizers, state derivation)
- RBAC setup (operator, API, agent service accounts)
- Kustomize overlays (dev, staging, production)

### Section 9: Development
- Local setup with Kind + PostgreSQL
- Makefile targets reference
- Building Docker images
- Running tests
- Project structure (directory tree)

### Section 10: Deployment
- Dev (Kind), Staging, Production
- Terraform (AWS, GCP)
- Required secrets (database, API keys)

### Section 11: Technology Stack
- Python dependencies with purpose
- Rust operator dependencies
- Infrastructure tools

## Files to Create

- `README.md` — The comprehensive README

## Files to Reference (source material)

- `BIGBANG.md` — Original vision and domain model
- `pyproject.toml` — Dependencies and metadata
- `Makefile` — All build targets
- `src/mob/config.py` — Configuration system
- `src/mob/cli/` — All CLI commands
- `src/mob/agent/entrypoint.py` — Agent entrypoint
- `operator/src/` — Rust operator
- `deploy/base/` — K8s manifests
- `docs/ideation/2026-03-23-open-ideation.md` — Project vision

## Acceptance Criteria

- [ ] README.md exists at project root
- [ ] Covers philosophy, goals, and design principles
- [ ] Quick start guide works end-to-end (verified)
- [ ] All CLI commands documented with examples
- [ ] Architecture diagram included
- [ ] Agent lifecycle and state machine documented
- [ ] Development setup instructions complete
- [ ] Configuration system documented
- [ ] K8s resources documented
- [ ] Technology stack listed

## Sources & References

- Explore agent output with full project analysis
- `docs/solutions/integration-issues/pydantic-ai-agent-image-k8s-orchestration.md` — Lessons learned
