.PHONY: setup build build-agent test lint format deploy clean install migrate \
       local-up local-down local-status local-reset \
       local-rebuild-operator local-rebuild-agent \
       dev-up dev-down dev-status dev-logs dev-psql \
       dev-rebuild dev-rebuild-agent dev-reset \
       deploy-dev deploy-staging deploy-production \
       infra-init-aws infra-init-gcp \
       infra-plan-aws infra-plan-gcp \
       infra-apply-aws infra-apply-gcp \
       build-agent-social build-agent-pi build-agent-openclaw \
       local-rebuild-agent-social local-rebuild-agent-pi local-rebuild-agent-openclaw \
       build-webhook-gateway local-rebuild-webhook-gateway \
       run

PYTHON := python3
UV := uv
APP_IMAGE := mob-api
APP_TAG := latest
AGENT_IMAGE := mob-agent-pydantic
AGENT_TAG := latest
SOCIAL_IMAGE := mob-agent-social
PI_IMAGE := mob-agent-pi
OPENCLAW_IMAGE := mob-agent-openclaw
WEBHOOK_IMAGE := mob-webhook-gateway
KIND_CLUSTER := mob-local
KIND_CTX := kind-$(KIND_CLUSTER)
ENV ?= dev

## setup: install dependencies and dev tools
setup:
	$(UV) sync --frozen

## migrate: run database schema migrations
migrate:
	$(UV) run mob migrate

## install: install the mob CLI into the local environment
install:
	$(UV) tool install --force --editable .

## build: build the API Docker image
build:
	docker build -t $(APP_IMAGE):$(APP_TAG) .

## build-agent: build the default pydantic-ai agent Docker image
build-agent:
	docker build -t $(AGENT_IMAGE):$(AGENT_TAG) -f Dockerfile.agent .

## test: run the test suite
test:
	$(UV) run pytest tests/ -v

# ---------- Local mode targets ----------

## local-up: start local environment (Kind + operator, SQLite, no PostgreSQL)
local-up:
	./scripts/local-setup.sh setup

## local-down: tear down local environment
local-down:
	./scripts/local-setup.sh teardown

## local-status: show local environment status
local-status:
	./scripts/local-setup.sh status

## local-reset: destroy and recreate local environment
local-reset:
	./scripts/local-setup.sh reset

## local-rebuild-operator: rebuild operator image and redeploy
local-rebuild-operator:
	docker build -t mob-operator:latest -f ./operator/Dockerfile ./operator/
	kind load docker-image mob-operator:latest --name $(KIND_CLUSTER)
	kubectl --context $(KIND_CTX) -n mob rollout restart deployment/mob-operator

## local-rebuild-agent: rebuild agent image and load to Kind
local-rebuild-agent: build-agent
	kind load docker-image $(AGENT_IMAGE):$(AGENT_TAG) --name $(KIND_CLUSTER)

## build-agent-social: build the social agent Docker image
build-agent-social:
	docker build -t $(SOCIAL_IMAGE):$(AGENT_TAG) -f Dockerfile.agent-social .

## build-agent-pi: build the Pi coding agent Docker image
build-agent-pi:
	docker build -t $(PI_IMAGE):$(AGENT_TAG) -f Dockerfile.agent-pi .

## build-agent-openclaw: build the OpenClaw agent Docker image
build-agent-openclaw:
	docker build -t $(OPENCLAW_IMAGE):$(AGENT_TAG) -f Dockerfile.agent-openclaw .

## local-rebuild-agent-social: rebuild social agent image and load to Kind
local-rebuild-agent-social: build-agent-social
	kind load docker-image $(SOCIAL_IMAGE):$(AGENT_TAG) --name $(KIND_CLUSTER)

## local-rebuild-agent-pi: rebuild Pi agent image and load to Kind
local-rebuild-agent-pi: build-agent-pi
	kind load docker-image $(PI_IMAGE):$(AGENT_TAG) --name $(KIND_CLUSTER)

## local-rebuild-agent-openclaw: rebuild OpenClaw agent image and load to Kind
local-rebuild-agent-openclaw: build-agent-openclaw
	kind load docker-image $(OPENCLAW_IMAGE):$(AGENT_TAG) --name $(KIND_CLUSTER)

