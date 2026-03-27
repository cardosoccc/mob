#!/usr/bin/env bash
#
# dev-setup.sh — Bootstrap a local Kind + PostgreSQL development environment
#
# PostgreSQL runs via Docker Compose (docker-compose.yaml).
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

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib.sh"

APP_IMAGE="mob-api"
APP_TAG="latest"
OPERATOR_IMAGE="mob-operator"
OPERATOR_TAG="latest"
AGENT_IMAGE="mob-agent-pydantic"
AGENT_TAG="latest"
COMPOSE_FILE="docker-compose.yaml"
DOCKER_NETWORK="mob-dev"
POSTGRES_CONTAINER="mob-postgres"

get_postgres_ip() {
  docker inspect -f "{{(index .NetworkSettings.Networks \"${DOCKER_NETWORK}\").IPAddress}}" "${POSTGRES_CONTAINER}" 2>/dev/null
}

cmd_teardown() {
  delete_kind_cluster

  log "Stopping Docker Compose PostgreSQL..."
  docker compose -f "${COMPOSE_FILE}" down -v 2>/dev/null || true

  clear_active_mode
  log "Dev environment torn down."
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
  check_prerequisites
  check_mode_conflict "dev"

  # --- Start PostgreSQL via Docker Compose ---
  log "Starting PostgreSQL via Docker Compose..."
  docker compose -f "${COMPOSE_FILE}" up -d

  log "Waiting for PostgreSQL to be healthy..."
  until docker inspect --format='{{.State.Health.Status}}' "${POSTGRES_CONTAINER}" 2>/dev/null | grep -q "healthy"; do
    sleep 2
  done
  log "PostgreSQL is healthy."

  # --- Create Kind cluster ---
  create_kind_cluster

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

  # --- Build and load Docker images ---
  build_and_load_image "${APP_IMAGE}" "${APP_TAG}" "Dockerfile" "."
  build_and_load_image "${OPERATOR_IMAGE}" "${OPERATOR_TAG}" "./operator/Dockerfile" "./operator/"
  build_and_load_image "${AGENT_IMAGE}" "${AGENT_TAG}" "Dockerfile.agent" "."

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

  set_active_mode "dev"

  # --- Summary ---
  echo
  log "Dev environment is ready!"
  echo
  info "API:        http://localhost:8080"
  info "Health:     http://localhost:8080/health"
  info "PostgreSQL: localhost:5432 (user: mob_admin, password: localdev, db: mob)"
  info "Kubectl:    kubectl --context ${KUBE_CTX} -n ${NAMESPACE} ..."
  echo
  info "Useful commands:"
  info "  make dev-status    — Show pod/service status"
  info "  make dev-logs      — Tail API logs"
  info "  make dev-psql      — Open psql shell"
  info "  make dev-rebuild   — Rebuild and redeploy the API"
  info "  make dev-down      — Tear down everything"
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
