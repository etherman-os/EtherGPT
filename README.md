# Open-gpt

One private ChatGPT Web plugin for an entire Mac or Linux/VPS: terminal, files, long-running processes, and every MCP server registered on that machine.

Open-gpt runs locally and connects outbound through the official [OpenAI Secure MCP Tunnel](https://github.com/openai/tunnel-client). ChatGPT gets one plugin and one tunnel. Open-gpt fans that connection out to local STDIO MCPs and remote Streamable HTTP MCPs.

> **Full access is real.** In full mode, ChatGPT can run arbitrary shell commands and read, overwrite, or delete anything the Open-gpt service account can access. Open-gpt requires an explicit acknowledgement before it will start in this mode.

## Why it exists

Normally every Roblox, Rojo, Blender, filesystem, browser, or custom MCP needs its own ChatGPT connection. Adding another MCP means adding another tunnel or rescanning plugin actions.

Open-gpt keeps a small permanent tool surface in ChatGPT:

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
Open-gpt on your machine
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
git clone https://github.com/YOUR_NAME/Open-gpt.git
cd Open-gpt
./install.sh
```

The installer downloads the matching official `tunnel-client` release and verifies its published SHA-256 checksum when the binary is not already installed. On macOS it also installs the health menu-bar app. Set `OPEN_GPT_SKIP_TUNNEL_INSTALL=1` or `OPEN_GPT_SKIP_MENU=1` to manage either component yourself.

Make sure `~/.local/bin` is on `PATH`, then initialize full access:

```bash
opengpt init \
  --tunnel-id 'tunnel_<32-lowercase-hex-characters>' \
  --ask-key \
  --i-understand-full-access
```

The runtime key is stored in macOS Keychain. On Linux it is stored in a mode-`0600` file under `~/.config/opengpt/` unless `CONTROL_PLANE_API_KEY` is provided by the service environment.

Run it in the foreground first:

```bash
opengpt doctor
opengpt run
```

Then create or edit one ChatGPT Web plugin:

1. Enable ChatGPT developer mode.
2. Create a plugin using **Tunnel** connection mode.
3. Select the same tunnel ID.
4. Scan the tools and permit the write actions you want.
5. Start a new chat and enable the Open-gpt plugin.

## Background service

Mac runs Open-gpt inside the logged-in GUI user session so native app MCPs such as Roblox or Blender can work:

```bash
opengpt service install --scope user
./scripts/install-macos-menu.sh
```

Linux/VPS user service:

```bash
opengpt service install --scope user
```

Linux/VPS system service with root-level host permissions:

```bash
sudo ./install.sh --system
sudo opengpt init --tunnel-id tunnel_... --ask-key --i-understand-full-access
sudo opengpt service install --scope system
```

Only use the system/root mode on a VPS intentionally dedicated to this trust model.

## MCP management

Add a local STDIO MCP:

```bash
opengpt mcp add rojo --env ROJO_PROJECT_DIR=~/Projects -- npx -y YOUR_ROJO_MCP_PACKAGE
opengpt mcp add roblox -- /absolute/path/to/roblox-mcp --stdio
```

Add a remote MCP:

```bash
opengpt mcp add-url context7 https://mcp.context7.com/mcp
opengpt mcp add-url private https://example.com/mcp --header 'Authorization=Bearer {env:PRIVATE_MCP_TOKEN}'
```

Import OpenCode's MCP registry:

```bash
opengpt mcp import-opencode ~/.config/opencode/opencode.jsonc
```

Inspect and control it:

```bash
opengpt mcp list
opengpt mcp probe all
opengpt mcp find blender
opengpt mcp disable blender
opengpt mcp enable blender
opengpt status
opengpt ui
```

The same operations are available to ChatGPT through the stable registry tools. The local dashboard can add HTTP MCPs, probe health, enable/disable, and remove servers.

## Scoped mode

For users who do not want whole-machine access:

```bash
opengpt init --scoped-root ~/Projects --scoped-root ~/Documents
```

In scoped mode, Open-gpt rejects file paths and command working directories outside those roots. This is a path boundary, not a complete OS sandbox; a child command can still have the permissions of the service account.

## Direct versus dynamic MCP exposure

- `dynamic` (default): available immediately through `mcp_find_tools` and `mcp_call`; no ChatGPT refresh.
- `direct`: every child tool also appears as `server_tool` in ChatGPT. Faster to call, but changing the set requires restarting Open-gpt and refreshing ChatGPT plugin actions.

```bash
opengpt mcp add-url context7 https://mcp.context7.com/mcp --expose direct
```

## Health

- Gateway: `http://127.0.0.1:8766/healthz`, `/readyz`, `/ui`
- Tunnel: `http://127.0.0.1:8088/healthz`, `/readyz`, `/metrics`, `/ui`

`opengpt doctor` checks the configuration, tunnel ID, runtime key, tunnel binary, access acknowledgement, and registry.

## Security model

- The OpenAI tunnel is outbound-only; Open-gpt does not publish the local MCP endpoint.
- Full access is disabled until explicitly acknowledged.
- Runtime tunnel credentials are not written to the registry JSON.
- MCP environment variables and HTTP headers are redacted from the dashboard status response.
- Child MCPs run with the same OS identity as Open-gpt. Only install MCPs you trust.
- Tool descriptions from a malicious MCP can influence the model. Review third-party MCP source and pin package versions for serious use.

## Development

```bash
uv sync --extra dev
uv run pytest
uv run opengpt --help
```

MIT licensed. Open-gpt is independent software and is not affiliated with or endorsed by OpenAI.
