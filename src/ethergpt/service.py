from __future__ import annotations

import os
import platform
import plistlib
import subprocess
import sys
from pathlib import Path
from typing import Literal


LAUNCHD_LABEL = "org.ethergpt.gateway"
SYSTEMD_UNIT = "ethergpt.service"


def _program_arguments(config_path: Path) -> list[str]:
    return [sys.executable, "-m", "ethergpt.cli", "--config", str(config_path), "run"]


def install_service(config_path: Path, scope: Literal["user", "system"] = "user") -> Path:
    system = platform.system()
    if system == "Darwin":
        if scope != "user":
            raise ValueError("macOS gateway must run in the logged-in user session")
        logs = Path.home() / "Library" / "Logs" / "EtherGPT"
        logs.mkdir(parents=True, exist_ok=True)
        target = Path.home() / "Library" / "LaunchAgents" / f"{LAUNCHD_LABEL}.plist"
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "Label": LAUNCHD_LABEL,
            "ProgramArguments": _program_arguments(config_path),
            "RunAtLoad": True,
            "KeepAlive": True,
            "ProcessType": "Interactive",
            "StandardOutPath": str(logs / "gateway.log"),
            "StandardErrorPath": str(logs / "gateway-error.log"),
            "EnvironmentVariables": {
                "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
            },
        }
        target.write_bytes(plistlib.dumps(payload, sort_keys=False))
        domain = f"gui/{os.getuid()}"
        subprocess.run(
            ["launchctl", "bootout", domain, str(target)],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        subprocess.run(["launchctl", "bootstrap", domain, str(target)], check=True)
        subprocess.run(["launchctl", "enable", f"{domain}/{LAUNCHD_LABEL}"], check=True)
        subprocess.run(["launchctl", "kickstart", "-k", f"{domain}/{LAUNCHD_LABEL}"], check=True)
        return target
    if system != "Linux":
        raise ValueError(f"Unsupported service platform: {system}")
    user_mode = scope == "user"
    if user_mode:
        target = Path.home() / ".config" / "systemd" / "user" / SYSTEMD_UNIT
        target.parent.mkdir(parents=True, exist_ok=True)
    else:
        if os.geteuid() != 0:
            raise PermissionError("System service installation must run as root")
        target = Path("/etc/systemd/system") / SYSTEMD_UNIT
    arguments = " ".join(_systemd_quote(value) for value in _program_arguments(config_path))
    target.write_text(
        "[Unit]\n"
        "Description=EtherGPT for ChatGPT\n"
        "After=network-online.target\n"
        "Wants=network-online.target\n\n"
        "[Service]\n"
        "Type=simple\n"
        f"ExecStart={arguments}\n"
        "Environment=PATH=/usr/local/bin:/usr/bin:/bin\n"
        "Restart=always\n"
        "RestartSec=3\n"
        "TimeoutStopSec=15\n\n"
        "[Install]\n"
        "WantedBy=default.target\n" if user_mode else
        "[Unit]\n"
        "Description=EtherGPT for ChatGPT\n"
        "After=network-online.target\n"
        "Wants=network-online.target\n\n"
        "[Service]\n"
        "Type=simple\n"
        "User=root\n"
        "Group=root\n"
        f"ExecStart={arguments}\n"
        "Environment=PATH=/usr/local/bin:/usr/bin:/bin\n"
        "Restart=always\n"
        "RestartSec=3\n"
        "TimeoutStopSec=15\n\n"
        "[Install]\n"
        "WantedBy=multi-user.target\n",
        encoding="utf-8",
    )
    command = ["systemctl"] + (["--user"] if user_mode else [])
    subprocess.run(command + ["daemon-reload"], check=True)
    subprocess.run(command + ["enable", "--now", SYSTEMD_UNIT], check=True)
    return target


def _systemd_quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def service_action(action: Literal["start", "stop", "restart", "status"]) -> int:
    system = platform.system()
    if system == "Darwin":
        domain = f"gui/{os.getuid()}"
        service = f"{domain}/{LAUNCHD_LABEL}"
        target = Path.home() / "Library" / "LaunchAgents" / f"{LAUNCHD_LABEL}.plist"
        if action == "start":
            loaded = subprocess.run(
                ["launchctl", "print", service],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            ).returncode == 0
            if not loaded:
                if not target.exists():
                    print(f"Service is not installed: {target}", file=sys.stderr)
                    return 1
                result = subprocess.run(
                    ["launchctl", "bootstrap", domain, str(target)], check=False
                )
                if result.returncode != 0:
                    return result.returncode
            return subprocess.run(
                ["launchctl", "kickstart", "-k", service], check=False
            ).returncode
        if action == "stop":
            return subprocess.run(
                ["launchctl", "bootout", domain, str(target)], check=False
            ).returncode
        if action == "restart":
            subprocess.run(
                ["launchctl", "bootout", domain, str(target)],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            result = subprocess.run(
                ["launchctl", "bootstrap", domain, str(target)], check=False
            )
            if result.returncode != 0:
                return result.returncode
            return subprocess.run(
                ["launchctl", "kickstart", "-k", service], check=False
            ).returncode
        return subprocess.run(["launchctl", "print", service], check=False).returncode
    command = ["systemctl"]
    if os.geteuid() != 0:
        command.append("--user")
    return subprocess.run(command + [action, SYSTEMD_UNIT], check=False).returncode
