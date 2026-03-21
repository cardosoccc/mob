#!/usr/bin/env bash
#
# dev-setup.sh — Bootstrap a local Kind + PostgreSQL development environment
#
# Usage:
#   ./scripts/dev-setup.sh          # Full setup (create cluster, build, deploy)
#   ./scripts/dev-setup.sh teardown # Destroy the local cluster
#   ./scripts/dev-setup.sh status   # Show status of all pods
#   ./scripts/dev-setup.sh reset    # Teardown + full setup
#
set -euo pipefail

KIND_CLUSTER="mob-local"
KIND_CONFIG="kind-config.yaml"
APP_IMAGE="mob-api"
APP_TAG="latest"
NAMESPACE="mob"
KUBE_CTX="kind-${KIND_CLUSTER}"

log()  { echo "==> $*"; }
info() { echo "    $*"; }

cluster_exists() {
  kind get clusters 2>/dev/null | grep -q "^${KIND_CLUSTER}$"
}

cmd_teardown() {
  log "Tearing down Kind cluster '${KIND_CLUSTER}'..."
  kind delete cluster --name "${KIND_CLUSTER}" 2>/dev/null || true
  log "Cluster deleted."
}

cmd_status() {
  if ! cluster_exists; then
    log "Cluster '${KIND_CLUSTER}' does not exist."
    exit 1
  fi
  log "Cluster: ${KIND_CLUSTER}"
  kubectl --context "${KUBE_CTX}" -n "${NAMESPACE}" get pods -o wide 2>/dev/null || info "Namespace '${NAMESPACE}' not found yet."
  echo
  log "Services:"
  kubectl --context "${KUBE_CTX}" -n "${NAMESPACE}" get svc 2>/dev/null || true
}

cmd_setup() {
  # --- Prerequisites check ---
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

  # --- Create Kind cluster ---
  if cluster_exists; then
    log "Kind cluster '${KIND_CLUSTER}' already exists, reusing it."
  else
    log "Creating Kind cluster '${KIND_CLUSTER}'..."
    kind create cluster --config "${KIND_CONFIG}"
    log "Cluster created."
  fi

  # --- Build and load Docker image ---
  log "Building Docker image '${APP_IMAGE}:${APP_TAG}'..."
  docker build -t "${APP_IMAGE}:${APP_TAG}" .

  log "Loading image into Kind cluster..."
  kind load docker-image "${APP_IMAGE}:${APP_TAG}" --name "${KIND_CLUSTER}"

  # --- Deploy with kustomize ---
  log "Applying dev overlay (API + PostgreSQL)..."
  kubectl --context "${KUBE_CTX}" apply -k deploy/overlays/dev/

  # --- Wait for PostgreSQL ---
  log "Waiting for PostgreSQL to be ready..."
  kubectl --context "${KUBE_CTX}" -n "${NAMESPACE}" rollout status statefulset/postgres --timeout=120s

  # --- Wait for API ---
  log "Waiting for API deployment to be ready..."
  kubectl --context "${KUBE_CTX}" -n "${NAMESPACE}" rollout status deployment/mob-api --timeout=180s

  # --- Print summary ---
  echo
  log "Local dev environment is ready!"
  echo
  info "API:        http://localhost:8080"
  info "Health:     http://localhost:8080/health"
  info "PostgreSQL: localhost:5432 (user: mob_admin, password: dev-changeme, db: mob)"
  info "Kubectl:    kubectl --context ${KUBE_CTX} -n ${NAMESPACE} ..."
  echo
  info "Useful commands:"
  info "  make dev-kind-status   — Show pod/service status"
  info "  make dev-kind-logs     — Tail API logs"
  info "  make dev-kind-psql     — Open psql shell"
  info "  make dev-kind-rebuild  — Rebuild and redeploy the API"
  info "  make dev-kind-down     — Tear down the cluster"
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
