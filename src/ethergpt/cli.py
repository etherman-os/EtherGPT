from __future__ import annotations

import argparse
import asyncio
import getpass
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from fastmcp import Client

from . import __version__
from .config import (
    default_config,
    default_config_path,
    enabled_server,
    load_config,
    public_config,
    save_config,
    server_mcp_config,
    validate_server_name,
)
from .gateway import create_gateway
from .secrets import get_runtime_key, set_runtime_key
from .service import install_service, service_action


def _path(value: str | None) -> Path:
    return Path(value).expanduser() if value else default_config_path()


def _print_json(value: Any) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False, default=str))


def _http_json(url: str, timeout: float = 2.0) -> dict[str, Any] | None:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError):
        return None


def _http_health(url: str, timeout: float = 2.0) -> dict[str, Any] | None:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace").strip()
            try:
                parsed = json.loads(raw)
                return parsed if isinstance(parsed, dict) else {"status": str(parsed)}
            except json.JSONDecodeError:
                return {"status": raw or "ok", "http_status": response.status}
    except (OSError, urllib.error.URLError):
        return None


def _gateway_base(config: dict[str, Any]) -> str:
    gateway = config["gateway"]
    return f"http://{gateway['host']}:{gateway['port']}"


def command_init(args: argparse.Namespace) -> int:
    path = _path(args.config)
    config = load_config(path) if path.exists() else default_config()
    if args.name:
        config["name"] = args.name
    if args.tunnel_binary:
        config["tunnel"]["binary"] = str(Path(args.tunnel_binary).expanduser())
    if args.i_understand_full_access:
        config["access"]["mode"] = "full"
        config["access"]["acknowledged_full_access"] = True
        config["access"]["allowed_roots"] = []
    elif args.scoped_root:
        config["access"]["mode"] = "scoped"
        config["access"]["acknowledged_full_access"] = False
        config["access"]["allowed_roots"] = [
            str(Path(root).expanduser().resolve()) for root in args.scoped_root
        ]
    tunnel_id = args.tunnel_id
    if tunnel_id is None and sys.stdin.isatty():
        current = config["tunnel"].get("tunnel_id", "")
        tunnel_id = input(f"OpenAI tunnel ID [{current or 'not set'}]: ").strip() or current
    if tunnel_id is not None:
        if tunnel_id and not re.fullmatch(r"tunnel_[0-9a-f]{32}", tunnel_id):
            raise ValueError("Tunnel ID must be tunnel_ followed by 32 hexadecimal characters")
        config["tunnel"]["tunnel_id"] = tunnel_id
    save_config(config, path)
    runtime_key = args.runtime_key
    if runtime_key is None and args.ask_key and sys.stdin.isatty():
        runtime_key = getpass.getpass("OpenAI tunnel runtime API key: ").strip()
    if runtime_key:
        set_runtime_key(runtime_key)
    print(f"Config: {path}")
    print(f"Runtime key: {'configured' if get_runtime_key() else 'missing'}")
    print(f"Access mode: {config['access']['mode']}")
    return 0


def command_serve(args: argparse.Namespace) -> int:
    path = _path(args.config)
    config = load_config(path)
    gateway = config["gateway"]
    create_gateway(path).run(
        transport="http",
        host=gateway["host"],
        port=int(gateway["port"]),
        path=gateway.get("mcp_path", "/mcp"),
        show_banner=not args.no_banner,
    )
    return 0


def _wait_for_gateway(base_url: str, process: subprocess.Popen[Any], timeout: float = 30) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Gateway exited with code {process.returncode}")
        if _http_json(f"{base_url}/readyz", timeout=0.5):
            return
        time.sleep(0.2)
    raise TimeoutError("Gateway did not become ready")


