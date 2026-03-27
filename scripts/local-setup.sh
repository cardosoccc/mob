#!/usr/bin/env bash
#
# local-setup.sh — Bootstrap a Kind cluster with the operator for local mode
#
# Local mode: CLI -> service layer -> SQLite. Kind runs only the operator
# and agent pods for agent-run lifecycle management.
#
# Usage:
#   ./scripts/local-setup.sh          # Full setup
#   ./scripts/local-setup.sh teardown # Destroy everything
#   ./scripts/local-setup.sh status   # Show status
#   ./scripts/local-setup.sh reset    # Teardown + setup
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib.sh"

OPERATOR_IMAGE="mob-operator"
OPERATOR_TAG="latest"
AGENT_IMAGE="mob-agent-pydantic"
AGENT_TAG="latest"

cmd_setup() {
  check_prerequisites
  check_mode_conflict "local"

  # --- Create Kind cluster ---
  create_kind_cluster

  # --- Build and load only operator + agent images (no API image needed) ---
  build_and_load_image "${OPERATOR_IMAGE}" "${OPERATOR_TAG}" "./operator/Dockerfile" "./operator/"
  build_and_load_image "${AGENT_IMAGE}" "${AGENT_TAG}" "Dockerfile.agent" "."

  # --- Deploy operator stack only (API scaled to 0, no PostgreSQL) ---
  log "Deploying operator stack to Kind cluster..."
  kubectl --context "${KUBE_CTX}" apply -k deploy/overlays/local/

  # --- Wait for operator ---
  log "Waiting for operator deployment to be ready..."
  kubectl --context "${KUBE_CTX}" -n "${NAMESPACE}" rollout status deployment/mob-operator --timeout=120s

  set_active_mode "local"

  # --- Summary ---
  echo
  log "Local environment is ready!"
  echo
  info "Mode:       local (CLI -> SQLite)"
  info "Database:   ~/.mob/mob.db (SQLite)"
  info "Kind:       ${KIND_CLUSTER} (operator + agent pods)"
  info "Kubectl:    kubectl --context ${KUBE_CTX} -n ${NAMESPACE} ..."
  echo
  info "Useful commands:"
  info "  make local-status           — Show pod/service status"
  info "  make local-rebuild-operator — Rebuild and redeploy the operator"
  info "  make local-rebuild-agent    — Rebuild and reload the agent image"
  info "  make local-down             — Tear down the Kind cluster"
  echo
  info "Note: 'mob agent-run send' uses kubectl port-forward in local mode"
  info "      (pod IPs are not directly routable from host)."
}

cmd_teardown() {
  delete_kind_cluster
  clear_active_mode
  log "Local environment torn down."
}

cmd_status() {
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
