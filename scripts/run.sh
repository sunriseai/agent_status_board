#!/usr/bin/env sh
set -eu

INSTALL_DIR="${AGENT_STATUS_BOARD_HOME:-$HOME/.agent-status-board}"
VENV_DIR="$INSTALL_DIR/.venv"
PYTHON_BIN="${PYTHON:-python3}"
PACKAGE_URL="${AGENT_STATUS_BOARD_PACKAGE:-https://github.com/sunriseai/agent_status_board/archive/refs/heads/main.zip}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "error: $PYTHON_BIN is required but was not found" >&2
  exit 1
fi

mkdir -p "$INSTALL_DIR"
"$PYTHON_BIN" -m venv "$VENV_DIR"

# shellcheck disable=SC1091
. "$VENV_DIR/bin/activate"

python -m pip install --upgrade pip
python -m pip install --upgrade "$PACKAGE_URL"

exec agent-status-board "$@"
