.PHONY: setup build test run lint format deploy clean \
       dev-up dev-down dev-logs \
       deploy-dev deploy-staging deploy-production \
       infra-init-aws infra-init-gcp \
       infra-plan-aws infra-plan-gcp \
       infra-apply-aws infra-apply-gcp

PYTHON := python3
UV := uv
APP_IMAGE := mob-api
APP_TAG := latest
KIND_CLUSTER := mob-local
ENV ?= dev

## setup: install dependencies and dev tools
setup:
	$(UV) sync --frozen

## build: build the Docker image
build:
	docker build -t $(APP_IMAGE):$(APP_TAG) .

## test: run the test suite
test:
	$(UV) run pytest tests/ -v

## dev-up: start local development environment with docker-compose
dev-up:
	docker compose up -d --build

## dev-down: stop local development environment
dev-down:
	docker compose down

## dev-logs: tail logs from local development environment
dev-logs:
	docker compose logs -f

## run: launch the application locally with kind cluster
run: build
	@echo "--- Ensuring kind cluster '$(KIND_CLUSTER)' exists ---"
	kind get clusters | grep -q $(KIND_CLUSTER) || kind create cluster --name $(KIND_CLUSTER)
	kind load docker-image $(APP_IMAGE):$(APP_TAG) --name $(KIND_CLUSTER)
	kubectl --context kind-$(KIND_CLUSTER) apply -k deploy/overlays/dev/
	@echo "--- Waiting for deployment rollout ---"
	kubectl --context kind-$(KIND_CLUSTER) -n mob rollout status deployment/mob-api --timeout=120s
	@echo "--- Application running. Port-forward with: kubectl --context kind-$(KIND_CLUSTER) -n mob port-forward svc/mob-api 8080:8080 ---"

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
