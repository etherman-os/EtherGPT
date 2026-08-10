# EtherGPT complete setup guide

This guide takes a new user from an empty machine to one ChatGPT Web connection
that can use the host terminal, filesystem, long-running processes, and every
MCP registered in EtherGPT.

> **Security warning:** Full mode intentionally gives ChatGPT every permission
> of the operating-system account running EtherGPT. On a root VPS that means
> root. Use a dedicated machine/account, review confirmation prompts, install
> only trusted MCPs, and never paste runtime keys into chat or commit them.

## Contents

1. [Choose a deployment](#1-choose-a-deployment)
2. [Create an OpenAI Secure MCP Tunnel](#2-create-an-openai-secure-mcp-tunnel)
3. [Install EtherGPT](#3-install-ethergpt)
4. [Initialize and start](#4-initialize-and-start)
5. [Connect to ChatGPT Web](#5-connect-to-chatgpt-web)
6. [Add and manage MCP servers](#6-add-and-manage-mcp-servers)
7. [Use EtherGPT](#7-use-ethergpt)
8. [Health, logs, updates, and troubleshooting](#8-health-logs-updates-and-troubleshooting)

## 1. Choose a deployment

- **macOS user service:** best for Blender, Roblox Studio, Rojo, and other apps
  running in the logged-in Mac session.
- **Linux desktop user service:** runs with the logged-in Linux user's
  permissions. Control it through the CLI/local dashboard; there is no Linux
  tray app yet.
- **VPS user service:** safer default when ChatGPT only needs one deployment
  account and that account's files.
- **VPS root/system service:** deliberately gives ChatGPT root administration
  through `host_*`. Prefer a dedicated VPS and working backups.

Every simultaneously running machine needs its own tunnel.

## 2. Create an OpenAI Secure MCP Tunnel

EtherGPT needs no inbound firewall port, public domain, Nginx, Cloudflare
Tunnel, or ngrok. The official tunnel client connects outward to OpenAI over
HTTPS and forwards requests to EtherGPT on `127.0.0.1`.

### Permissions

- Create/edit a tunnel: Tunnels **Read + Manage**.
- Run `tunnel-client` and select a tunnel in ChatGPT: **Read + Use**.
- ChatGPT developer mode is a separate account/workspace permission.

For Enterprise/Edu, ask the workspace admin to allow developer mode and the
Platform organization administrator to grant tunnel permissions.

### Create the tunnel

1. Open [OpenAI Platform tunnel settings](https://platform.openai.com/settings/organization/tunnels).
2. Select the Platform organization that will own the tunnel.
3. Create a new tunnel.
4. Use a machine-specific name/description such as `My MacBook` or `Babil VPS`.
5. Associate the tunnel with the owning Platform organization and the ChatGPT
   workspace that should list it. Add any other Platform organization that will
   call it from Codex/API.
6. Copy the generated ID, for example
   `tunnel_0123456789abcdef0123456789abcdef`.
7. Create/copy the runtime API key offered by the setup flow and keep it secret.

The runtime key authenticates the local tunnel client. It is not the tunnel ID,
and an API key alone does not grant ChatGPT workspace or plugin access.

Official references:

- [Secure MCP Tunnel](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels)
- [Connect and test a ChatGPT plugin](https://developers.openai.com/plugins/deploy/connect-chatgpt)

## 3. Install EtherGPT

### macOS: one-command Homebrew setup

Install [Homebrew](https://brew.sh/) first if needed, then run:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/etherman-os/EtherGPT/main/scripts/brew-setup.sh)"
```

It installs `uv`, clones/updates EtherGPT under
`~/.local/share/ethergpt/source`, creates an isolated runtime, installs the
checksum-verified official tunnel client, installs `~/.local/bin/ethergpt`, the
menu-bar app, and `~/Applications/EtherGPT.app`.

If `ethergpt` is missing in a new terminal:

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zprofile
source ~/.zprofile
```

Source installation:

```bash
git clone https://github.com/etherman-os/EtherGPT.git
cd EtherGPT
./scripts/brew-setup.sh
```

### Linux desktop or non-root VPS

Install Git, curl, Python 3.11+, and `uv`. On Ubuntu/Debian:

```bash
sudo apt update
sudo apt install -y git curl ca-certificates python3
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
```

Install as the current user:

```bash
git clone https://github.com/etherman-os/EtherGPT.git
cd EtherGPT
./install.sh
```

`ethergpt` installs a systemd user unit on first start. For a headless user
service that must run after SSH logout, an administrator may enable lingering:

```bash
sudo loginctl enable-linger "$USER"
```

### Root VPS/system installation

Become root. On Ubuntu/Debian:

```bash
sudo -i
apt update
apt install -y git curl ca-certificates python3
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="/root/.local/bin:$PATH"
```

Install in a stable path; the service references this environment:

```bash
git clone https://github.com/etherman-os/EtherGPT.git /opt/ethergpt-source
cd /opt/ethergpt-source
./install.sh --system
```

The command is installed at `/usr/local/bin/ethergpt`. Stay in the root shell
for initialization so configuration and credentials belong to root.

## 4. Initialize and start

Full access (intentional whole-account control):

```bash
ethergpt init \
  --name "My MacBook" \
  --tunnel-id 'tunnel_0123456789abcdef0123456789abcdef' \
  --ask-key \
  --i-understand-full-access
```

`--ask-key` keeps the runtime key out of shell history. For restricted access:

```bash
ethergpt init \
  --tunnel-id 'tunnel_0123456789abcdef0123456789abcdef' \
  --ask-key \
  --scoped-root "$HOME/Projects" \
  --scoped-root "$HOME/Documents"
```

Validate and start persistently:

```bash
ethergpt doctor
ethergpt       # enable auto-start and start now
ethergpt status
```

Power commands are the same on macOS and Linux:

```bash
ethergpt on    # start now and stay enabled after login/boot
ethergpt off   # stop now and stay disabled after login/boot
ethergpt update # check and install origin/main, then refresh the service
```

On macOS, **Quit EtherGPT (Stop & Stay Off)** also removes the menu icon. Run
`ethergpt`, `ethergpt on`, or launch **EtherGPT.app** from Spotlight to restore
the gateway, tunnel, and menu.

## 5. Connect to ChatGPT Web

Secure MCP Tunnel is for private/developer-mode connections. It does not by
itself publish EtherGPT to the public plugin directory; each user connects a
tunnel allowed for their own workspace.

1. Confirm `ethergpt status` says `Gateway: ONLINE` and `Tunnel: ready`.
2. In ChatGPT open **Settings → Security and login**.
3. Enable **Developer mode** (availability depends on workspace policy).
4. Open [ChatGPT Plugins](https://chatgpt.com/plugins).
5. Select the plus button.
6. Enter a user-facing name and description.
7. Under **Connection**, choose **Tunnel**.
8. Select the tunnel or paste its complete `tunnel_id`.
9. Create the connection and review the discovered EtherGPT tools.
10. Start a new conversation and enable the connection from the tools menu.

If the tunnel is missing, verify that it includes the target ChatGPT workspace
and that the creator has Tunnels **Read + Use**.

After EtherGPT top-level tool names, schemas, annotations, auth, or resources
change: restart EtherGPT, open ChatGPT Plugins, select **Refresh**, confirm the
metadata, and start a new conversation. Dynamic child MCP additions do not need
Refresh because the stable dispatcher tools stay unchanged.

## 6. Add and manage MCP servers

### Dashboard

Open [http://127.0.0.1:8766/ui](http://127.0.0.1:8766/ui), run `ethergpt ui`, or
use **Open Dashboard** on macOS. The dashboard can add Streamable HTTP MCPs.
Each row has an **Enabled / Disabled** control and a separate health pill.

### Local STDIO MCP

Everything after `--` is the exact child process command:

```bash
ethergpt mcp add context7 -- npx -y @upstash/context7-mcp
ethergpt mcp add fetch -- uvx mcp-server-fetch
ethergpt mcp add local-tool --cwd "$HOME/Projects/example" -- /absolute/path/to/server --stdio
```

Environment example:

```bash
ethergpt mcp add rojo \
  --env ROJO_PROJECT_DIR="$HOME/Projects/game" \
  --env ROJO_BIN=/usr/local/bin/rojo \
  -- /absolute/path/to/rojo-mcp
```

For secrets, prefer `{env:NAME}` references and provide the real variable to
the service environment rather than storing it in a prompt or registry JSON.

### Remote Streamable HTTP MCP

```bash
ethergpt mcp add-url context7 https://mcp.context7.com/mcp
ethergpt mcp add-url private https://example.com/mcp \
  --header 'Authorization=Bearer {env:PRIVATE_MCP_TOKEN}'
```

### Inspect and control

```bash
ethergpt mcp list
ethergpt mcp probe all
ethergpt mcp tools blender
ethergpt mcp find screenshot
ethergpt mcp disable blender
ethergpt mcp enable blender
ethergpt mcp remove old-server
```

`dynamic` exposure is the default and works immediately through
`mcp_find_tools`/`mcp_call`. `direct` mounts every child tool as a top-level
namespaced tool but requires restart + ChatGPT Refresh when its metadata changes:

```bash
ethergpt mcp add-url context7 https://mcp.context7.com/mcp --expose direct
```

## 7. Use EtherGPT

Example ChatGPT prompts:

```text
Show EtherGPT gateway status and list every registered MCP.
```

```text
Create a project under ~/Projects/demo, run its tests, and show the result.
```

```text
Find Blender's viewport screenshot tool, call it, and describe the actual image.
```

```text
Add https://mcp.example.com/mcp as example, probe it, and list its tools.
```

```text
Disable Roblox and Blender MCPs but leave the host terminal available.
```

EtherGPT forwards native MCP image, audio, embedded-resource, and resource-link
blocks at the top level. Screenshots should be visible on the first successful
call instead of arriving only as base64 nested in JSON.

## 8. Health, logs, updates, and troubleshooting

### Health and logs

```text
Gateway: http://127.0.0.1:8766/healthz  /readyz  /ui
Tunnel:  http://127.0.0.1:8088/healthz  /readyz  /metrics  /ui
```

```bash
ethergpt doctor
ethergpt status
ethergpt mcp probe all
```

macOS logs: `~/Library/Logs/EtherGPT/`

```bash
# Linux user service
journalctl --user -u ethergpt.service -n 200 --no-pager

# Root VPS service
sudo journalctl -u ethergpt.service -n 200 --no-pager
```

### Update

On macOS choose **Check & Install Update…** from the menu bar, or on any
supported platform run:

```bash
ethergpt update
```

The updater checks `origin/main`, requires a clean Git checkout, fast-forwards
only, reruns the platform installer, refreshes the LaunchAgent/systemd unit, and
restarts the Linux service. If EtherGPT was installed from a wheel without a
source checkout, it clones the official repository into
`~/.local/share/ethergpt/source` or `/opt/ethergpt-source` for root Linux.

Manual alternatives:

macOS one-command install:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/etherman-os/EtherGPT/main/scripts/brew-setup.sh)"
ethergpt service restart
```

Source/Linux install:

```bash
cd /path/to/EtherGPT
git pull --ff-only
./install.sh                 # user
# or: ./install.sh --system  # already-root system install
ethergpt service restart
```

### ChatGPT says the tool was disabled

If status is ONLINE/ready, open ChatGPT Plugins, Refresh the connection, confirm
the tools, and start a new conversation with it enabled.

### Tunnel is absent in ChatGPT

Check the ChatGPT workspace association, Tunnels **Read + Use**, and ChatGPT
developer-mode permission.

### Screenshot is base64 but has no visible pixels

Update/restart EtherGPT, Refresh the ChatGPT connection, and use a new
conversation. The child must return MCP `ImageContent`; current EtherGPT
forwards it directly instead of nesting it in JSON.

Whole-desktop capture is a separate macOS permission boundary. Grant the
relevant terminal/MCP executable **System Settings → Privacy & Security → Screen
Recording**. Blender viewport screenshots normally do not need whole-desktop
Screen Recording permission.

### One child MCP is offline

```bash
ethergpt mcp enable blender
ethergpt mcp probe blender
ethergpt mcp tools blender
```

Ensure GUI apps and their MCP add-ons/listeners are running.

### Port conflict

EtherGPT uses loopback ports `8766` and `8088`. Stop the old instance or change
the configuration. Do not run one tunnel ID from two machines at once.

## Security checklist

- Associate tunnels only with required organizations/workspaces.
- Rotate any key pasted into chat, logs, screenshots, or shell history.
- Keep dashboard/health ports loopback-only unless separately protected.
- Review MCP source and pin serious dependencies.
- Prefer an unprivileged account when root is unnecessary.
- Maintain backups before granting full VPS control.
- Treat third-party MCP descriptions/outputs as prompt-injection input.

EtherGPT is independent software and is not affiliated with or endorsed by
OpenAI.
