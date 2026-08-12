#!/usr/bin/env bash
set -euo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
  printf '%s\n' 'macOS app tests skipped on non-Darwin host'
  exit 0
fi

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
test_root="$(mktemp -d)"
trap 'rm -rf "$test_root"' EXIT

cp "$repo_root/tests/fixtures/macos_launcher_logic_test.swift" "$test_root/main.swift"
swiftc \
  "$repo_root/macos/EtherGPTLaunchLogic.swift" \
  "$test_root/main.swift" \
  -o "$test_root/test-launch-logic"
"$test_root/test-launch-logic"

app="$test_root/EtherGPT.app"
mkdir -p "$app/Contents/MacOS" "$app/Contents/Resources"
cp "$repo_root/macos/Info.plist" "$app/Contents/Info.plist"
cp /bin/echo "$app/Contents/MacOS/EtherGPT"
printf '%s\n' 'signature fixture' >"$app/Contents/Resources/fixture.txt"

"$repo_root/scripts/sign-macos-app.sh" "$app"
codesign --verify --deep --strict --verbose=2 "$app"

printf '%s\n' 'macOS app bundle tests passed'
