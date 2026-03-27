#!/usr/bin/env bash
#
# lib.sh — Shared functions for mob setup scripts
#

KIND_CLUSTER="mob-local"
KIND_CONFIG="kind-config.yaml"
KIND_NODE="${KIND_CLUSTER}-control-plane"
NAMESPACE="mob"
KUBE_CTX="kind-${KIND_CLUSTER}"
MODE_FILE="/tmp/.mob-env-mode"

log()  { echo "==> $*"; }
info() { echo "    $*"; }

check_prerequisites() {
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
}

cluster_exists() {
  kind get clusters 2>/dev/null | grep -q "^${KIND_CLUSTER}$"
}

create_kind_cluster() {
  if cluster_exists; then
    log "Kind cluster '${KIND_CLUSTER}' already exists, reusing it."
  else
    log "Creating Kind cluster '${KIND_CLUSTER}'..."
    kind create cluster --config "${KIND_CONFIG}"
    log "Cluster created."
  fi
}

delete_kind_cluster() {
  log "Tearing down Kind cluster..."
  kind delete cluster --name "${KIND_CLUSTER}" 2>/dev/null || true
}

build_and_load_image() {
  local image="$1"
  local tag="$2"
  local dockerfile="$3"
  local context="$4"

  log "Building Docker image '${image}:${tag}'..."
  docker build -t "${image}:${tag}" -f "${dockerfile}" "${context}"

  log "Loading '${image}:${tag}' into Kind cluster..."
  kind load docker-image "${image}:${tag}" --name "${KIND_CLUSTER}"
}

check_mode_conflict() {
  local desired="$1"
  if [ -f "${MODE_FILE}" ]; then
    local current
    current=$(cat "${MODE_FILE}")
    if [ "${current}" != "${desired}" ]; then
      echo "ERROR: '${current}' environment is currently active." >&2
      echo "Run 'make ${current}-down' first, then retry." >&2
      exit 1
    fi
  fi
}

set_active_mode() {
  echo "$1" > "${MODE_FILE}"
}

clear_active_mode() {
  rm -f "${MODE_FILE}"
}
