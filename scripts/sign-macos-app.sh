#!/usr/bin/env bash
set -euo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
  printf '%s\n' 'App bundle signing is only available on macOS.' >&2
  exit 1
fi

app="${1:-}"
if [[ -z "$app" || ! -d "$app/Contents" ]]; then
  printf '%s\n' 'Usage: sign-macos-app.sh /path/to/App.app' >&2
  exit 2
fi

codesign --force --deep --sign - "$app"
codesign --verify --deep --strict --verbose=2 "$app"
