#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
credential_helper="$repo_root/scripts/ethergpt-github-credential"
auth_helper="$repo_root/scripts/ethergpt-github-auth"

test -x "$credential_helper"
test -x "$auth_helper"

test_root="$(mktemp -d)"
trap 'rm -rf "$test_root"' EXIT
token_file="$test_root/github.token"
cli_log="$test_root/cli.log"
fake_cli="$test_root/ethergpt"
config_file="$test_root/config.json"

printf '%s' 'test-token-value' >"$token_file"
chmod 0600 "$token_file"

credential_output="$({
  printf '%s\n' 'protocol=https' 'host=github.com' ''
} | ETHERGPT_GITHUB_TOKEN_FILE="$token_file" "$credential_helper" get)"
test "$credential_output" = $'username=x-access-token\npassword=test-token-value'

wrong_host_output="$({
  printf '%s\n' 'protocol=https' 'host=example.com' ''
} | ETHERGPT_GITHUB_TOKEN_FILE="$token_file" "$credential_helper" get)"
test -z "$wrong_host_output"

cat >"$fake_cli" <<'SCRIPT'
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$*" >>"$ETHERGPT_TEST_CLI_LOG"
if [[ "${ETHERGPT_TEST_PROBE_FAIL:-0}" == "1" && "$*" == *'mcp probe github' ]]; then
  exit 1
fi
SCRIPT
chmod 0700 "$fake_cli"

: >"$cli_log"
printf '%s\n' 'new-test-token' | \
  ETHERGPT_GITHUB_TOKEN_FILE="$token_file" \
  ETHERGPT_CLI="$fake_cli" \
  ETHERGPT_CONFIG="$config_file" \
  ETHERGPT_TEST_CLI_LOG="$cli_log" \
  "$auth_helper" >/dev/null

test "$(cat "$token_file")" = 'new-test-token'
test "$(stat -c '%a' "$token_file" 2>/dev/null || stat -f '%Lp' "$token_file")" = '600'
test "$(sed -n '1p' "$cli_log")" = "--config $config_file mcp enable github"
test "$(sed -n '2p' "$cli_log")" = "--config $config_file mcp probe github"

: >"$cli_log"
if printf '%s\n' 'token-with-failed-probe' | \
  ETHERGPT_GITHUB_TOKEN_FILE="$token_file" \
  ETHERGPT_CLI="$fake_cli" \
  ETHERGPT_CONFIG="$config_file" \
  ETHERGPT_TEST_CLI_LOG="$cli_log" \
  ETHERGPT_TEST_PROBE_FAIL=1 \
  "$auth_helper" >/dev/null 2>&1; then
  echo 'auth helper unexpectedly accepted a failed MCP probe' >&2
  exit 1
fi
test "$(tail -n 1 "$cli_log")" = "--config $config_file mcp disable github"

ETHERGPT_GITHUB_TOKEN_FILE="$token_file" \
  ETHERGPT_CLI="$fake_cli" \
  ETHERGPT_CONFIG="$config_file" \
  ETHERGPT_TEST_CLI_LOG="$cli_log" \
  "$auth_helper" --clear >/dev/null

test ! -s "$token_file"
test "$(tail -n 1 "$cli_log")" = "--config $config_file mcp disable github"

printf '%s\n' 'github helper tests passed'
