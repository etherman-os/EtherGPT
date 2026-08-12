# Babil Root Developer VPS Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the existing Babil EtherGPT service into a persistent root-level development VPS with a protected workspace, outbound development access, and a prepared official GitHub MCP.

**Architecture:** Preserve the loopback-only EtherGPT gateway and outbound OpenAI tunnel. Keep execution under root, store credentials only in root-readable files, and run GitHub's official MCP server as a pinned ephemeral Docker STDIO child. Leave GitHub disabled until a real fine-grained PAT is installed.

**Tech Stack:** Ubuntu 24.04, systemd, EtherGPT 0.1.4, Docker 29.1.3, Git, GitHub MCP Server `v1.9.0`, OpenAI Secure MCP Tunnel

## Global Constraints

- EtherGPT remains `User=root` and `Group=root`.
- The gateway remains bound to `127.0.0.1:8766`; no public inbound port is added.
- `/root/.config/ethergpt/secrets` and `/root/ethergpt-workspace` use mode `0700`.
- Secret files use mode `0600` and must never be printed to output or stored directly in `config.json`.
- The GitHub MCP token reference is `file:/root/.config/ethergpt/secrets/github.token`.
- GitHub MCP stays disabled until the token is installed and verified.
- The Docker image is pinned to `ghcr.io/github/github-mcp-server:v1.9.0`.

---

### Task 1: Back up and verify the existing root gateway

**Files:**
- Read: `/etc/systemd/system/ethergpt.service`
- Read: `/root/.config/ethergpt/config.json`
- Create: `/root/.config/ethergpt/backups/<timestamp>/ethergpt.service`
- Create: `/root/.config/ethergpt/backups/<timestamp>/config.json`

**Interfaces:**
- Consumes: Existing root EtherGPT MCP endpoint at `http://127.0.0.1:8766/mcp`.
- Produces: A rollback copy and verified root command channel.

- [ ] **Step 1: Call `host_info` through the local MCP endpoint**

Expected fields: `uid: 0`, `gid: 0`, `access_mode: full`.

- [ ] **Step 2: Create a timestamped backup directory with mode 0700**

Run through root `host_exec`:

```bash
install -d -m 0700 /root/.config/ethergpt/backups/2026-08-12-root-vps
cp -a /etc/systemd/system/ethergpt.service /root/.config/ethergpt/backups/2026-08-12-root-vps/ethergpt.service
cp -a /root/.config/ethergpt/config.json /root/.config/ethergpt/backups/2026-08-12-root-vps/config.json
```

- [ ] **Step 3: Verify backup ownership and hashes**

Run:

```bash
stat -c '%a %U:%G %n' /root/.config/ethergpt/backups/2026-08-12-root-vps
sha256sum /etc/systemd/system/ethergpt.service /root/.config/ethergpt/backups/2026-08-12-root-vps/ethergpt.service
sha256sum /root/.config/ethergpt/config.json /root/.config/ethergpt/backups/2026-08-12-root-vps/config.json
```

Expected: directory `700 root:root`; each original/backup pair has identical hashes.

### Task 2: Create the private development and secret storage layout

**Files:**
- Create: `/root/ethergpt-workspace/`
- Create: `/root/.config/ethergpt/secrets/`
- Create: `/root/.config/ethergpt/secrets/github.token`
- Create: `/root/ethergpt-workspace/README.txt`

**Interfaces:**
- Consumes: Root filesystem access from Task 1.
- Produces: `file:/root/.config/ethergpt/secrets/github.token` and a stable project root.

- [ ] **Step 1: Create root-only directories**

Run:

```bash
install -d -o root -g root -m 0700 /root/ethergpt-workspace
install -d -o root -g root -m 0700 /root/.config/ethergpt/secrets
```

- [ ] **Step 2: Create an empty root-only token file**

Run:

```bash
install -o root -g root -m 0600 /dev/null /root/.config/ethergpt/secrets/github.token
```

- [ ] **Step 3: Document the workspace purpose without secrets**

Write `/root/ethergpt-workspace/README.txt` with:

```text
EtherGPT Babil development workspace.
Clone and test repositories below this directory.
Never store access tokens inside project repositories.
```

- [ ] **Step 4: Verify that unprivileged `chaos` cannot read the secret**

Run as root:

```bash
runuser -u chaos -- test ! -r /root/.config/ethergpt/secrets/github.token
stat -c '%a %U:%G %n' /root/ethergpt-workspace /root/.config/ethergpt/secrets /root/.config/ethergpt/secrets/github.token
```

