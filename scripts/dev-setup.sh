#!/usr/bin/env bash
#
# dev-setup.sh — Bootstrap a local Kind + PostgreSQL development environment
#
# PostgreSQL runs via Docker Compose (docker-compose.dev.yaml).
# The API runs in a local Kind cluster.
# Both share the 'mob-dev' Docker network so pods can reach Postgres.
#
# Usage:
#   ./scripts/dev-setup.sh          # Full setup
#   ./scripts/dev-setup.sh teardown # Destroy everything
#   ./scripts/dev-setup.sh status   # Show status
#   ./scripts/dev-setup.sh reset    # Teardown + setup
#
set -euo pipefail

KIND_CLUSTER="mob-local"
KIND_CONFIG="kind-config.yaml"
KIND_NODE="${KIND_CLUSTER}-control-plane"
APP_IMAGE="mob-api"
APP_TAG="latest"
NAMESPACE="mob"
KUBE_CTX="kind-${KIND_CLUSTER}"
COMPOSE_FILE="docker-compose.yaml"
DOCKER_NETWORK="mob-dev"
POSTGRES_CONTAINER="mob-postgres"

log()  { echo "==> $*"; }
info() { echo "    $*"; }

cluster_exists() {
  kind get clusters 2>/dev/null | grep -q "^${KIND_CLUSTER}$"
}

get_postgres_ip() {
  docker inspect -f "{{(index .NetworkSettings.Networks \"${DOCKER_NETWORK}\").IPAddress}}" "${POSTGRES_CONTAINER}" 2>/dev/null
}

cmd_teardown() {
  log "Tearing down Kind cluster..."
  kind delete cluster --name "${KIND_CLUSTER}" 2>/dev/null || true

  log "Stopping Docker Compose PostgreSQL..."
  docker compose -f "${COMPOSE_FILE}" down -v 2>/dev/null || true

  log "Teardown complete."
}

cmd_status() {
  log "Docker Compose (PostgreSQL):"
  docker compose -f "${COMPOSE_FILE}" ps 2>/dev/null || info "Not running."
  echo

  if ! cluster_exists; then
    log "Kind cluster '${KIND_CLUSTER}' does not exist."
    return
  fi

  log "Kind cluster: ${KIND_CLUSTER}"
  kubectl --context "${KUBE_CTX}" -n "${NAMESPACE}" get pods -o wide 2>/dev/null || info "Namespace '${NAMESPACE}' not found yet."
  echo
  log "Services:"
  kubectl --context "${KUBE_CTX}" -n "${NAMESPACE}" get svc 2>/dev/null || true
}

cmd_setup() {
  # --- Prerequisites ---
  for cmd in docker kind kubectl; do
    if ! command -v "$cmd" &>/dev/null; then
      echo "ERROR: '${cmd}' is required but not found in PATH." >&2
      exit 1
    fi
  done

  if ! docker info &>/dev/null; then
    echo "ERROR: Docker daemon is not running." >&2
    exit 1
  fi

  # --- Start PostgreSQL via Docker Compose ---
  log "Starting PostgreSQL via Docker Compose..."
  docker compose -f "${COMPOSE_FILE}" up -d

  log "Waiting for PostgreSQL to be healthy..."
  until docker inspect --format='{{.State.Health.Status}}' "${POSTGRES_CONTAINER}" 2>/dev/null | grep -q "healthy"; do
    sleep 2
  done
  log "PostgreSQL is healthy."

  # --- Create Kind cluster ---
  if cluster_exists; then
    log "Kind cluster '${KIND_CLUSTER}' already exists, reusing it."
  else
    log "Creating Kind cluster '${KIND_CLUSTER}'..."
    kind create cluster --config "${KIND_CONFIG}"
    log "Cluster created."
  fi

  # --- Connect Kind node to the Compose network ---
  if docker inspect "${KIND_NODE}" --format='{{json .NetworkSettings.Networks}}' | grep -q "${DOCKER_NETWORK}"; then
    log "Kind node already connected to '${DOCKER_NETWORK}' network."
  else
    log "Connecting Kind node to '${DOCKER_NETWORK}' Docker network..."
    docker network connect "${DOCKER_NETWORK}" "${KIND_NODE}"
  fi

  # --- Get Postgres container IP on the shared network ---
  POSTGRES_IP=$(get_postgres_ip)
  if [ -z "${POSTGRES_IP}" ]; then
    echo "ERROR: Could not determine PostgreSQL container IP on '${DOCKER_NETWORK}' network." >&2
    exit 1
  fi
  log "PostgreSQL reachable at ${POSTGRES_IP} on '${DOCKER_NETWORK}' network."

  # --- Patch the Endpoints manifest with the real Postgres IP ---
  sed "s/127\.0\.0\.1/${POSTGRES_IP}/g" deploy/overlays/dev/postgres.yaml > /tmp/mob-postgres-endpoints.yaml

  # --- Build and load Docker image ---
  log "Building Docker image '${APP_IMAGE}:${APP_TAG}'..."
  docker build -t "${APP_IMAGE}:${APP_TAG}" .

  log "Loading image into Kind cluster..."
  kind load docker-image "${APP_IMAGE}:${APP_TAG}" --name "${KIND_CLUSTER}"

  # --- Deploy with kustomize ---
  log "Deploying API to Kind cluster..."
  kubectl --context "${KUBE_CTX}" apply -k deploy/overlays/dev/

  # --- Apply the patched Endpoints with the real Postgres IP ---
  log "Configuring Kubernetes Endpoints to point to Docker Compose PostgreSQL..."
  kubectl --context "${KUBE_CTX}" apply -f /tmp/mob-postgres-endpoints.yaml
  rm -f /tmp/mob-postgres-endpoints.yaml

  # --- Wait for API ---
  log "Waiting for API deployment to be ready..."
  kubectl --context "${KUBE_CTX}" -n "${NAMESPACE}" rollout status deployment/mob-api --timeout=180s

  # --- Summary ---
  echo
  log "Local dev environment is ready!"
  echo
  info "API:        http://localhost:8080"
  info "Health:     http://localhost:8080/health"
  info "PostgreSQL: localhost:5432 (user: mob_admin, password: localdev, db: mob)"
  info "Kubectl:    kubectl --context ${KUBE_CTX} -n ${NAMESPACE} ..."
  echo
  info "Useful commands:"
  info "  make dev-kind-status   — Show pod/service status"
  info "  make dev-kind-logs     — Tail API logs"
  info "  make dev-kind-psql     — Open psql shell"
  info "  make dev-kind-rebuild  — Rebuild and redeploy the API"
  info "  make dev-kind-down     — Tear down everything"
}

case "${1:-setup}" in
  setup)    cmd_setup ;;
  teardown) cmd_teardown ;;
  status)   cmd_status ;;
  reset)    cmd_teardown; cmd_setup ;;
  *)
    echo "Usage: $0 {setup|teardown|status|reset}" >&2
    exit 1
    ;;
esac