def command_run(args: argparse.Namespace) -> int:
    path = _path(args.config).resolve()
    config = load_config(path)
    if config["access"].get("mode") == "full" and not config["access"].get(
        "acknowledged_full_access", False
    ):
        raise PermissionError(
            "Full access must be explicitly acknowledged: "
            "ethergpt init --i-understand-full-access"
        )
    tunnel = config["tunnel"]
    tunnel_id = tunnel.get("tunnel_id", "")
    if not tunnel_id:
        raise RuntimeError("Tunnel ID is missing; run ethergpt init")
    runtime_key = get_runtime_key()
    if not runtime_key:
        raise RuntimeError("Runtime API key is missing; run ethergpt init --ask-key")
    binary_raw = str(tunnel.get("binary", "tunnel-client"))
    binary = shutil.which(binary_raw) or str(Path(binary_raw).expanduser())
    if not Path(binary).is_file():
        raise FileNotFoundError(f"tunnel-client not found: {binary_raw}")

    gateway_process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "ethergpt.cli",
            "--config",
            str(path),
            "serve",
            "--no-banner",
        ]
    )
    tunnel_process: subprocess.Popen[Any] | None = None

    def stop_children(signum: int | None = None, frame: Any = None) -> None:
        for child in (tunnel_process, gateway_process):
            if child is not None and child.poll() is None:
                child.terminate()

    signal.signal(signal.SIGTERM, stop_children)
    signal.signal(signal.SIGINT, stop_children)

    try:
        base = _gateway_base(config)
        _wait_for_gateway(base, gateway_process)
        environment = os.environ.copy()
        environment["CONTROL_PLANE_API_KEY"] = runtime_key
        tunnel_process = subprocess.Popen(
            [
                binary,
                "run",
                f"--control-plane.tunnel-id={tunnel_id}",
                "--control-plane.api-key=env:CONTROL_PLANE_API_KEY",
                f"--mcp.server-url={base}{config['gateway'].get('mcp_path', '/mcp')}",
                "--mcp.connection-max-ttl=60m",
                f"--health.listen-addr={tunnel['health_host']}:{tunnel['health_port']}",
                "--log.level=info",
                "--log.format=struct-text",
            ],
            env=environment,
        )
        while True:
            gateway_code = gateway_process.poll()
            tunnel_code = tunnel_process.poll()
            if gateway_code is not None or tunnel_code is not None:
                return gateway_code if gateway_code is not None else int(tunnel_code or 0)
            time.sleep(0.5)
    finally:
        stop_children()
        for child in (tunnel_process, gateway_process):
            if child is not None:
                try:
                    child.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    child.kill()


def command_status(args: argparse.Namespace) -> int:
    path = _path(args.config)
    config = load_config(path)
    gateway = _http_json(f"{_gateway_base(config)}/api/status")
    tunnel = config["tunnel"]
    tunnel_base = f"http://{tunnel['health_host']}:{tunnel['health_port']}"
    payload = {
        "gateway": gateway or {"ok": False, "status": "offline"},
        "tunnel": {
            "health": _http_health(f"{tunnel_base}/healthz") or {"status": "offline"},
            "ready": _http_health(f"{tunnel_base}/readyz") or {"status": "not_ready"},
            "ui": f"{tunnel_base}/ui",
        },
        "gateway_ui": f"{_gateway_base(config)}/ui",
    }
    if args.json:
        _print_json(payload)
    else:
        gateway_state = "ONLINE" if gateway else "OFFLINE"
        tunnel_state = payload["tunnel"]["ready"].get("status", "not_ready")
        print(f"Gateway: {gateway_state}  {_gateway_base(config)}")
        print(f"Tunnel:  {tunnel_state}  {tunnel_base}")
        print(f"MCPs:    {len(config.get('servers', {}))} registered")
        for name, server in config.get("servers", {}).items():
            state = "enabled" if server.get("enabled", True) else "disabled"
            print(f"  - {name}: {state}, {server['type']}, {server.get('expose', 'dynamic')}")
    return 0 if gateway and payload["tunnel"]["health"].get("status") != "offline" else 1