Expected: access check exits 0; modes are `700`, `700`, and `600` with `root:root` ownership.

### Task 3: Install and register the official GitHub MCP safely

**Files:**
- Modify: `/root/.config/ethergpt/config.json`
- Docker image: `ghcr.io/github/github-mcp-server:v1.9.0`

**Interfaces:**
- Consumes: Token file path from Task 2 and existing EtherGPT CLI.
- Produces: Disabled dynamic child MCP named `github`.

- [ ] **Step 1: Pull the pinned official image**

Run:

```bash
docker pull ghcr.io/github/github-mcp-server:v1.9.0
```

Expected: exit 0 and a local image tagged `v1.9.0`.

- [ ] **Step 2: Register the Docker STDIO MCP**

Run:

```bash
/opt/ethergpt-source/.venv/bin/ethergpt --config /root/.config/ethergpt/config.json mcp add github --env GITHUB_PERSONAL_ACCESS_TOKEN=file:/root/.config/ethergpt/secrets/github.token --env GITHUB_TOOLSETS=all -- docker run -i --rm -e GITHUB_PERSONAL_ACCESS_TOKEN -e GITHUB_TOOLSETS ghcr.io/github/github-mcp-server:v1.9.0
/opt/ethergpt-source/.venv/bin/ethergpt --config /root/.config/ethergpt/config.json mcp disable github
```

Expected: the registry contains `github`, type `stdio`, exposure `dynamic`, enabled `false`; `config.json` contains only the `file:` reference, not a token.

- [ ] **Step 3: Confirm the image entrypoint responds without exposing a token**

Run:

```bash
docker image inspect ghcr.io/github/github-mcp-server:v1.9.0 --format '{{json .Config.Entrypoint}} {{json .Config.Cmd}}'
```

Expected: inspect succeeds. Do not start an authenticated session until the token file is populated.

### Task 4: Verify GPT development-host capabilities

**Files:**
- Use: `/root/ethergpt-workspace/`

**Interfaces:**
- Consumes: Root host tools and workspace from Tasks 1-2.
- Produces: Evidence that filesystem, Git, process execution, DNS, and HTTPS work.

- [ ] **Step 1: Verify root identity and workspace write access**

Run through `host_exec`:

```bash
id
touch /root/ethergpt-workspace/.ethergpt-write-test
test -f /root/ethergpt-workspace/.ethergpt-write-test
rm /root/ethergpt-workspace/.ethergpt-write-test
```

Expected: `uid=0(root)` and exit 0.

- [ ] **Step 2: Verify outbound HTTPS and Git access**

Run:

```bash
curl -fsS --max-time 20 https://api.github.com/rate_limit >/dev/null
git ls-remote https://github.com/github/github-mcp-server.git HEAD
```

Expected: both exit 0 and Git returns one `HEAD` hash.

- [ ] **Step 3: Verify the service and tunnel remain private and healthy**

Run:

```bash
systemctl is-active ethergpt.service
ss -ltn | grep '127.0.0.1:8766'
curl -fsS http://127.0.0.1:8766/api/status
```

Expected: service is active, gateway is loopback-only, status reports full mode and the disabled GitHub registry entry.

### Task 5: Token activation handoff

**Files:**
- Modify later: `/root/.config/ethergpt/secrets/github.token`
- Modify later: `/root/.config/ethergpt/config.json`

**Interfaces:**
- Consumes: A fine-grained PAT supplied outside logs and repository files.
- Produces: Enabled and probed GitHub MCP.

- [ ] **Step 1: Install the token without echoing it**

In an interactive root shell, use a hidden prompt that writes directly to the root-only file. Do not pass the token as a command-line argument.

- [ ] **Step 2: Enable and probe GitHub**

Run:

```bash
/opt/ethergpt-source/.venv/bin/ethergpt --config /root/.config/ethergpt/config.json mcp enable github
/opt/ethergpt-source/.venv/bin/ethergpt --config /root/.config/ethergpt/config.json mcp probe github
```

Expected: probe succeeds and reports tools from the official GitHub MCP.

- [ ] **Step 3: Perform a read-only identity/repository query first**

Use EtherGPT `mcp_tools` and `mcp_call` to identify the authenticated GitHub user and list accessible repositories. Only after this succeeds should write-capable GitHub tools be used.
