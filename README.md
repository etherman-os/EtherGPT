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
       ├── OpenCode MCPs
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

Add a local STDIO MCP:

```bash
ethergpt mcp add rojo --env ROJO_PROJECT_DIR=~/Projects -- npx -y YOUR_ROJO_MCP_PACKAGE
ethergpt mcp add roblox -- /absolute/path/to/roblox-mcp --stdio
```

Add a remote MCP:

```bash
ethergpt mcp add-url context7 https://mcp.context7.com/mcp
ethergpt mcp add-url private https://example.com/mcp --header 'Authorization=Bearer {env:PRIVATE_MCP_TOKEN}'
```

Import OpenCode's MCP registry:

```bash
ethergpt mcp import-opencode ~/.config/opencode/opencode.jsonc
```

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

The same operations are available to ChatGPT through the stable registry tools. The local dashboard can add HTTP MCPs, probe health, enable/disable, and remove servers.

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