def command_doctor(args: argparse.Namespace) -> int:
    path = _path(args.config)
    failures = 0
    try:
        config = load_config(path)
        print(f"✓ config: {path}")
    except Exception as exc:
        print(f"✗ config: {type(exc).__name__}: {exc}")
        return 1
    tunnel_id = config["tunnel"].get("tunnel_id", "")
    if tunnel_id:
        print("✓ tunnel ID configured")
    else:
        print("✗ tunnel ID missing")
        failures += 1
    if get_runtime_key():
        print("✓ runtime key configured")
    else:
        print("✗ runtime key missing")
        failures += 1
    binary_raw = str(config["tunnel"].get("binary", "tunnel-client"))
    binary = shutil.which(binary_raw) or str(Path(binary_raw).expanduser())
    if Path(binary).is_file():
        result = subprocess.run([binary, "--version"], capture_output=True, text=True, check=False)
        print(f"✓ tunnel-client: {(result.stdout or result.stderr).strip()}")
    else:
        print(f"✗ tunnel-client not found: {binary_raw}")
        failures += 1
    print(f"✓ access mode: {config['access']['mode']}")
    if config["access"]["mode"] == "full":
        if config["access"].get("acknowledged_full_access"):
            print("✓ full host access explicitly acknowledged")
        else:
            print("✗ full host access not acknowledged")
            failures += 1
    print(f"✓ MCP registry: {len(config.get('servers', {}))} entries")
    return 1 if failures else 0


def _mutate_server(path: Path, name: str, mutation: str) -> None:
    config = load_config(path)
    if name not in config.get("servers", {}):
        raise KeyError(f"Unknown MCP server: {name}")
    if mutation == "remove":
        del config["servers"][name]
    else:
        config["servers"][name]["enabled"] = mutation == "enable"
    save_config(config, path)


