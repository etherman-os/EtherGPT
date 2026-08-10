# EtherGPT

One private ChatGPT Web plugin for an entire Mac or Linux/VPS: terminal, files, long-running processes, and every MCP server registered on that machine.

EtherGPT runs locally and connects outbound through the official [OpenAI Secure MCP Tunnel](https://github.com/openai/tunnel-client). ChatGPT gets one plugin and one tunnel. EtherGPT fans that connection out to local STDIO MCPs and remote Streamable HTTP MCPs.

> **Full access is real.** In full mode, ChatGPT can run arbitrary shell commands and read, overwrite, or delete anything the EtherGPT service account can access. EtherGPT requires an explicit acknowledgement before it will start in this mode.

## Why it exists

Normally every Roblox, Rojo, Blender, filesystem, browser, or custom MCP needs its own ChatGPT connection. Adding another MCP means adding another tunnel or rescanning plugin actions.

EtherGPT keeps a small permanent tool surface in ChatGPT:

- `host_*` — shell, files, search, exact editing, and background processes.
- `mcp_servers` / `mcp_find_tools` / `mcp_tools` — live MCP discovery.
- `mcp_call` — call any tool on any enabled MCP.
- `mcp_add_*`, `mcp_set_enabled`, `mcp_remove`, `mcp_probe` — manage the registry from ChatGPT.

New MCPs are immediately usable through `mcp_find_tools` and `mcp_call`; the ChatGPT plugin does not need a new tunnel or action scan. Frequently used MCPs may optionally be exposed as direct namespaced tools, which does require a gateway restart and ChatGPT action refresh.

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

## Install

```bash
git clone https://github.com/YOUR_NAME/EtherGPT.git
cd EtherGPT
./install.sh
```

The installer downloads the matching official `tunnel-client` release and verifies its published SHA-256 checksum when the binary is not already installed. On macOS it also installs the health menu-bar app. Set `ETHERGPT_SKIP_TUNNEL_INSTALL=1` or `ETHERGPT_SKIP_MENU=1` to manage either component yourself.

Make sure `~/.local/bin` is on `PATH`, then initialize full access:

```bash
ethergpt init \
  --tunnel-id 'tunnel_<32-lowercase-hex-characters>' \
  --ask-key \
  --i-understand-full-access
```

The runtime key is stored in macOS Keychain. On Linux it is stored in a mode-`0600` file under `~/.config/ethergpt/` unless `CONTROL_PLANE_API_KEY` is provided by the service environment.

Run it in the foreground first:

```bash
ethergpt doctor
ethergpt run
```

Then create or edit one ChatGPT Web plugin:

1. Enable ChatGPT developer mode.
2. Create a plugin using **Tunnel** connection mode.
3. Select the same tunnel ID.
4. Scan the tools and permit the write actions you want.
5. Start a new chat and enable the EtherGPT plugin.

## Background service

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

The menu labels the same actions **Auto-start ON** and **Auto-start OFF** so the persistent full-access state is explicit.

Linux/VPS user service:

```bash
ethergpt service install --scope user
```

Linux/VPS system service with root-level host permissions:

```bash
sudo ./install.sh --system
sudo ethergpt init --tunnel-id tunnel_... --ask-key --i-understand-full-access
sudo ethergpt service install --scope system
```

Only use the system/root mode on a VPS intentionally dedicated to this trust model.

## MCP management

### Add an MCP from the dashboard

Open `http://127.0.0.1:8766/ui` or choose **Open Dashboard** from the macOS menu-bar app. The form at the bottom adds a remote Streamable HTTP MCP. Enter a short unique name and its full `/mcp` URL. Each registry row has an **Enabled / Disabled** toggle; the separate status pill reports the most recent connection check.

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
