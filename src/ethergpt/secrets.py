from __future__ import annotations

import getpass
import os
import platform
import subprocess
from pathlib import Path

from .config import default_config_path


KEYCHAIN_SERVICE = "org.ethergpt.openai-tunnel-runtime"


def _linux_secret_path() -> Path:
    override = os.environ.get("ETHERGPT_RUNTIME_KEY_FILE")
    if override:
        return Path(override).expanduser()
    return default_config_path().parent / "runtime.key"


def set_runtime_key(key: str) -> None:
    if not key:
        raise ValueError("Runtime key cannot be empty")
    if platform.system() == "Darwin":
        account = getpass.getuser()
        subprocess.run(
            ["security", "delete-generic-password", "-s", KEYCHAIN_SERVICE, "-a", account],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        subprocess.run(
            [
                "security",
                "add-generic-password",
                "-U",
                "-s",
                KEYCHAIN_SERVICE,
                "-a",
                account,
                "-w",
                key,
            ],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        return
    path = _linux_secret_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(key.strip() + "\n", encoding="utf-8")
    os.chmod(path, 0o600)


def get_runtime_key() -> str | None:
    environment = os.environ.get("CONTROL_PLANE_API_KEY")
    if environment:
        return environment
    if platform.system() == "Darwin":
        result = subprocess.run(
            [
                "security",
                "find-generic-password",
                "-s",
                KEYCHAIN_SERVICE,
                "-a",
                getpass.getuser(),
                "-w",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        value = result.stdout.strip()
        return value or None
    path = _linux_secret_path()
    if path.exists():
        value = path.read_text(encoding="utf-8").strip()
        return value or None
    return None
