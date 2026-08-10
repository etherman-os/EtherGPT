from __future__ import annotations

from pathlib import Path
from typing import Any

import json5

from .config import load_config, save_config, validate_server_name


def import_opencode(
    source: Path,
    destination: Path,
    *,
    expose: str = "dynamic",
    replace: bool = False,
) -> dict[str, Any]:
    raw = json5.loads(source.read_text(encoding="utf-8"))
    mcp_section = raw.get("mcp", {})
    if isinstance(mcp_section, dict) and isinstance(mcp_section.get("servers"), dict):
        mcp_section = mcp_section["servers"]
    if not isinstance(mcp_section, dict):
        raise ValueError("OpenCode config has no MCP server map")
    config = load_config(destination)
    imported: list[str] = []
    skipped: list[str] = []
    unsupported: list[str] = []
    for name, server in mcp_section.items():
        try:
            validate_server_name(name)
        except ValueError:
            unsupported.append(name)
            continue
        if name in config.get("servers", {}) and not replace:
            skipped.append(name)
            continue
        if not isinstance(server, dict):
            unsupported.append(name)
            continue
        kind = server.get("type", "local")
        if kind == "local" and isinstance(server.get("command"), list):
            converted: dict[str, Any] = {
                "type": "stdio",
                "command": [str(part) for part in server["command"]],
                "enabled": bool(server.get("enabled", True)),
                "expose": expose,
            }
            environment = server.get("environment") or server.get("env")
            if isinstance(environment, dict) and environment:
                converted["env"] = {str(key): str(value) for key, value in environment.items()}
            if server.get("cwd"):
                converted["cwd"] = str(server["cwd"])
        elif kind == "remote" and isinstance(server.get("url"), str):
            converted = {
                "type": "http",
                "url": server["url"],
                "enabled": bool(server.get("enabled", True)),
                "expose": expose,
            }
            if isinstance(server.get("headers"), dict) and server["headers"]:
                converted["headers"] = {
                    str(key): str(value) for key, value in server["headers"].items()
                }
        else:
            unsupported.append(name)
            continue
        if server.get("timeout"):
            converted["timeout_ms"] = int(server["timeout"])
        config.setdefault("servers", {})[name] = converted
        imported.append(name)
    save_config(config, destination)
    return {"imported": imported, "skipped": skipped, "unsupported": unsupported}
