#!/bin/bash
set -euo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "Homebrew setup is intended for macOS. Use ./install.sh on Linux." >&2
  exit 1
fi

if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew is required: https://brew.sh" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd || true)"
if [[ -n "$SCRIPT_DIR" && -f "$SCRIPT_DIR/../install.sh" ]]; then
  ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
else
  ROOT_DIR="$HOME/.local/share/ethergpt/source"
  mkdir -p "$(dirname "$ROOT_DIR")"
  if [[ -d "$ROOT_DIR/.git" ]]; then
    git -C "$ROOT_DIR" pull --ff-only
  else
    git clone https://github.com/etherman-os/EtherGPT.git "$ROOT_DIR"
  fi
fi

if ! command -v uv >/dev/null 2>&1; then
  brew install uv
fi

"$ROOT_DIR/install.sh"

echo
echo "Mac install complete. Starting EtherGPT…"
"$HOME/.local/bin/ethergpt"
echo "If setup is incomplete, EtherGPT opens the local setup dashboard automatically."
