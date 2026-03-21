.PHONY: setup build test run lint format deploy clean

PYTHON := python3
UV := uv
APP_IMAGE := mob-api
APP_TAG := latest
KIND_CLUSTER := mob-local

## setup: install dependencies and dev tools
setup:
	$(UV) sync --frozen

## build: build the Docker image
build:
	docker build -t $(APP_IMAGE):$(APP_TAG) .

## test: run the test suite
test:
	$(UV) run pytest tests/ -v

## run: launch the application locally with SQLite and kind
run: build
	@echo "--- Ensuring kind cluster '$(KIND_CLUSTER)' exists ---"
	kind get clusters | grep -q $(KIND_CLUSTER) || kind create cluster --name $(KIND_CLUSTER)
	kind load docker-image $(APP_IMAGE):$(APP_TAG) --name $(KIND_CLUSTER)
	kubectl --context kind-$(KIND_CLUSTER) apply -f deploy/
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

## deploy: apply Kubernetes manifests to the current context
deploy:
	kubectl apply -f deploy/

## clean: remove build artifacts and kind cluster
clean:
	rm -rf dist/ build/ *.egg-info .pytest_cache .mypy_cache htmlcov .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	-kind delete cluster --name $(KIND_CLUSTER)
