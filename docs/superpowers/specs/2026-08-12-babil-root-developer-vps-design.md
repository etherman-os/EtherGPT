# Babil Root Developer VPS Design

## Goal

Configure the existing Babil EtherGPT installation as a persistent, root-level
development machine that ChatGPT can use to clone repositories, edit code, run
tests, start services, access the internet, and invoke GitHub through a child MCP.

## Existing state

- EtherGPT runs as the `root` systemd user.
- The gateway listens only on `127.0.0.1:8766`.
- ChatGPT reaches it through the outbound OpenAI Secure MCP Tunnel.
- EtherGPT is intentionally configured in `full` access mode.
- No child MCP is currently registered on Babil.

## Chosen design

Keep EtherGPT running as `root`. Create these root-only locations:

- `/root/.config/ethergpt/secrets/` for MCP credentials.
- `/root/ethergpt-workspace/` for cloned repositories and test worktrees.
- `/root/.config/ethergpt/secrets/github.env` for the GitHub credential.

Directories use mode `0700`; secret files use mode `0600`. The systemd service
loads the secret environment file. EtherGPT's MCP registry refers to the token as
`{env:GITHUB_PERSONAL_ACCESS_TOKEN}` instead of storing the token in
`config.json`.

The GitHub MCP is installed from GitHub's official MCP server distribution and
registered as a local STDIO child MCP. Its package/image version is pinned rather
than tracking an unbounded latest version. The registry may be prepared before a
token exists, but it remains disabled until a real token is installed.

## Capabilities

The existing EtherGPT host tools provide root terminal, filesystem, process, and
network access. Repositories are cloned under `/root/ethergpt-workspace`. Project
commands run with normal outbound internet access and may bind local ports when
needed. Public exposure of a test service is not automatic; it requires an
explicit firewall, reverse-proxy, or tunnel decision.

The GitHub child MCP provides repository and issue/pull-request operations
allowed by the supplied GitHub credential. Ordinary `git clone`, test runners,
package managers, and web requests remain available through EtherGPT's host tools.

## Security boundary

Other unprivileged Linux accounts cannot traverse `/root` or read the secret
files. The server's root account, root processes, and ChatGPT operating through a
full-access root EtherGPT session can read them. No design can hide a credential
from an agent that has unrestricted root shell access on the same machine.

Use a fine-grained GitHub personal access token restricted to the necessary
repositories and permissions. A GitHub App with short-lived installation tokens
is a future hardening option, not part of this initial setup.

## Failure handling and rollback

Back up the current EtherGPT systemd unit and config before changes. Validate the
new unit with `systemd-analyze verify`, then reload and restart it. If startup
fails, restore the backups and restart the previous unit. Never print the GitHub
token in command output, logs, status endpoints, or documentation.

## Verification

- Confirm root-only modes and ownership with `stat`.
- Confirm EtherGPT remains active and bound only to loopback.
- Confirm the OpenAI tunnel process is healthy.
- Confirm root host tools can create and remove a harmless file in the workspace.
- Confirm outbound HTTPS works.
- After a token is supplied, enable and probe the GitHub MCP and perform a
  read-only repository query before allowing write operations.
