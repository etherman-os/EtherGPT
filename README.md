# EtherGPT

One private ChatGPT Web plugin for an entire Mac or Linux/VPS: terminal, files, long-running processes, and every MCP server registered on that machine.

EtherGPT runs locally and connects outbound through the official [OpenAI Secure MCP Tunnel](https://github.com/openai/tunnel-client). ChatGPT gets one plugin and one tunnel. EtherGPT fans that connection out to local STDIO MCPs and remote Streamable HTTP MCPs.

**New here? Follow the [complete setup guide](docs/SETUP.md)** for tunnel
creation, macOS/Homebrew, Linux desktop, root or non-root VPS installation,
ChatGPT connection, MCP registration, updates, health checks, and troubleshooting.

> **Full access is real.** In full mode, ChatGPT can run arbitrary shell commands and read, overwrite, or delete anything the EtherGPT service account can access. EtherGPT requires an explicit acknowledgement before it will start in this mode.

## Why it exists

Normally every Roblox, Rojo, Blender, filesystem, browser, or custom MCP needs its own ChatGPT connection. Adding another MCP means adding another tunnel or rescanning plugin actions.

EtherGPT keeps a small permanent tool surface in ChatGPT:

- `host_*` — shell, files, search, exact editing, and background processes.
- `mcp_servers` / `mcp_find_tools` / `mcp_tools` — live MCP discovery.
- `mcp_call` — call any tool on any enabled MCP.
- `mcp_add_*`, `mcp_set_enabled`, `mcp_remove`, `mcp_probe` — manage the registry from ChatGPT.

New MCPs are immediately usable through `mcp_find_tools` and `mcp_call`; the ChatGPT plugin does not need a new tunnel or action scan. Frequently used MCPs may optionally be exposed as direct namespaced tools, which does require a gateway restart and ChatGPT action refresh.

Child MCP image, audio, and resource blocks are forwarded as native top-level
MCP content. A Blender viewport screenshot therefore reaches ChatGPT as an
actual image instead of an opaque base64 string nested inside JSON.

## Architecture

```text
ChatGPT Web plugin
       │
       │ OpenAI Secure MCP Tunnel (outbound HTTPS)
       ▼
EtherGPT on your machine
       ├── full host tools (shell/files/processes)
       ├── Roblox MCP
       ├── Rojo MCP
       ├── Blender MCP
       ├── browser / GitHub / custom MCPs
       └── any STDIO or Streamable HTTP MCP
```

The gateway and dashboards bind to loopback by default. The machine does not need an inbound port, public domain, Nginx, Cloudflare Tunnel, or ngrok.

## Requirements

- macOS 13+ or a modern Linux distribution.
- Python 3.11+ and [`uv`](https://docs.astral.sh/uv/).
- An OpenAI tunnel ID and runtime API key.
- A ChatGPT workspace/account where your existing custom plugin can run the desired write actions.

## Create the OpenAI tunnel first

1. Open [OpenAI Platform → Tunnels](https://platform.openai.com/settings/organization/tunnels).
2. Create a tunnel named for the machine, such as `My MacBook` or `Production VPS`.
3. Associate it with the Platform organization and ChatGPT workspace that will
   use it.
4. Copy the `tunnel_id` and runtime API key from the setup flow. Keep the key secret.

Creating/editing tunnels requires Tunnels **Read + Manage**; running the client
or selecting the tunnel in ChatGPT requires **Read + Use**. See the official
[Secure MCP Tunnel guide](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels)
and the [complete EtherGPT setup guide](docs/SETUP.md#2-create-an-openai-secure-mcp-tunnel).

## Install

```bash
git clone https://github.com/etherman-os/EtherGPT.git
cd EtherGPT
./install.sh
```

The installer downloads the matching official `tunnel-client` release and verifies its published SHA-256 checksum when the binary is not already installed. On macOS it also installs the health menu-bar app. Set `ETHERGPT_SKIP_TUNNEL_INSTALL=1` or `ETHERGPT_SKIP_MENU=1` to manage either component yourself.

When installation runs in a terminal, the first-time wizard opens automatically.
If it was installed non-interactively, run:

```bash
ethergpt setup
```

The wizard asks for the machine name, `tunnel_id`, tunnel runtime API key, and
full or scoped host access. The runtime key is stored in macOS Keychain. On
Linux it is stored in a mode-`0600` file under `~/.config/ethergpt/` unless
`CONTROL_PLANE_API_KEY` is provided by the service environment. It is never
returned by the dashboard API. Scoped mode limits file tools to the selected
folders and disables arbitrary shell/background commands; full mode enables the
intentionally unrestricted development workflow.

Then start persistently:

```bash
ethergpt doctor
ethergpt
```

Bare `ethergpt` also launches the terminal wizard automatically when setup is
missing. A non-interactive/macOS app start keeps the local gateway alive without
opening the OpenAI tunnel and opens the setup dashboard instead. Saving setup
starts the tunnel automatically.

Then create or edit one ChatGPT Web plugin:

1. In ChatGPT open **Settings → Security and login** and enable **Developer mode**.
2. Open [ChatGPT Plugins](https://chatgpt.com/plugins) and select the plus button.
3. Enter a name/description, then choose **Connection → Tunnel**.
4. Select the same tunnel or paste its `tunnel_id`, create the connection, and
   review the discovered EtherGPT tools.
5. Start a new chat and enable the EtherGPT connection from the tools menu.

See [Connect EtherGPT to ChatGPT](docs/SETUP.md#5-connect-to-chatgpt-web) for
the complete flow and permission troubleshooting.

## Background service

The same persistent power commands work on macOS, Linux desktops, and Linux
VPS hosts:

```bash
ethergpt       # turn on now and automatically after login/boot
ethergpt off   # stop now and stay off
ethergpt on    # turn back on
ethergpt update # check origin/main and install an available update
```

On first use under Linux, bare `ethergpt` installs the appropriate systemd
unit automatically: a user unit for regular users or a system unit when run as
root. A headless VPS has no menu icon; use these commands and
`ethergpt status`.

Mac runs EtherGPT inside the logged-in GUI user session so native app MCPs such as Roblox or Blender can work:

```bash
ethergpt service install --scope user
./scripts/install-macos-menu.sh
```

After installation, control persistent startup from the menu bar or the CLI:

```bash
ethergpt service enable   # start now and at future logins
ethergpt service disable  # stop now and stay off at future logins
ethergpt service restart
```

On macOS, **Quit EtherGPT (Stop & Stay Off)** in the menu-bar app stops the
gateway and tunnel, disables both auto-start entries, and removes the menu icon.
To turn everything back on, launch **EtherGPT** from Spotlight/Finder or run:

```bash
ethergpt
```

The launcher re-enables auto-start and starts the gateway, tunnel, and menu icon.
If setup is incomplete, it opens the local setup page and the menu displays
**EtherGPT SETUP** with **Setup required — Open Dashboard…**.
Use **Check & Install Update…** in the macOS menu or run `ethergpt update` on
macOS/Linux. The updater refuses to overwrite a Git checkout with local changes.

### Easy macOS setup with Homebrew

One command installs `uv` through Homebrew, downloads EtherGPT, creates the
isolated runtime, installs the official OpenAI tunnel client, and adds both the
menu-bar app and Spotlight launcher:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/etherman-os/EtherGPT/main/scripts/brew-setup.sh)"
```

The script launches EtherGPT when installation finishes. If connection details
are missing, the setup dashboard opens automatically; terminal users can always
run `ethergpt setup`.

The same script can also be run as `./scripts/brew-setup.sh` from a cloned repo.
A signed Homebrew cask can be added after the first packaged macOS release.

The menu labels the same actions **Auto-start ON** and **Auto-start OFF** so the persistent full-access state is explicit.

Linux/VPS user service:

```bash
ethergpt service install --scope user
```

Linux/VPS system service with root-level host permissions:

```bash
sudo ./install.sh --system
sudo ethergpt setup
sudo ethergpt service install --scope system
```

Only use the system/root mode on a VPS intentionally dedicated to this trust model.

## MCP management

### Add an MCP from the dashboard

Open `http://127.0.0.1:8766/ui` or choose **Open Dashboard** from the macOS menu-bar app. The form at the bottom adds a remote Streamable HTTP MCP. Enter a short unique name and its full `/mcp` URL. Each registry row has an **Enabled / Disabled** toggle; the separate status pill reports the most recent connection check.

The dashboard's **Config & setup** section also lets you add or replace the
tunnel ID and runtime API key, rename the machine, or switch between full and
scoped host access. Leave an already configured credential field blank to keep
its current value. Saving restarts the local gateway/tunnel automatically.

For scripts and automation, the original non-interactive command remains
available:

```bash
ethergpt init --tunnel-id tunnel_... --ask-key --i-understand-full-access
```

STDIO MCPs launch local commands and therefore must be added from the CLI or through ChatGPT's `mcp_add_stdio` tool.

### Add a local STDIO MCP

Everything after `--` is the MCP process command:

```bash
ethergpt mcp add context7 -- npx -y @upstash/context7-mcp
ethergpt mcp add fetch -- uvx mcp-server-fetch
ethergpt mcp add local-tool --cwd ~/Projects -- /absolute/path/to/server --stdio
```

Pass environment values with repeatable `--env KEY=VALUE` options. Prefer `{env:NAME}` references for secrets so credentials are resolved from the EtherGPT service environment instead of being copied into prompts or dashboard responses:

```bash
ethergpt mcp add rojo \
  --env ROJO_PROJECT_DIR=/Users/me/Projects \
  --env ROJO_BIN=/opt/homebrew/bin/rojo \
  -- /absolute/path/to/rojo-mcp
```

### GitHub MCP and private clones on a root VPS

For an intentionally root-controlled development VPS, install the protected Git
helpers and the pinned official GitHub MCP image:

```bash
sudo install -d -o root -g root -m 0700 /root/ethergpt-workspace
sudo install -d -o root -g root -m 0700 /root/.config/ethergpt/secrets
sudo install -o root -g root -m 0600 /dev/null /root/.config/ethergpt/secrets/github.token
sudo install -o root -g root -m 0700 scripts/ethergpt-github-auth /usr/local/sbin/ethergpt-github-auth
sudo install -o root -g root -m 0700 scripts/ethergpt-github-credential /usr/local/sbin/ethergpt-github-credential
sudo docker pull ghcr.io/github/github-mcp-server:v1.9.0
sudo ethergpt mcp add github \
  --env GITHUB_PERSONAL_ACCESS_TOKEN=file:/root/.config/ethergpt/secrets/github.token \
  --env GITHUB_TOOLSETS=all \
  -- docker run -i --rm \
  -e GITHUB_PERSONAL_ACCESS_TOKEN -e GITHUB_TOOLSETS \
  ghcr.io/github/github-mcp-server:v1.9.0
sudo ethergpt mcp disable github
sudo git config --global credential.https://github.com.helper \
  '!/usr/local/sbin/ethergpt-github-credential'
```

Create a [fine-grained GitHub personal access token](https://github.com/settings/personal-access-tokens/new)
restricted to the required repositories and permissions. Enter it from an
interactive root shell so it never appears in a command argument or shell
history:

```bash
sudo -i                  # or: su - root
ethergpt-github-auth
```

The command writes the token with mode `0600`, enables and probes the GitHub MCP,
and leaves normal root `git clone`, `pull`, and `push` able to authenticate to
private `github.com` repositories. Run `ethergpt-github-auth --clear` to erase the
token and disable the MCP. `GITHUB_TOOLSETS=all` exposes all server toolsets, but
the token's repository selection and permissions remain the real authorization
boundary.

### Add a remote HTTP MCP

```bash
ethergpt mcp add-url context7 https://mcp.context7.com/mcp
ethergpt mcp add-url private https://example.com/mcp --header 'Authorization=Bearer {env:PRIVATE_MCP_TOKEN}'
```

### Add and manage MCPs from ChatGPT

The EtherGPT plugin exposes the same registry operations to ChatGPT. Example prompts:

```text
Add the Streamable HTTP MCP https://mcp.example.com/mcp as example.
Add a STDIO MCP named local-tool using: npx -y @example/mcp-server
Disable blender, then list all registered MCPs.
Find every tool related to screenshots and call the Blender viewport screenshot tool.
```

These use `mcp_add_http`, `mcp_add_stdio`, `mcp_set_enabled`, `mcp_find_tools`, and `mcp_call` behind the scenes. Dynamic MCPs are available immediately; no new tunnel or ChatGPT metadata refresh is required.

Native media returned by dynamic tools is preserved. For example:

```text
Find Blender's viewport screenshot tool, call it, and describe the image itself.
```

ChatGPT should receive the PNG directly on the first successful tool call; it
should not need to decode base64 into `/mnt/data` first.

Inspect and control it:

```bash
ethergpt mcp list
ethergpt mcp probe all
ethergpt mcp find blender
ethergpt mcp disable blender
ethergpt mcp enable blender
ethergpt status
ethergpt ui
```

The same operations are available to ChatGPT through the stable registry tools. `ethergpt mcp probe all` performs an explicit health check; enable/disable only controls whether EtherGPT is allowed to connect to that MCP.

## Scoped mode

For users who do not want whole-machine access:

```bash
ethergpt init --scoped-root ~/Projects --scoped-root ~/Documents
```

In scoped mode, EtherGPT rejects file paths and command working directories outside those roots. This is a path boundary, not a complete OS sandbox; a child command can still have the permissions of the service account.

## Direct versus dynamic MCP exposure

- `dynamic` (default): available immediately through `mcp_find_tools` and `mcp_call`; no ChatGPT refresh.
- `direct`: every child tool also appears as `server_tool` in ChatGPT. Faster to call, but changing the set requires restarting EtherGPT and refreshing ChatGPT plugin actions.

```bash
ethergpt mcp add-url context7 https://mcp.context7.com/mcp --expose direct
```

## Health

- Gateway: `http://127.0.0.1:8766/healthz`, `/readyz`, `/ui`
- Tunnel: `http://127.0.0.1:8088/healthz`, `/readyz`, `/metrics`, `/ui`

`ethergpt doctor` checks the configuration, tunnel ID, runtime key, tunnel binary, access acknowledgement, and registry.

## Troubleshooting ChatGPT connections

If ChatGPT reports that the EtherGPT tool or plugin "has been disabled" while `ethergpt status` still shows both **Gateway ONLINE** and **Tunnel ready**, the local tunnel is healthy and the conversation is holding stale or disabled plugin state. Open the connection at ChatGPT Plugins, select **Refresh**, confirm that the 20 EtherGPT tools are advertised, and start a new conversation with the plugin enabled.

If only one child MCP is unavailable, check its **Enabled / Disabled** toggle in the dashboard and run:

```bash
ethergpt mcp enable blender
ethergpt mcp probe blender
ethergpt mcp tools blender
```

Changing a dynamic child MCP does not require a ChatGPT refresh. Refresh is only required when EtherGPT's own top-level tool metadata or a directly exposed MCP changes.

If a screenshot call succeeds but ChatGPT only sees base64/JSON, update
EtherGPT, restart it, open the connection at ChatGPT Plugins, select
**Refresh**, and start a new conversation. Current EtherGPT forwards MCP
`ImageContent` at the top level. Whole-desktop screenshot MCPs may additionally
need macOS **Privacy & Security → Screen Recording** permission; Blender's own
viewport screenshot normally does not.

## Security model

- The OpenAI tunnel is outbound-only; EtherGPT does not publish the local MCP endpoint.
- Full access is disabled until explicitly acknowledged.
- Runtime tunnel credentials are not written to the registry JSON.
- MCP environment variables and HTTP headers are redacted from the dashboard status response.
- Child MCPs run with the same OS identity as EtherGPT. Only install MCPs you trust.
- Tool descriptions from a malicious MCP can influence the model. Review third-party MCP source and pin package versions for serious use.

## Development

```bash
uv sync --extra dev
uv run pytest
uv run ethergpt --help
```

MIT licensed. EtherGPT is independent software and is not affiliated with or endorsed by OpenAI.
