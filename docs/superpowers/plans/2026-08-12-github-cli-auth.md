# GitHub CLI Authentication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend EtherGPT's GitHub authentication helper so one protected token configures GitHub MCP, HTTPS Git credentials, and the GitHub CLI on macOS and Linux.

**Architecture:** Keep `github.token` as EtherGPT's protected input file and pass it to GitHub CLI only over standard input. Treat `gh` as optional, preserve the existing MCP rollback semantics, and make `--clear` remove local GitHub CLI authentication without revoking the PAT remotely.

**Tech Stack:** Bash, GitHub CLI, EtherGPT CLI, Docker-hosted GitHub MCP, shell integration tests.

## Global Constraints

- Never place the GitHub token in command arguments, logs, or shell history.
- Keep the token file mode `0600` and its parent directory mode `0700`.
- Preserve GitHub MCP and HTTPS Git credential-helper behavior.
- GitHub CLI absence must not make GitHub MCP setup fail.
- Operate the Babil tunnel, gateway, MCP registry, GitHub credentials, and developer workspace as root.
- Remove only legacy EtherGPT artifacts from the `chaos` account; do not touch the unrelated project that account hosts.

---

### Task 1: GitHub CLI setup and clear behavior

**Files:**
- Modify: `tests/test_github_helpers.sh`
- Modify: `scripts/ethergpt-github-auth`

**Interfaces:**
- Consumes: `ETHERGPT_GITHUB_TOKEN_FILE`, `ETHERGPT_CLI`, `ETHERGPT_CONFIG`, and optional `ETHERGPT_GH_CLI` executable override.
- Produces: setup that calls `gh auth login --hostname github.com --git-protocol https --with-token` via standard input and clear behavior that calls `gh auth logout --hostname github.com --user LOGIN` when an authenticated account exists.

- [ ] **Step 1: Write the failing integration test**

Add a fake GitHub CLI that records arguments and standard input separately. Assert setup receives `new-test-token` only on standard input, assert no token appears in the argument log, and assert clear logs out the fake authenticated user. Add a second setup invocation with a nonexistent `ETHERGPT_GH_CLI` and assert MCP setup still succeeds.

- [ ] **Step 2: Run the helper test to verify RED**

Run: `./tests/test_github_helpers.sh`

Expected: FAIL because `ethergpt-github-auth` never invokes the fake GitHub CLI.

- [ ] **Step 3: Implement the minimal helper behavior**

Resolve `gh` from `ETHERGPT_GH_CLI` when supplied, otherwise from `PATH`. After the MCP probe succeeds, pipe the protected token file into the exact non-interactive login command. During `--clear`, query the authenticated login with `gh api user --jq .login` and pass it to the exact hostname-and-user logout command. Skip both paths when no executable exists.

- [ ] **Step 4: Run focused and complete tests**

Run:

```bash
./tests/test_github_helpers.sh
UV_CACHE_DIR=/private/tmp/ethergpt-uv-cache uv run pytest
bash -n scripts/ethergpt-github-auth scripts/ethergpt-github-credential
git diff --check
```

Expected: helper tests pass, 29 Python tests pass, scripts parse, and diff check is clean.

- [ ] **Step 5: Update user documentation and commit**

Update `README.md` to state that the helper also configures `gh`, document the optional CLI behavior, and explain that `--clear` removes local CLI auth without revoking the PAT. Commit the script, tests, and README together.

---

### Task 2: Deploy and verify on macOS and Babil root

**Files:**
- Install: `scripts/ethergpt-github-auth` to `/Users/berkay/.local/bin/ethergpt-github-auth`
- Install: `scripts/ethergpt-github-auth` to `/usr/local/sbin/ethergpt-github-auth` on Babil
- Remove on Babil: legacy EtherGPT-only processes and paths under `/home/chaos`

**Interfaces:**
- Consumes: existing protected token files on each host and the tested helper from Task 1.
- Produces: successful `gh auth status`, authenticated `gh api user`, healthy GitHub MCP probe, healthy root tunnel, and no EtherGPT runtime/config/process owned by `chaos`.

- [ ] **Step 1: Install the tested helper on macOS**

Install it mode `0700`, invoke it interactively using the existing protected token as standard input without printing the token, and verify `gh auth status --hostname github.com`, `gh api user --jq .login`, and `ethergpt mcp probe github`.

- [ ] **Step 2: Install the tested helper on Babil root**

Copy it mode `0700`, invoke it inside a root login shell using the existing protected token as standard input without printing the token, and run the same CLI and MCP checks as root.

- [ ] **Step 3: Remove legacy chaos-owned EtherGPT artifacts**

Before deletion, re-resolve the exact chaos-owned process IDs whose command references `/tmp/babil_gateway_exec.py`, `/home/chaos/.local/share/ethergpt`, or `/home/chaos/.local/bin/ethergpt`. Terminate only those processes. Remove only these exact legacy paths if present:

```text
/home/chaos/.config/ethergpt
/home/chaos/.local/share/ethergpt
/home/chaos/.local/bin/ethergpt
/tmp/babil_gateway_exec.py
```

- [ ] **Step 4: Verify isolation and root service health**

Assert no chaos-owned process or exact legacy path contains EtherGPT, while `/opt/ethergpt-source`, `/root/.config/ethergpt`, and `ethergpt.service` remain. Verify ports `8766` and `8088` listen only on loopback, tunnel channel `main` reports `probe_status=ok`, GitHub MCP reports 85 tools, and the root GitHub CLI account is authenticated.

- [ ] **Step 5: Publish and synchronize**

Push `main`, confirm the remote head equals the local commit, update `/Users/berkay/EtherGPT` with a fast-forward pull, and run the focused helper test from the synchronized checkout.