## build-webhook-gateway: build the webhook gateway Docker image
build-webhook-gateway:
	docker build -t $(WEBHOOK_IMAGE):$(AGENT_TAG) -f Dockerfile.webhook-gateway .

## local-rebuild-webhook-gateway: rebuild webhook gateway and load to Kind
local-rebuild-webhook-gateway: build-webhook-gateway
	kind load docker-image $(WEBHOOK_IMAGE):$(AGENT_TAG) --name $(KIND_CLUSTER)

# ---------- Dev mode targets ----------

## dev-up: start dev environment (Kind + PostgreSQL + API)
dev-up:
	./scripts/dev-setup.sh setup

## dev-down: stop dev environment
dev-down:
	./scripts/dev-setup.sh teardown

## dev-status: show dev environment status
dev-status:
	./scripts/dev-setup.sh status

## dev-logs: tail API pod logs
dev-logs:
	kubectl --context $(KIND_CTX) -n mob logs -f -l app.kubernetes.io/component=api

## dev-psql: open psql shell against local PostgreSQL
dev-psql:
	docker exec -it mob-postgres psql -U mob_admin -d mob

## dev-rebuild: rebuild API image and redeploy to Kind cluster
dev-rebuild: build
	kind load docker-image $(APP_IMAGE):$(APP_TAG) --name $(KIND_CLUSTER)
	kubectl --context $(KIND_CTX) -n mob rollout restart deployment/mob-api
	kubectl --context $(KIND_CTX) -n mob rollout status deployment/mob-api --timeout=120s

## dev-rebuild-agent: rebuild agent image and load to Kind
dev-rebuild-agent: build-agent
	kind load docker-image $(AGENT_IMAGE):$(AGENT_TAG) --name $(KIND_CLUSTER)

## dev-reset: destroy and recreate dev environment
dev-reset:
	./scripts/dev-setup.sh reset

## run: legacy alias for dev-up
run: dev-up

# ---------- Quality targets ----------

## lint: run flake8 and mypy
lint:
	$(UV) run flake8 src/ tests/
	$(UV) run mypy src/

## format: run black formatter
format:
	$(UV) run black src/ tests/

# ---------- Deployment targets ----------

## deploy-dev: deploy to dev environment (kind cluster)
deploy-dev:
	kubectl apply -k deploy/overlays/dev/

## deploy-staging: deploy to staging environment
deploy-staging:
	kubectl apply -k deploy/overlays/staging/

## deploy-production: deploy to production environment
deploy-production:
	kubectl apply -k deploy/overlays/production/

# ---------- Infrastructure targets ----------

## infra-init-aws: initialize Terraform for AWS
infra-init-aws:
	cd infra/aws && terraform init -backend-config="key=$(ENV)/terraform.tfstate"

## infra-plan-aws: plan AWS infrastructure changes
infra-plan-aws:
	cd infra/aws && terraform plan -var-file=../environments/$(ENV)/aws.tfvars

## infra-apply-aws: apply AWS infrastructure changes
infra-apply-aws:
	cd infra/aws && terraform apply -var-file=../environments/$(ENV)/aws.tfvars

## infra-init-gcp: initialize Terraform for GCP
infra-init-gcp:
	cd infra/gcp && terraform init -backend-config="prefix=$(ENV)/terraform.tfstate"

## infra-plan-gcp: plan GCP infrastructure changes
infra-plan-gcp:
	cd infra/gcp && terraform plan -var-file=../environments/$(ENV)/gcp.tfvars

## infra-apply-gcp: apply GCP infrastructure changes
infra-apply-gcp:
	cd infra/gcp && terraform apply -var-file=../environments/$(ENV)/gcp.tfvars

# ---------- Cleanup ----------

## clean: remove build artifacts and kind cluster
clean:
	rm -rf dist/ build/ *.egg-info .pytest_cache .mypy_cache htmlcov .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	-kind delete cluster --name $(KIND_CLUSTER)
	docker compose down -v 2>/dev/null || true
