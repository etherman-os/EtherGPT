from __future__ import annotations

import asyncio
import json
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal

from fastmcp import Client, FastMCP
from fastmcp.server import create_proxy
from fastmcp.tools import ToolResult
from mcp.types import ToolAnnotations
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse

from . import __version__
from .config import (
    default_config_path,
    enabled_server,
    load_config,
    public_config,
    save_config,
    server_mcp_config,
    setup_status,
    validate_tunnel_id,
    validate_server_name,
)
from .host_tools import register_host_tools
from .secrets import get_runtime_key, set_runtime_key


DASHBOARD_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>EtherGPT</title>
  <style>
    :root { color-scheme: dark; font-family: ui-sans-serif, system-ui, sans-serif; }
    * { box-sizing: border-box; }
    body { margin: 0; background: #0a0d12; color: #e9eef8; }
    main { max-width: 980px; margin: 0 auto; padding: 40px 22px 70px; }
    header { display: flex; justify-content: space-between; align-items: flex-start; gap: 18px; }
    h1 { margin: 0; font-size: 30px; }
    h2 { margin: 30px 0 12px; font-size: 18px; }
    .sub, .help { color: #8f9bad; }
    .sub { margin: 8px 0 28px; }
    .help { font-size: 13px; line-height: 1.5; }
    a { color: #9db9ff; }
    .top, .server, details, .setup-banner { background: #121821; border: 1px solid #253044; border-radius: 14px; }
    .top { padding: 20px; display: grid; grid-template-columns: repeat(auto-fit,minmax(180px,1fr)); gap: 12px; }
    .metric { background: #0d121a; border-radius: 10px; padding: 14px; }
    .label { color: #8490a3; font-size: 12px; text-transform: uppercase; letter-spacing: .08em; }
    .value { margin-top: 7px; font-size: 18px; font-weight: 650; overflow-wrap: anywhere; }
    .ok { color: #43d18b; } .off { color: #f1b84b; } .bad { color: #ff6b72; }
    .setup-banner { padding: 18px 20px; margin-bottom: 18px; border-color: #9a6b20; background: #241c10; display: flex; justify-content: space-between; align-items: center; gap: 16px; }
    .setup-banner strong { display: block; color: #ffd18a; margin-bottom: 5px; }
    .hidden { display: none !important; }
    details { margin: 18px 0 0; overflow: hidden; }
    summary { cursor: pointer; padding: 16px 18px; font-weight: 650; }
    .config-body { padding: 0 18px 20px; border-top: 1px solid #253044; }
    .config-grid { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 14px; margin-top: 18px; }
    .field { display: grid; gap: 7px; }
    .field.wide { grid-column: 1 / -1; }
    .field label { color: #c6d1e3; font-size: 13px; font-weight: 600; }
    input, select, textarea { width: 100%; color: #e9eef8; background: #0d121a; border: 1px solid #35445b; border-radius: 8px; padding: 10px; }
    textarea { min-height: 76px; resize: vertical; }
    .check { display: flex; gap: 10px; align-items: flex-start; color: #c6d1e3; font-size: 13px; line-height: 1.4; }
    .check input { width: auto; margin-top: 3px; }
    .form-result { min-height: 20px; margin-top: 12px; font-size: 13px; }
    #servers { display: grid; gap: 10px; }
    .server { padding: 15px 17px; display: flex; justify-content: space-between; align-items: center; gap: 15px; }
    .name { font-weight: 650; } .details { color: #8f9bad; font-size: 13px; margin-top: 4px; }
    .actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; justify-content: flex-end; }
    .pill, button { border-radius: 99px; background: #202a38; padding: 7px 11px; font-size: 12px; }
    button { color: #dfe8f8; border: 1px solid #35445b; cursor: pointer; }
    button:hover { border-color: #6d86ad; }
    button.primary { background: #315fcc; border-color: #5680e5; color: white; }
    button.enabled { color: #43d18b; border-color: #287a58; background: #142b24; }
    button.disabled { color: #aeb8c8; border-color: #445066; background: #1a202b; }
    .danger { color: #ff9298; }
    #add-http { margin-top: 14px; display: grid; grid-template-columns: 1fr 2fr auto; gap: 8px; }
    code { color: #b8c7e8; }
    @media (max-width: 700px) {
      header, .setup-banner, .server { align-items: stretch; flex-direction: column; }
      .config-grid, #add-http { grid-template-columns: 1fr; }
      .field.wide { grid-column: auto; }
      .actions { justify-content: flex-start; }
    }
  </style>
</head>
<body><main>
  <header>
    <div><h1>EtherGPT</h1><p class="sub">One private ChatGPT connection for this machine and all of its MCP servers.</p></div>
    <button id="config-button">Config &amp; setup</button>
  </header>

  <section class="setup-banner hidden" id="setup-banner">
    <div><strong>Setup required</strong><span id="setup-missing">Add your tunnel details to connect ChatGPT.</span></div>
    <button class="primary" onclick="openSetup()">Set up now</button>
  </section>

  <section class="top" id="summary"><div class="metric">Loading…</div></section>

  <details id="config-panel">
    <summary>Connection and host access</summary>
    <div class="config-body">
      <p class="help">Create a tunnel in <a href="https://platform.openai.com/settings/organization/tunnels" target="_blank" rel="noreferrer">OpenAI Platform tunnel settings</a>. Use its <code>tunnel_id</code> and the runtime API key created for <code>tunnel-client</code>; this is not a normal model API key.</p>
      <form id="setup-form">
        <div class="config-grid">
          <div class="field"><label for="machine-name">Machine name</label><input id="machine-name" name="name" required maxlength="128"></div>
          <div class="field"><label for="access-mode">Host access</label><select id="access-mode" name="access_mode"><option value="full">Full host access</option><option value="scoped">Selected folders only</option></select></div>
          <div class="field"><label for="tunnel-id">Tunnel ID</label><input id="tunnel-id" name="tunnel_id" autocomplete="off" placeholder="tunnel_…"></div>
          <div class="field"><label for="runtime-key">Tunnel runtime API key</label><input id="runtime-key" name="runtime_key" type="password" autocomplete="new-password" placeholder="Paste runtime key"></div>
          <div class="field wide hidden" id="roots-field"><label for="allowed-roots">Allowed folders</label><textarea id="allowed-roots" name="allowed_roots" placeholder="~/Projects, ~/Documents"></textarea></div>
          <label class="check field wide" id="full-access-field"><input id="full-access" name="acknowledge_full_access" type="checkbox"><span>I understand that ChatGPT can run commands and read, create, change, or delete files anywhere on this host.</span></label>
        </div>
        <p class="help">Leaving an already configured tunnel ID or runtime key blank keeps its current value. Saving restarts the local gateway and tunnel automatically.</p>
        <button class="primary" id="save-setup" type="submit">Save connection</button>
        <div class="form-result" id="setup-result"></div>
      </form>
    </div>
  </details>

  <h2>MCP registry</h2><section id="servers"></section>
  <form id="add-http"><input name="name" placeholder="MCP name" required><input name="url" placeholder="https://…/mcp" required><button>Add HTTP MCP</button></form>
</main>
<script>
let formInitialized = false;
function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, character => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[character]));
}
function openSetup() {
  const panel = document.querySelector('#config-panel');
  panel.open = true;
  panel.scrollIntoView({behavior:'smooth', block:'start'});
}
function syncAccessFields() {
  const scoped = document.querySelector('#access-mode').value === 'scoped';
  document.querySelector('#roots-field').classList.toggle('hidden', !scoped);
  document.querySelector('#full-access-field').classList.toggle('hidden', scoped);
}
async function refresh() {
  try {
    const response = await fetch('/api/status');
    const data = await response.json();
    const setupRequired = !data.setup_complete;
    document.querySelector('#setup-banner').classList.toggle('hidden', !setupRequired);
    document.querySelector('#setup-missing').textContent = setupRequired
      ? `Missing: ${data.setup.missing.join(', ').replaceAll('_', ' ')}`
      : 'Connection configured.';
    document.querySelector('#config-button').textContent = setupRequired ? 'Setup required — press here' : 'Config & setup';
    if (setupRequired) document.querySelector('#config-panel').open = true;
    document.querySelector('#summary').innerHTML = `
      <div class="metric"><div class="label">Gateway</div><div class="value ok">Live</div></div>
      <div class="metric"><div class="label">Connection</div><div class="value ${setupRequired ? 'off' : 'ok'}">${setupRequired ? 'Setup required' : 'Configured'}</div></div>
      <div class="metric"><div class="label">Host</div><div class="value">${escapeHtml(data.hostname)}</div></div>
      <div class="metric"><div class="label">Access</div><div class="value">${escapeHtml(data.access_mode)}</div></div>
      <div class="metric"><div class="label">Registered MCPs</div><div class="value">${data.server_count}</div></div>`;

    if (!formInitialized) {
      document.querySelector('#machine-name').value = data.config.name || '';
      document.querySelector('#access-mode').value = data.config.access.mode || 'full';
      document.querySelector('#allowed-roots').value = (data.config.access.allowed_roots || []).join(', ');
      document.querySelector('#full-access').checked = Boolean(data.config.access.acknowledged_full_access);
      document.querySelector('#tunnel-id').placeholder = data.setup.tunnel_id_configured ? `${data.config.tunnel.tunnel_id} (leave blank to keep)` : 'tunnel_…';
      document.querySelector('#runtime-key').placeholder = data.setup.runtime_key_configured ? 'Configured — leave blank to keep' : 'Paste runtime key';
      syncAccessFields();
      formInitialized = true;
    }

    const rows = Object.entries(data.servers).map(([name, server]) => {
      const healthClass = server.runtime_status === 'connected' ? 'ok' : (server.runtime_status === 'failed' ? 'bad' : 'off');
      const state = server.enabled ? server.runtime_status : 'disabled';
      const enabledLabel = server.enabled ? 'Enabled' : 'Disabled';
      const enabledClass = server.enabled ? 'enabled' : 'disabled';
      return `<div class="server"><div><div class="name">${escapeHtml(name)}</div><div class="details">${escapeHtml(server.type)} · ${escapeHtml(server.expose)} · ${server.tool_count ?? 0} tools</div></div><div class="actions"><button class="${enabledClass}" onclick="setEnabled('${name}', ${!server.enabled})">${enabledLabel}</button><button class="danger" onclick="removeServer('${name}')">Remove</button><div class="pill ${healthClass}">${escapeHtml(state)}</div></div></div>`;
    });
    document.querySelector('#servers').innerHTML = rows.join('') || '<div class="server">No MCP servers registered yet.</div>';
  } catch (error) {
    document.querySelector('#setup-result').textContent = 'Gateway is refreshing…';
  }
}
async function setEnabled(name, enabled) {
  await fetch('/api/server/enabled', {method:'POST', headers:{'content-type':'application/json'}, body:JSON.stringify({name, enabled})});
  await refresh();
}
async function removeServer(name) {
  if (!confirm(`Remove ${name}?`)) return;
  await fetch('/api/server/remove', {method:'POST', headers:{'content-type':'application/json'}, body:JSON.stringify({name})});
  await refresh();
}
document.querySelector('#config-button').addEventListener('click', openSetup);
document.querySelector('#access-mode').addEventListener('change', syncAccessFields);
document.querySelector('#setup-form').addEventListener('submit', async event => {
  event.preventDefault();
  const button = document.querySelector('#save-setup');
  const result = document.querySelector('#setup-result');
  button.disabled = true;
  result.className = 'form-result';
  result.textContent = 'Saving securely…';
  const values = Object.fromEntries(new FormData(event.target));
  values.acknowledge_full_access = document.querySelector('#full-access').checked;
  try {
    const response = await fetch('/api/setup', {method:'POST', headers:{'content-type':'application/json'}, body:JSON.stringify(values)});
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || 'Could not save setup');
    result.className = 'form-result ok';
    result.textContent = 'Saved. Gateway and tunnel are refreshing…';
    document.querySelector('#runtime-key').value = '';
    document.querySelector('#tunnel-id').value = '';
    formInitialized = false;
    setTimeout(refresh, 1200);
  } catch (error) {
    result.className = 'form-result bad';
    result.textContent = error.message;
  } finally {
    button.disabled = false;
  }
});
document.querySelector('#add-http').addEventListener('submit', async event => {
  event.preventDefault();
  const values = Object.fromEntries(new FormData(event.target));
  const response = await fetch('/api/server/http', {method:'POST', headers:{'content-type':'application/json'}, body:JSON.stringify(values)});
  if (!response.ok) alert((await response.json()).error || 'Could not add MCP');
  else { event.target.reset(); await refresh(); }
});
refresh(); setInterval(refresh, 5000);
</script></body></html>"""


def _tool_to_dict(tool: Any) -> dict[str, Any]:
    if hasattr(tool, "model_dump"):
        payload = tool.model_dump(mode="json", exclude_none=True)
    else:
        payload = {"name": str(tool)}
    return payload


def _result_to_dict(result: Any, *, include_content: bool = True) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if getattr(result, "data", None) is not None:
        payload["data"] = result.data
    if getattr(result, "structured_content", None) is not None:
        payload["structured_content"] = result.structured_content
    content = getattr(result, "content", None)
    if include_content and content is not None:
        payload["content"] = [
            item.model_dump(mode="json", exclude_none=True)
            if hasattr(item, "model_dump")
            else str(item)
            for item in content
        ]
    payload["is_error"] = bool(getattr(result, "is_error", False))
    return payload


def _status_snapshot(
    config: dict[str, Any], runtime_states: dict[str, dict[str, Any]] | None = None
) -> dict[str, Any]:
    runtime_states = runtime_states or {}
    setup = setup_status(config, runtime_key_configured=bool(get_runtime_key()))
    return {
        "ok": True,
        "service": "ethergpt",
        "version": __version__,
        "setup_complete": setup["complete"],
        "setup": setup,
        "hostname": __import__("platform").node(),
        "name": config.get("name"),
        "access_mode": config.get("access", {}).get("mode"),
        "server_count": len(config.get("servers", {})),
        "servers": {
            name: {
                "type": server.get("type"),
                "enabled": server.get("enabled", True),
                "expose": server.get("expose", "dynamic"),
                "runtime_status": (
                    "disabled"
                    if not server.get("enabled", True)
                    else runtime_states.get(name, {}).get("status", "not_checked")
                ),
                "tool_count": runtime_states.get(name, {}).get("tool_count"),
                "last_checked_at": runtime_states.get(name, {}).get("checked_at"),
                "error": runtime_states.get(name, {}).get("error"),
            }
            for name, server in config.get("servers", {}).items()
        },
    }


class ChildClientPool:
    """Keep STDIO and HTTP child MCP sessions alive between ChatGPT tool calls."""

    def __init__(self) -> None:
        self._clients: dict[str, tuple[str, Client[Any]]] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    @staticmethod
    def _fingerprint(server: dict[str, Any]) -> str:
        return json.dumps(server, sort_keys=True, separators=(",", ":"))

    @asynccontextmanager
    async def connect(self, name: str, server: dict[str, Any]):
        lock = self._locks.setdefault(name, asyncio.Lock())
        async with lock:
            fingerprint = self._fingerprint(server)
            existing = self._clients.get(name)
            if existing and existing[0] != fingerprint:
                await existing[1].__aexit__(None, None, None)
                self._clients.pop(name, None)
                existing = None
            if existing is None:
                timeout = max(1.0, float(server.get("timeout_ms", 30_000)) / 1000)
                client = Client(
                    server_mcp_config(name, server), timeout=timeout, init_timeout=timeout
                )
                await client.__aenter__()
                self._clients[name] = (fingerprint, client)
            yield self._clients[name][1]

    async def invalidate(self, name: str) -> None:
        lock = self._locks.setdefault(name, asyncio.Lock())
        async with lock:
            existing = self._clients.pop(name, None)
            if existing:
                await existing[1].__aexit__(None, None, None)

    async def close(self) -> None:
        for name in list(self._clients):
            await self.invalidate(name)


def create_gateway(config_path: Path | None = None) -> FastMCP:
    path = config_path or default_config_path()
    initial = load_config(path)
    runtime_states: dict[str, dict[str, Any]] = {}
    child_pool = ChildClientPool()

    @asynccontextmanager
    async def lifespan(server: FastMCP):
        try:
            yield {}
        finally:
            await child_pool.close()

    mcp = FastMCP(
        initial.get("name", "EtherGPT"),
        version=__version__,
        instructions=(
            "This is the trusted host gateway for one user-controlled computer. "
            "Use host_* tools for terminal and filesystem work. Use mcp_servers, "
            "mcp_tools and mcp_call to discover and call optional MCP servers. "
            "The owner intentionally enabled full host access when access_mode is full."
        ),
        lifespan=lifespan,
    )
    register_host_tools(mcp, initial)

    for child_name, child_server in initial.get("servers", {}).items():
        if child_server.get("enabled", True) and child_server.get("expose", "dynamic") == "direct":
            mcp.mount(
                create_proxy(server_mcp_config(child_name, child_server)),
                namespace=child_name,
            )

    async def probe_server(server_name: str) -> dict[str, Any]:
        started = time.monotonic()
        try:
            current = load_config(path)
            server = enabled_server(current, server_name)
            timeout = max(1.0, float(server.get("timeout_ms", 30_000)) / 1000)
            async with child_pool.connect(server_name, server) as client:
                tools = await asyncio.wait_for(client.list_tools(), timeout=timeout)
            state = {
                "status": "connected",
                "tool_count": len(tools),
                "latency_ms": round((time.monotonic() - started) * 1000),
                "checked_at": int(time.time()),
            }
        except Exception as exc:
            state = {
                "status": "failed",
                "tool_count": 0,
                "latency_ms": round((time.monotonic() - started) * 1000),
                "checked_at": int(time.time()),
                "error": f"{type(exc).__name__}: {exc}"[:600],
            }
        runtime_states[server_name] = state
        return {"server": server_name, **state}

    @mcp.tool(
        annotations=ToolAnnotations(
            title="Gateway status",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        )
    )
    def gateway_status() -> dict[str, Any]:
        """Return gateway health, host name, access mode and registered MCP states."""
        return _status_snapshot(load_config(path), runtime_states)

    @mcp.tool(
        annotations=ToolAnnotations(
            title="List MCP servers",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        )
    )
    def mcp_servers() -> dict[str, Any]:
        """List registered child MCP servers and whether each is enabled and directly exposed."""
        current = load_config(path)
        return {
            "servers": _status_snapshot(current, runtime_states)["servers"],
            "note": (
                "Dynamic servers are immediately available through mcp_tools/mcp_call. "
                "Direct server metadata changes require a gateway restart and ChatGPT plugin refresh."
            ),
        }

    @mcp.tool(
        annotations=ToolAnnotations(
            title="List child MCP tools",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        )
    )
    async def mcp_tools(server_name: str) -> dict[str, Any]:
        """Connect to one enabled child MCP server and return its current tool schemas."""
        current = load_config(path)
        server = enabled_server(current, server_name)
        async with child_pool.connect(server_name, server) as client:
            tools = await client.list_tools()
        runtime_states[server_name] = {
            "status": "connected",
            "tool_count": len(tools),
            "checked_at": int(time.time()),
        }
        return {"server": server_name, "tools": [_tool_to_dict(tool) for tool in tools]}

    @mcp.tool(
        annotations=ToolAnnotations(
            title="Find tools across MCP servers",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        )
    )
    async def mcp_find_tools(query: str = "", max_results: int = 50) -> dict[str, Any]:
        """Search live tool names and descriptions across every enabled child MCP.

        This stable discovery tool lets ChatGPT use MCPs added after the plugin was
        connected, without rescanning the ChatGPT plugin action list.
        """
        current = load_config(path)
        names = [
            name
            for name, server in current.get("servers", {}).items()
            if server.get("enabled", True)
        ]
        needle = query.casefold().strip()

        async def inspect(name: str) -> tuple[str, list[Any] | None, str | None]:
            try:
                server = enabled_server(current, name)
                timeout = max(1.0, float(server.get("timeout_ms", 30_000)) / 1000)
                async with child_pool.connect(name, server) as client:
                    tools = await client.list_tools()
                runtime_states[name] = {
                    "status": "connected",
                    "tool_count": len(tools),
                    "checked_at": int(time.time()),
                }
                return name, list(tools), None
            except Exception as exc:
                runtime_states[name] = {
                    "status": "failed",
                    "tool_count": 0,
                    "checked_at": int(time.time()),
                    "error": f"{type(exc).__name__}: {exc}"[:600],
                }
                return name, None, runtime_states[name]["error"]

        inspected = await asyncio.gather(*(inspect(name) for name in names))
        matches: list[dict[str, Any]] = []
        errors: dict[str, str] = {}
        for server_name, tools, error in inspected:
            if error:
                errors[server_name] = error
                continue
            for tool in tools or []:
                payload = _tool_to_dict(tool)
                haystack = f"{payload.get('name', '')} {payload.get('description', '')}".casefold()
                if needle and needle not in haystack:
                    continue
                matches.append({"server": server_name, **payload})
        limit = max(1, min(int(max_results), 500))
        return {
            "query": query,
            "matches": matches[:limit],
            "total_matches": len(matches),
            "truncated": len(matches) > limit,
            "errors": errors,
        }

    @mcp.tool(
        annotations=ToolAnnotations(
            title="Call child MCP tool",
            readOnlyHint=False,
            destructiveHint=True,
            idempotentHint=False,
            openWorldHint=True,
        )
    )
    async def mcp_call(
        server_name: str, tool_name: str, arguments: dict[str, Any] | None = None
    ) -> ToolResult:
        """Call a tool on an enabled child MCP without adding another ChatGPT connection.

        First call mcp_tools to learn the exact tool name and argument schema. Tool safety
        depends on the selected child server, so this generic dispatcher is marked destructive.
        """
        current = load_config(path)
        server = enabled_server(current, server_name)
        async with child_pool.connect(server_name, server) as client:
            result = await client.call_tool(tool_name, arguments or {})
        runtime_states[server_name] = {
            "status": "connected",
            "checked_at": int(time.time()),
            "tool_count": runtime_states.get(server_name, {}).get("tool_count"),
        }
        # Keep child media/resource blocks at the top level. If an ImageContent
        # block is nested inside JSON, ChatGPT only sees an opaque base64 string
        # and cannot inspect its pixels without an unreliable conversion step.
        return ToolResult(
            content=list(getattr(result, "content", None) or []),
            structured_content={
                "server": server_name,
                "tool": tool_name,
                "result": _result_to_dict(result, include_content=False),
            },
            is_error=bool(getattr(result, "is_error", False)),
        )

    @mcp.tool(
        annotations=ToolAnnotations(
            title="Probe child MCP",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        )
    )
    async def mcp_probe(server_name: str) -> dict[str, Any]:
        """Check one enabled child MCP connection and report latency, tool count or error."""
        return await probe_server(server_name)

    @mcp.tool(
        annotations=ToolAnnotations(
            title="Enable or disable MCP",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        )
    )
    async def mcp_set_enabled(server_name: str, enabled: bool) -> dict[str, Any]:
        """Enable or disable a registered child MCP server."""
        current = load_config(path)
        if server_name not in current.get("servers", {}):
            raise KeyError(f"Unknown MCP server: {server_name}")
        current["servers"][server_name]["enabled"] = bool(enabled)
        save_config(current, path)
        await child_pool.invalidate(server_name)
        runtime_states[server_name] = {
            "status": "not_checked" if enabled else "disabled",
            "checked_at": int(time.time()),
        }
        direct = current["servers"][server_name].get("expose", "dynamic") == "direct"
        return {
            "ok": True,
            "server": server_name,
            "enabled": bool(enabled),
            "gateway_restart_required": direct,
            "chatgpt_refresh_required": direct,
        }

    @mcp.tool(
        annotations=ToolAnnotations(
            title="Register local MCP",
            readOnlyHint=False,
            destructiveHint=True,
            idempotentHint=True,
            openWorldHint=True,
        )
    )
    async def mcp_add_stdio(
        server_name: str,
        command: list[str],
        cwd: str | None = None,
        environment: dict[str, str] | None = None,
        expose: Literal["dynamic", "direct"] = "dynamic",
    ) -> dict[str, Any]:
        """Register or replace a local stdio MCP command in this machine's registry."""
        validate_server_name(server_name)
        if not command:
            raise ValueError("command cannot be empty")
        current = load_config(path)
        entry: dict[str, Any] = {
            "type": "stdio",
            "command": command,
            "enabled": True,
            "expose": expose,
        }
        if cwd:
            entry["cwd"] = cwd
        if environment:
            entry["env"] = environment
        current.setdefault("servers", {})[server_name] = entry
        save_config(current, path)
        await child_pool.invalidate(server_name)
        return {
            "ok": True,
            "server": server_name,
            "gateway_restart_required": expose == "direct",
            "chatgpt_refresh_required": expose == "direct",
        }

    @mcp.tool(
        annotations=ToolAnnotations(
            title="Register remote MCP",
            readOnlyHint=False,
            destructiveHint=True,
            idempotentHint=True,
            openWorldHint=True,
        )
    )
    async def mcp_add_http(
        server_name: str,
        url: str,
        headers: dict[str, str] | None = None,
        expose: Literal["dynamic", "direct"] = "dynamic",
    ) -> dict[str, Any]:
        """Register or replace a Streamable HTTP MCP server in this machine's registry."""
        validate_server_name(server_name)
        current = load_config(path)
        entry: dict[str, Any] = {
            "type": "http",
            "url": url,
            "enabled": True,
            "expose": expose,
        }
        if headers:
            entry["headers"] = headers
        current.setdefault("servers", {})[server_name] = entry
        save_config(current, path)
        await child_pool.invalidate(server_name)
        return {
            "ok": True,
            "server": server_name,
            "gateway_restart_required": expose == "direct",
            "chatgpt_refresh_required": expose == "direct",
        }

    @mcp.tool(
        annotations=ToolAnnotations(
            title="Remove MCP server",
            readOnlyHint=False,
            destructiveHint=True,
            idempotentHint=True,
            openWorldHint=False,
        )
    )
    async def mcp_remove(server_name: str) -> dict[str, Any]:
        """Remove a child MCP from the EtherGPT registry."""
        current = load_config(path)
        if server_name not in current.get("servers", {}):
            raise KeyError(f"Unknown MCP server: {server_name}")
        direct = current["servers"][server_name].get("expose", "dynamic") == "direct"
        del current["servers"][server_name]
        save_config(current, path)
        await child_pool.invalidate(server_name)
        runtime_states.pop(server_name, None)
        return {
            "ok": True,
            "server": server_name,
            "gateway_restart_required": direct,
            "chatgpt_refresh_required": direct,
        }

    @mcp.custom_route("/healthz", methods=["GET"])
    async def healthz(request: Request) -> JSONResponse:
        return JSONResponse({"status": "live", "service": "ethergpt", "version": __version__})

    @mcp.custom_route("/readyz", methods=["GET"])
    async def readyz(request: Request) -> JSONResponse:
        try:
            current = load_config(path)
            snapshot = _status_snapshot(current)
            status = "ready" if snapshot["setup_complete"] else "setup_required"
            return JSONResponse({"status": status, **snapshot})
        except Exception as exc:
            return JSONResponse(
                {"status": "not_ready", "error": f"{type(exc).__name__}: {exc}"}, status_code=503
            )

    @mcp.custom_route("/api/status", methods=["GET"])
    async def api_status(request: Request) -> JSONResponse:
        current = load_config(path)
        return JSONResponse(
            {**_status_snapshot(current, runtime_states), "config": public_config(current)}
        )

    @mcp.custom_route("/api/setup", methods=["POST"])
    async def api_setup(request: Request) -> JSONResponse:
        try:
            payload = await request.json()
            current = load_config(path)

            name = str(payload.get("name", current.get("name", "EtherGPT"))).strip()
            if not name or len(name) > 128:
                raise ValueError("Machine name must be 1-128 characters")
            current["name"] = name

            submitted_tunnel = str(payload.get("tunnel_id", "")).strip()
            tunnel_id = submitted_tunnel or str(
                current.get("tunnel", {}).get("tunnel_id", "")
            )
            current["tunnel"]["tunnel_id"] = validate_tunnel_id(tunnel_id)

            runtime_key = str(payload.get("runtime_key", "")).strip()
            if not runtime_key and not get_runtime_key():
                raise ValueError("Tunnel runtime API key is required")

            mode = str(payload.get("access_mode", "full")).strip().casefold()
            if mode == "full":
                if payload.get("acknowledge_full_access") is not True:
                    raise ValueError("Full host access must be explicitly acknowledged")
                current["access"]["mode"] = "full"
                current["access"]["acknowledged_full_access"] = True
                current["access"]["allowed_roots"] = []
            elif mode == "scoped":
                raw_roots = payload.get("allowed_roots", [])
                if isinstance(raw_roots, str):
                    raw_roots = raw_roots.replace("\n", ",").split(",")
                if not isinstance(raw_roots, list):
                    raise ValueError("Allowed folders must be a list")
                roots = [
                    str(Path(str(root).strip()).expanduser().resolve())
                    for root in raw_roots
                    if str(root).strip()
                ]
                if not roots:
                    raise ValueError("Scoped access needs at least one allowed folder")
                current["access"]["mode"] = "scoped"
                current["access"]["acknowledged_full_access"] = False
                current["access"]["allowed_roots"] = roots
            else:
                raise ValueError("Access mode must be full or scoped")

            if runtime_key:
                set_runtime_key(runtime_key)
            save_config(current, path)
            return JSONResponse(
                {
                    "ok": True,
                    "setup": setup_status(
                        current, runtime_key_configured=bool(get_runtime_key())
                    ),
                    "config": public_config(current),
                    "restart_pending": True,
                }
            )
        except Exception as exc:
            return JSONResponse(
                {"error": f"{type(exc).__name__}: {exc}"}, status_code=400
            )

    @mcp.custom_route("/api/probe", methods=["POST"])
    async def api_probe(request: Request) -> JSONResponse:
        payload = await request.json()
        name = str(payload.get("name", ""))
        return JSONResponse(await probe_server(name))

    @mcp.custom_route("/api/server/enabled", methods=["POST"])
    async def api_server_enabled(request: Request) -> JSONResponse:
        payload = await request.json()
        name = str(payload.get("name", ""))
        current = load_config(path)
        if name not in current.get("servers", {}):
            return JSONResponse({"error": f"Unknown MCP server: {name}"}, status_code=404)
        current["servers"][name]["enabled"] = bool(payload.get("enabled"))
        save_config(current, path)
        await child_pool.invalidate(name)
        return JSONResponse({"ok": True, "name": name, "enabled": payload.get("enabled")})

    @mcp.custom_route("/api/server/remove", methods=["POST"])
    async def api_server_remove(request: Request) -> JSONResponse:
        payload = await request.json()
        name = str(payload.get("name", ""))
        current = load_config(path)
        if name not in current.get("servers", {}):
            return JSONResponse({"error": f"Unknown MCP server: {name}"}, status_code=404)
        del current["servers"][name]
        save_config(current, path)
        await child_pool.invalidate(name)
        runtime_states.pop(name, None)
        return JSONResponse({"ok": True, "name": name})

    @mcp.custom_route("/api/server/http", methods=["POST"])
    async def api_server_http(request: Request) -> JSONResponse:
        try:
            payload = await request.json()
            name = validate_server_name(str(payload.get("name", "")))
            url = str(payload.get("url", "")).strip()
            if not url.startswith(("http://", "https://")):
                raise ValueError("URL must start with http:// or https://")
            current = load_config(path)
            current.setdefault("servers", {})[name] = {
                "type": "http",
                "url": url,
                "enabled": True,
                "expose": "dynamic",
            }
            save_config(current, path)
            await child_pool.invalidate(name)
            return JSONResponse({"ok": True, "name": name, "url": url})
        except Exception as exc:
            return JSONResponse({"error": f"{type(exc).__name__}: {exc}"}, status_code=400)

    @mcp.custom_route("/ui", methods=["GET"])
    async def dashboard(request: Request) -> HTMLResponse:
        return HTMLResponse(DASHBOARD_HTML)

    return mcp
