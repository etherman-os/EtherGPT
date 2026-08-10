#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
SCOPE="user"
if [[ "${1:-}" == "--system" ]]; then
  SCOPE="system"
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required. Install it from https://docs.astral.sh/uv/getting-started/installation/" >&2
  exit 1
fi

cd "$ROOT_DIR"
uv sync --locked

if [[ "$SCOPE" == "system" ]]; then
  if [[ "$(id -u)" -ne 0 ]]; then
    echo "Run system installation with sudo: sudo ./install.sh --system" >&2
    exit 1
  fi
  ln -sfn "$ROOT_DIR/.venv/bin/ethergpt" /usr/local/bin/ethergpt
  echo "Installed /usr/local/bin/ethergpt"
else
  mkdir -p "$HOME/.local/bin"
  ln -sfn "$ROOT_DIR/.venv/bin/ethergpt" "$HOME/.local/bin/ethergpt"
  echo "Installed $HOME/.local/bin/ethergpt"
fi

if ! command -v tunnel-client >/dev/null 2>&1 && [[ "${ETHERGPT_SKIP_TUNNEL_INSTALL:-0}" != "1" ]]; then
  echo
  echo "Installing the verified official OpenAI tunnel-client…"
  "$ROOT_DIR/scripts/install-tunnel-client.sh"
fi

if [[ "$(uname -s)" == "Darwin" && "${ETHERGPT_SKIP_MENU:-0}" != "1" ]]; then
  echo
  if command -v swiftc >/dev/null 2>&1; then
    echo "Installing the EtherGPT menu-bar status app…"
    "$ROOT_DIR/scripts/install-macos-menu.sh"
  else
    echo "Skipping the menu-bar app because swiftc/Xcode Command Line Tools is unavailable."
  fi
fi

echo
echo "Next:"
echo "  ethergpt init --tunnel-id tunnel_... --ask-key --i-understand-full-access"
echo "  ethergpt doctor"
echo "  ethergpt"
