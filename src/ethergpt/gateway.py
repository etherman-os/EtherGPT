from __future__ import annotations

import asyncio
import json
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal

from fastmcp import Client, FastMCP
from fastmcp.server import create_proxy
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
    validate_server_name,
)
from .host_tools import register_host_tools


DASHBOARD_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>EtherGPT</title>
  <style>
    :root { color-scheme: dark; font-family: ui-sans-serif, system-ui, sans-serif; }
    body { margin: 0; background: #0a0d12; color: #e9eef8; }
    main { max-width: 980px; margin: 0 auto; padding: 40px 22px; }
    h1 { margin: 0; font-size: 30px; }
    .sub { color: #8f9bad; margin: 8px 0 28px; }
    .top, .server { background: #121821; border: 1px solid #253044; border-radius: 14px; }
    .top { padding: 20px; display: grid; grid-template-columns: repeat(auto-fit,minmax(180px,1fr)); gap: 12px; }
    .metric { background: #0d121a; border-radius: 10px; padding: 14px; }
    .label { color: #8490a3; font-size: 12px; text-transform: uppercase; letter-spacing: .08em; }
    .value { margin-top: 7px; font-size: 18px; font-weight: 650; }
    .ok { color: #43d18b; } .off { color: #f1b84b; } .bad { color: #ff6b72; }
    h2 { margin: 30px 0 12px; font-size: 18px; }
    #servers { display: grid; gap: 10px; }
    .server { padding: 15px 17px; display: flex; justify-content: space-between; align-items: center; }
    .name { font-weight: 650; } .details { color: #8f9bad; font-size: 13px; margin-top: 4px; }
    .actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
    .pill, button { border-radius: 99px; background: #202a38; padding: 6px 10px; font-size: 12px; }
    button { color: #dfe8f8; border: 1px solid #35445b; cursor: pointer; }
    button:hover { border-color: #6d86ad; }
    button.enabled { color: #43d18b; border-color: #287a58; background: #142b24; }
    button.disabled { color: #aeb8c8; border-color: #445066; background: #1a202b; }
    .danger { color: #ff9298; }
    form { margin-top: 14px; display: grid; grid-template-columns: 1fr 2fr auto; gap: 8px; }
    input, select { color: #e9eef8; background: #0d121a; border: 1px solid #35445b; border-radius: 8px; padding: 9px; }
    code { color: #b8c7e8; }
  </style>
</head>
<body><main>
  <h1>EtherGPT</h1>
  <p class="sub">One private ChatGPT connection for this machine and all of its MCP servers.</p>
  <section class="top" id="summary"><div class="metric">Loading…</div></section>
  <h2>MCP registry</h2><section id="servers"></section>
  <form id="add-http"><input name="name" placeholder="MCP name" required><input name="url" placeholder="https://…/mcp" required><button>Add HTTP MCP</button></form>
</main>
<script>
async function refresh() {
  const response = await fetch('/api/status');
  const data = await response.json();
  document.querySelector('#summary').innerHTML = `
    <div class="metric"><div class="label">Gateway</div><div class="value ok">Live</div></div>
    <div class="metric"><div class="label">Host</div><div class="value">${data.hostname}</div></div>
    <div class="metric"><div class="label">Access</div><div class="value">${data.access_mode}</div></div>
    <div class="metric"><div class="label">Registered MCPs</div><div class="value">${data.server_count}</div></div>`;
  const rows = Object.entries(data.servers).map(([name, server]) => {
    const healthClass = server.runtime_status === 'connected' ? 'ok' : (server.runtime_status === 'failed' ? 'bad' : 'off');
    const state = server.enabled ? server.runtime_status : 'disabled';
    const enabledLabel = server.enabled ? 'Enabled' : 'Disabled';
    const enabledClass = server.enabled ? 'enabled' : 'disabled';
    return `<div class="server"><div><div class="name">${name}</div><div class="details">${server.type} · ${server.expose} · ${server.tool_count ?? 0} tools</div></div><div class="actions"><button class="${enabledClass}" onclick="setEnabled('${name}', ${!server.enabled})">${enabledLabel}</button><button class="danger" onclick="removeServer('${name}')">Remove</button><div class="pill ${healthClass}">${state}</div></div></div>`;
  });
  document.querySelector('#servers').innerHTML = rows.join('') || '<div class="server">No MCP servers registered yet.</div>';
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


def _result_to_dict(result: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if getattr(result, "data", None) is not None:
        payload["data"] = result.data
    if getattr(result, "structured_content", None) is not None:
        payload["structured_content"] = result.structured_content
    content = getattr(result, "content", None)
    if content is not None:
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
    return {
        "ok": True,
        "service": "ethergpt",
        "version": __version__,
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
    ) -> dict[str, Any]:
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
        return {"server": server_name, "tool": tool_name, "result": _result_to_dict(result)}

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
            return JSONResponse({"status": "ready", **_status_snapshot(current)})
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
