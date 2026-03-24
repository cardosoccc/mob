.PHONY: setup build test run lint format deploy clean install \
       dev-up dev-down dev-logs \
       dev-kind-up dev-kind-down dev-kind-status dev-kind-logs \
       dev-kind-psql dev-kind-rebuild dev-kind-reset \
       deploy-dev deploy-staging deploy-production \
       infra-init-aws infra-init-gcp \
       infra-plan-aws infra-plan-gcp \
       infra-apply-aws infra-apply-gcp \
       migrate

PYTHON := python3
UV := uv
APP_IMAGE := mob-api
APP_TAG := latest
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

## build: build the Docker image
build:
	docker build -t $(APP_IMAGE):$(APP_TAG) .

## test: run the test suite
test:
	$(UV) run pytest tests/ -v

## dev-up: start local development environment (Kind + PostgreSQL)
dev-up: dev-kind-up

## dev-down: stop local development environment
dev-down: dev-kind-down

## dev-logs: tail logs from local development environment
dev-logs: dev-kind-logs

## run: launch the application locally with kind cluster (legacy alias for dev-kind-up)
run: dev-kind-up

## dev-kind-up: create Kind cluster with local PostgreSQL and deploy the app
dev-kind-up:
	./scripts/dev-setup.sh setup

## dev-kind-down: tear down the Kind cluster and all resources
dev-kind-down:
	./scripts/dev-setup.sh teardown

## dev-kind-status: show pod and service status in the local cluster
dev-kind-status:
	./scripts/dev-setup.sh status

## dev-kind-logs: tail API pod logs
dev-kind-logs:
	kubectl --context $(KIND_CTX) -n mob logs -f -l app.kubernetes.io/component=api

## dev-kind-psql: open a psql shell against the local PostgreSQL
dev-kind-psql:
	docker exec -it mob-postgres psql -U mob_admin -d mob

## dev-kind-rebuild: rebuild the Docker image and redeploy to the Kind cluster
dev-kind-rebuild: build
	kind load docker-image $(APP_IMAGE):$(APP_TAG) --name $(KIND_CLUSTER)
	kubectl --context $(KIND_CTX) -n mob rollout restart deployment/mob-api
	kubectl --context $(KIND_CTX) -n mob rollout status deployment/mob-api --timeout=120s

## dev-kind-reset: destroy and recreate the full local environment
dev-kind-reset:
	./scripts/dev-setup.sh reset

## lint: run flake8 and mypy
lint:
	$(UV) run flake8 src/ tests/
	$(UV) run mypy src/

## format: run black formatter
format:
	$(UV) run black src/ tests/

## deploy-dev: deploy to dev environment (kind cluster)
deploy-dev:
	kubectl apply -k deploy/overlays/dev/

## deploy-staging: deploy to staging environment
deploy-staging:
	kubectl apply -k deploy/overlays/staging/

## deploy-production: deploy to production environment
deploy-production:
	kubectl apply -k deploy/overlays/production/

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

## clean: remove build artifacts and kind cluster
clean:
	rm -rf dist/ build/ *.egg-info .pytest_cache .mypy_cache htmlcov .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	-kind delete cluster --name $(KIND_CLUSTER)
	docker compose down -v 2>/dev/null || true