def _key_values(values: list[str], label: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for value in values:
        key, separator, item = value.partition("=")
        if not separator or not key:
            raise ValueError(f"{label} must use KEY=VALUE format: {value}")
        result[key] = item
    return result


def command_mcp(args: argparse.Namespace) -> int:
    path = _path(args.config)
    config = load_config(path)
    action = args.mcp_action
    if action == "list":
        payload = {
            name: {
                "enabled": server.get("enabled", True),
                "type": server["type"],
                "expose": server.get("expose", "dynamic"),
                "target": server.get("url") or server.get("command"),
            }
            for name, server in config.get("servers", {}).items()
        }
        if args.json:
            _print_json(payload)
        else:
            for name, server in payload.items():
                state = "✓" if server["enabled"] else "○"
                print(f"{state} {name:<20} {server['type']:<6} {server['expose']:<7} {server['target']}")
            if not payload:
                print("No MCP servers registered")
        return 0
    if action == "add":
        validate_server_name(args.name)
        command = list(args.command)
        environment_values = list(args.env)
        cwd = args.cwd
        expose = args.expose
        while command and command[0] != "--":
            option = command.pop(0)
            if option == "--env" and command:
                environment_values.append(command.pop(0))
            elif option == "--cwd" and command:
                cwd = command.pop(0)
            elif option == "--expose" and command:
                expose = command.pop(0)
                if expose not in {"dynamic", "direct"}:
                    raise ValueError("--expose must be dynamic or direct")
            else:
                command.insert(0, option)
                break
        if command and command[0] == "--":
            command = command[1:]
        if not command:
            raise ValueError("Usage: ethergpt mcp add NAME -- COMMAND [ARGS...]")
        config.setdefault("servers", {})[args.name] = {
            "type": "stdio",
            "command": command,
            "enabled": True,
            "expose": expose,
            **({"cwd": cwd} if cwd else {}),
            **(
                {"env": _key_values(environment_values, "--env")}
                if environment_values
                else {}
            ),
        }
        save_config(config, path)
        print(f"Added {args.name}; available immediately through mcp_tools/mcp_call")
        if expose == "direct":
            print("Direct exposure selected: restart gateway and refresh the ChatGPT plugin metadata")
        return 0
    if action == "add-url":
        validate_server_name(args.name)
        config.setdefault("servers", {})[args.name] = {
            "type": "http",
            "url": args.url,
            "enabled": True,
            "expose": args.expose,
            **(
                {"headers": _key_values(args.header, "--header")}
                if args.header
                else {}
            ),
        }
        save_config(config, path)
        print(f"Added {args.name}: {args.url}")
        return 0
    if action in {"enable", "disable", "remove"}:
        _mutate_server(path, args.name, action)
        print(f"{action}d {args.name}" if action != "remove" else f"removed {args.name}")
        return 0
    if action == "tools":
        return asyncio.run(_command_mcp_tools(path, args.name))
    if action == "find":
        return asyncio.run(_command_mcp_find(path, args.query, args.max_results))
    if action == "probe":
        return asyncio.run(_command_mcp_probe(path, args.name))
    if action == "call":
        arguments = json.loads(args.arguments) if args.arguments else {}
        return asyncio.run(_command_mcp_call(path, args.name, args.tool, arguments))
    raise ValueError(f"Unsupported MCP action: {action}")


def command_service(args: argparse.Namespace) -> int:
    path = _path(args.config).resolve()
    if args.service_action == "install":
        target = install_service(path, args.scope)
        print(f"Service installed: {target}")
        return 0
    return service_action(args.service_action)


def command_ui(args: argparse.Namespace) -> int:
    config = load_config(_path(args.config))
    url = f"{_gateway_base(config)}/ui"
    opener = "open" if sys.platform == "darwin" else "xdg-open"
    if shutil.which(opener):
        subprocess.run([opener, url], check=False)
    print(url)
    return 0


async def _command_mcp_tools(path: Path, name: str) -> int:
    config = load_config(path)
    server = enabled_server(config, name)
    async with Client(server_mcp_config(name, server)) as client:
        tools = await client.list_tools()
    _print_json([tool.model_dump(mode="json", exclude_none=True) for tool in tools])
    return 0


async def _command_mcp_call(path: Path, name: str, tool: str, arguments: dict[str, Any]) -> int:
    config = load_config(path)
    server = enabled_server(config, name)
    async with Client(server_mcp_config(name, server)) as client:
        result = await client.call_tool(tool, arguments)
    _print_json(result.model_dump(mode="json", exclude_none=True))
    return 0


async def _command_mcp_probe(path: Path, name: str) -> int:
    config = load_config(path)
    names = list(config.get("servers", {})) if name == "all" else [name]
    failed = False
    for server_name in names:
        started = time.monotonic()
        try:
            server = enabled_server(config, server_name)
            timeout = max(1.0, float(server.get("timeout_ms", 30_000)) / 1000)
            async with Client(
                server_mcp_config(server_name, server), timeout=timeout, init_timeout=timeout
            ) as client:
                tools = await client.list_tools()
            print(
                f"✓ {server_name}: connected, {len(tools)} tools, "
                f"{round((time.monotonic() - started) * 1000)} ms"
            )
        except Exception as exc:
            failed = True
            print(f"✗ {server_name}: {type(exc).__name__}: {exc}")
    return 1 if failed else 0


async def _command_mcp_find(path: Path, query: str, max_results: int) -> int:
    config = load_config(path)
    needle = query.casefold().strip()
    matches: list[dict[str, str]] = []
    for name, server in config.get("servers", {}).items():
        if not server.get("enabled", True):
            continue
        try:
            async with Client(server_mcp_config(name, server)) as client:
                tools = await client.list_tools()
            for tool in tools:
                description = tool.description or ""
                if needle and needle not in f"{tool.name} {description}".casefold():
                    continue
                matches.append(
                    {"server": name, "tool": tool.name, "description": description}
                )
        except Exception as exc:
            print(f"warning: {name}: {type(exc).__name__}: {exc}", file=sys.stderr)
    _print_json(matches[: max(1, min(max_results, 500))])
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ethergpt", description="One ChatGPT MCP gateway per machine")
    parser.add_argument("--config", help="Path to config.json")
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="action", required=True)

    init = subparsers.add_parser("init", help="Create configuration and store tunnel credentials")
    init.add_argument("--name")
    init.add_argument("--tunnel-id")
    init.add_argument("--tunnel-binary")
    init.add_argument("--runtime-key")
    init.add_argument("--ask-key", action="store_true")
    access = init.add_mutually_exclusive_group()
    access.add_argument(
        "--i-understand-full-access",
        action="store_true",
        help="Allow ChatGPT to run arbitrary commands and read/write the whole host",
    )
    access.add_argument(
        "--scoped-root",
        action="append",
        help="Restrict file and command working directories to this root (repeatable)",
    )

    serve = subparsers.add_parser("serve", help="Run only the local MCP gateway")
    serve.add_argument("--no-banner", action="store_true")
    subparsers.add_parser("run", help="Run gateway and OpenAI tunnel in the foreground")
    status = subparsers.add_parser("status", help="Show gateway and tunnel health")
    status.add_argument("--json", action="store_true")
    subparsers.add_parser("doctor", help="Validate configuration and dependencies")
    subparsers.add_parser("ui", help="Open the local gateway dashboard")

    service = subparsers.add_parser("service", help="Install or control the background service")
    service_sub = service.add_subparsers(dest="service_action", required=True)
    service_install = service_sub.add_parser("install")
    service_install.add_argument("--scope", choices=["user", "system"], default="user")
    for action in ("start", "stop", "restart", "status", "enable", "disable"):
        service_sub.add_parser(action)

    mcp = subparsers.add_parser("mcp", help="Manage child MCP servers")
    mcp_sub = mcp.add_subparsers(dest="mcp_action", required=True)
    mcp_list = mcp_sub.add_parser("list")
    mcp_list.add_argument("--json", action="store_true")
    mcp_add = mcp_sub.add_parser("add")
    mcp_add.add_argument("name")
    mcp_add.add_argument("--cwd")
    mcp_add.add_argument("--env", action="append", default=[], metavar="KEY=VALUE")
    mcp_add.add_argument("--expose", choices=["dynamic", "direct"], default="dynamic")
    mcp_add.add_argument("command", nargs=argparse.REMAINDER)
    mcp_url = mcp_sub.add_parser("add-url")
    mcp_url.add_argument("name")
    mcp_url.add_argument("url")
    mcp_url.add_argument("--header", action="append", default=[], metavar="KEY=VALUE")
    mcp_url.add_argument("--expose", choices=["dynamic", "direct"], default="dynamic")
    for action in ("enable", "disable", "remove", "tools"):
        child = mcp_sub.add_parser(action)
        child.add_argument("name")
    mcp_find = mcp_sub.add_parser("find")
    mcp_find.add_argument("query", nargs="?", default="")
    mcp_find.add_argument("--max-results", type=int, default=50)
    mcp_probe = mcp_sub.add_parser("probe")
    mcp_probe.add_argument("name", nargs="?", default="all")
    mcp_call = mcp_sub.add_parser("call")
    mcp_call.add_argument("name")
    mcp_call.add_argument("tool")
    mcp_call.add_argument("arguments", nargs="?", help="JSON object")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        if args.action == "init":
            return command_init(args)
        if args.action == "serve":
            return command_serve(args)
        if args.action == "run":
            return command_run(args)
        if args.action == "status":
            return command_status(args)
        if args.action == "doctor":
            return command_doctor(args)
        if args.action == "ui":
            return command_ui(args)
        if args.action == "service":
            return command_service(args)
        if args.action == "mcp":
            return command_mcp(args)
        parser.error("Unknown command")
        return 2
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
