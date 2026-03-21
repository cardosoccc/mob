#!/usr/bin/env bash
set -euo pipefail

REPO="cardosoccc/mob"
INSTALL_DIR="${MOB_INSTALL_DIR:-$HOME/.local/bin}"
MIN_PYTHON="3.11"

info()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
error() { printf '\033[1;31merror:\033[0m %s\n' "$*" >&2; exit 1; }

# --- pre-flight checks ---

command -v python3 >/dev/null 2>&1 || error "python3 is required but not found"

python_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
if [ "$(printf '%s\n' "$MIN_PYTHON" "$python_version" | sort -V | head -n1)" != "$MIN_PYTHON" ]; then
    error "Python >= $MIN_PYTHON is required (found $python_version)"
fi

if command -v uv >/dev/null 2>&1; then
    installer="uv"
elif command -v pipx >/dev/null 2>&1; then
    installer="pipx"
elif command -v pip3 >/dev/null 2>&1; then
    installer="pip"
else
    error "One of uv, pipx, or pip3 is required but none were found"
fi

# --- install ---

info "Installing mob CLI via $installer ..."

case "$installer" in
    uv)
        uv tool install "mob @ git+https://github.com/${REPO}.git"
        ;;
    pipx)
        pipx install "git+https://github.com/${REPO}.git"
        ;;
    pip)
        pip3 install --user "git+https://github.com/${REPO}.git"
        ;;
esac

# --- verify ---

if command -v mob >/dev/null 2>&1; then
    info "mob $(mob --version 2>/dev/null || echo '') installed successfully!"
else
    info "mob was installed but is not on your PATH."
    info "Add the following to your shell profile:"
    echo ""
    case "$installer" in
        uv)   echo "  export PATH=\"\$HOME/.local/bin:\$PATH\"" ;;
        pipx) echo "  export PATH=\"\$HOME/.local/bin:\$PATH\"" ;;
        pip)  echo "  export PATH=\"$(python3 -m site --user-base)/bin:\$PATH\"" ;;
    esac
    echo ""
fi
