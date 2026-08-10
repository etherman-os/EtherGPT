#!/bin/bash
set -euo pipefail

for dependency in curl unzip awk find install; do
  command -v "$dependency" >/dev/null 2>&1 || {
    echo "Required command is missing: $dependency" >&2
    exit 1
  }
done

case "$(uname -s)" in
  Darwin) PLATFORM="darwin" ;;
  Linux) PLATFORM="linux" ;;
  *) echo "Unsupported operating system: $(uname -s)" >&2; exit 1 ;;
esac

case "$(uname -m)" in
  arm64|aarch64) ARCH="arm64" ;;
  x86_64|amd64) ARCH="amd64" ;;
  *) echo "Unsupported architecture: $(uname -m)" >&2; exit 1 ;;
esac

ASSET="$PLATFORM-$ARCH.zip"
BASE="https://github.com/openai/tunnel-client/releases/latest/download"
TEMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TEMP_DIR"' EXIT

curl -fsSL "$BASE/$ASSET" -o "$TEMP_DIR/$ASSET"
curl -fsSL "$BASE/SHA256SUMS.txt" -o "$TEMP_DIR/SHA256SUMS.txt"

EXPECTED="$(awk -v asset="$ASSET" '$2 == asset || $2 == "*" asset {print $1; exit}' "$TEMP_DIR/SHA256SUMS.txt")"
if [[ -z "$EXPECTED" ]]; then
  echo "Could not find $ASSET in the official checksum manifest" >&2
  exit 1
fi
if command -v shasum >/dev/null 2>&1; then
  ACTUAL="$(shasum -a 256 "$TEMP_DIR/$ASSET" | awk '{print $1}')"
else
  ACTUAL="$(sha256sum "$TEMP_DIR/$ASSET" | awk '{print $1}')"
fi
if [[ "$ACTUAL" != "$EXPECTED" ]]; then
  echo "Checksum verification failed for $ASSET" >&2
  exit 1
fi

unzip -q "$TEMP_DIR/$ASSET" -d "$TEMP_DIR/unpacked"
BINARY="$(find "$TEMP_DIR/unpacked" -type f -name tunnel-client -print -quit)"
if [[ -z "$BINARY" ]]; then
  echo "The official archive did not contain tunnel-client" >&2
  exit 1
fi

if [[ "$(id -u)" -eq 0 ]]; then
  TARGET="/usr/local/bin/tunnel-client"
else
  mkdir -p "$HOME/.local/bin"
  TARGET="$HOME/.local/bin/tunnel-client"
fi
install -m 0755 "$BINARY" "$TARGET"
echo "Installed verified official tunnel-client: $TARGET"
