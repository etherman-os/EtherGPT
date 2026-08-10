from __future__ import annotations

import json
import os
import re
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any


SERVER_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")


def default_config_path() -> Path:
    override = os.environ.get("OPEN_GPT_CONFIG")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".config" / "opengpt" / "config.json"


def default_config() -> dict[str, Any]:
    return {
        "version": 1,
        "name": f"Open-gpt - {os.uname().nodename}",
        "access": {
            "mode": "full",
            "acknowledged_full_access": False,
            "allowed_roots": [],
            "max_output_chars": 120_000,
            "max_read_chars": 250_000,
            "max_timeout_seconds": 900,
        },
        "gateway": {
            "host": "127.0.0.1",
            "port": 8766,
            "mcp_path": "/mcp",
        },
        "tunnel": {
            "tunnel_id": "",
            "binary": "tunnel-client",
            "health_host": "127.0.0.1",
            "health_port": 8088,
        },
        "servers": {},
    }


def validate_server_name(name: str) -> str:
    if not SERVER_NAME_RE.fullmatch(name):
        raise ValueError(
            "MCP name must be 1-64 characters: letters, digits, dot, dash, underscore"
        )
    return name


def _validate(config: dict[str, Any]) -> None:
    if config.get("version") != 1:
        raise ValueError("Unsupported config version")
    access = config.get("access", {})
    if access.get("mode") not in {"full", "scoped"}:
        raise ValueError("access.mode must be 'full' or 'scoped'")
    if access.get("mode") == "full" and not isinstance(
        access.get("acknowledged_full_access", False), bool
    ):
        raise ValueError("access.acknowledged_full_access must be true or false")
    gateway = config.get("gateway", {})
    port = int(gateway.get("port", 0))
    if not 1 <= port <= 65535:
        raise ValueError("gateway.port must be between 1 and 65535")
    for name, server in config.get("servers", {}).items():
        validate_server_name(name)
        kind = server.get("type")
        if kind not in {"stdio", "http"}:
            raise ValueError(f"{name}: type must be stdio or http")
        if server.get("expose", "dynamic") not in {"dynamic", "direct"}:
            raise ValueError(f"{name}: expose must be dynamic or direct")
        if kind == "stdio":
            command = server.get("command")
            if not isinstance(command, list) or not command or not all(
                isinstance(part, str) and part for part in command
            ):
                raise ValueError(f"{name}: stdio command must be a non-empty string array")
        if kind == "http" and not isinstance(server.get("url"), str):
            raise ValueError(f"{name}: HTTP server requires url")


def load_config(path: Path | None = None) -> dict[str, Any]:
    config_path = path or default_config_path()
    if not config_path.exists():
        config = default_config()
        _validate(config)
        return config
    config = json.loads(config_path.read_text(encoding="utf-8"))
    _validate(config)
    return config


def save_config(config: dict[str, Any], path: Path | None = None) -> Path:
    config_path = path or default_config_path()
    _validate(config)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(config, indent=2, ensure_ascii=False) + "\n"
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{config_path.name}.", dir=config_path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
        os.chmod(temporary, 0o600)
        temporary.replace(config_path)
    finally:
        temporary.unlink(missing_ok=True)
    return config_path


def resolve_secret_ref(value: str) -> str:
    if value.startswith("env:"):
        key = value[4:]
        if not key or key not in os.environ:
            raise ValueError(f"Missing environment variable: {key}")
        return os.environ[key]
    if value.startswith("file:"):
        return Path(value[5:]).expanduser().read_text(encoding="utf-8").strip()
    match = re.fullmatch(r"\{env:([A-Za-z_][A-Za-z0-9_]*)\}", value)
    if match:
        key = match.group(1)
        if key not in os.environ:
            raise ValueError(f"Missing environment variable: {key}")
        return os.environ[key]
    return value


def server_mcp_config(
    name: str, server: dict[str, Any], *, resolve_secrets: bool = True
) -> dict[str, Any]:
    validate_server_name(name)
    if server["type"] == "stdio":
        command = server["command"]
        entry: dict[str, Any] = {
            "command": command[0],
            "args": command[1:],
        }
        if server.get("cwd"):
            entry["cwd"] = str(Path(server["cwd"]).expanduser())
        if server.get("env"):
            entry["env"] = {
                key: resolve_secret_ref(str(value)) if resolve_secrets else str(value)
                for key, value in server["env"].items()
            }
    else:
        entry = {
            "url": server["url"],
            "transport": "http",
        }
        if server.get("headers"):
            entry["headers"] = {
                key: resolve_secret_ref(str(value)) if resolve_secrets else str(value)
                for key, value in server["headers"].items()
            }
    if server.get("timeout_ms"):
        entry["timeout"] = int(server["timeout_ms"])
    return {"mcpServers": {name: entry}}


def enabled_server(config: dict[str, Any], name: str) -> dict[str, Any]:
    server = config.get("servers", {}).get(name)
    if not server:
        raise KeyError(f"Unknown MCP server: {name}")
    if not server.get("enabled", True):
        raise ValueError(f"MCP server is disabled: {name}")
    return server


def direct_mcp_config(config: dict[str, Any]) -> dict[str, Any] | None:
    merged: dict[str, Any] = {"mcpServers": {}}
    for name, server in config.get("servers", {}).items():
        if server.get("enabled", True) and server.get("expose", "dynamic") == "direct":
            child = server_mcp_config(name, server)
            merged["mcpServers"].update(child["mcpServers"])
    return merged if merged["mcpServers"] else None


def public_config(config: dict[str, Any]) -> dict[str, Any]:
    safe = deepcopy(config)
    tunnel_id = safe.get("tunnel", {}).get("tunnel_id", "")
    if tunnel_id:
        safe["tunnel"]["tunnel_id"] = f"{tunnel_id[:11]}...{tunnel_id[-4:]}"
    for server in safe.get("servers", {}).values():
        for field in ("env", "headers"):
            if field in server:
                server[field] = {key: "<configured>" for key in server[field]}
    return safe


def resolve_access_path(config: dict[str, Any], raw_path: str) -> Path:
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    path = path.resolve(strict=False)
    access = config.get("access", {})
    if access.get("mode") == "full":
        return path
    roots = [Path(root).expanduser().resolve(strict=False) for root in access.get("allowed_roots", [])]
    if not roots:
        raise PermissionError("Scoped mode has no allowed_roots")
    if not any(path == root or path.is_relative_to(root) for root in roots):
        raise PermissionError(f"Path is outside allowed roots: {path}")
    return path
