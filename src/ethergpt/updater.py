from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

from . import __version__


OFFICIAL_REPOSITORY = "https://github.com/etherman-os/EtherGPT.git"


def _git_root(candidate: Path) -> Path | None:
    candidate = candidate.resolve()
    if candidate.is_file():
        candidate = candidate.parent
    for directory in (candidate, *candidate.parents):
        if (directory / ".git").exists() and (directory / "pyproject.toml").exists():
            return directory
    return None


def find_source_root() -> Path | None:
    override = os.environ.get("ETHERGPT_SOURCE_DIR")
    candidates = [
        Path(override).expanduser() if override else None,
        Path(__file__),
        Path(shutil.which("ethergpt") or sys.argv[0]),
        Path.cwd(),
        Path.home() / ".local" / "share" / "ethergpt" / "source",
        Path("/opt/ethergpt-source"),
    ]
    for candidate in candidates:
        if candidate is None:
            continue
        root = _git_root(candidate)
        if root is not None:
            return root
    return None


def default_source_root() -> Path:
    if platform.system() == "Linux" and os.geteuid() == 0:
        return Path("/opt/ethergpt-source")
    return Path.home() / ".local" / "share" / "ethergpt" / "source"


def source_version(root: Path) -> str:
    data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    return str(data["project"]["version"])


def _run(
    command: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    capture: bool = False,
) -> subprocess.CompletedProcess[str]:
    print("+ " + " ".join(command), flush=True)
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        check=False,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )


def _output(command: list[str], *, cwd: Path) -> str:
    result = _run(command, cwd=cwd, capture=True)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(detail or f"Command failed ({result.returncode})")
    return (result.stdout or "").strip()


def _ensure_clean_checkout(root: Path) -> None:
    dirty = _output(["git", "status", "--porcelain"], cwd=root)
    if dirty:
        raise RuntimeError(
            "Update stopped because the EtherGPT source has local changes. "
            f"Commit or stash them first: {root}"
        )


def _fetch_and_fast_forward(root: Path) -> bool:
    _ensure_clean_checkout(root)
    fetch = _run(["git", "fetch", "origin", "main"], cwd=root)
    if fetch.returncode != 0:
        raise RuntimeError("Could not fetch origin/main")

    current = _output(["git", "rev-parse", "HEAD"], cwd=root)
    latest = _output(["git", "rev-parse", "origin/main"], cwd=root)
    if current == latest:
        return False

    ancestor = _run(
        ["git", "merge-base", "--is-ancestor", "HEAD", "origin/main"], cwd=root
    )
    if ancestor.returncode != 0:
        raise RuntimeError(
            "Local history is not a fast-forward of origin/main; update refused."
        )
    merge = _run(["git", "merge", "--ff-only", "origin/main"], cwd=root)
    if merge.returncode != 0:
        raise RuntimeError("Fast-forward update failed")
    return True


def _install_environment() -> dict[str, str]:
    env = os.environ.copy()
    additions = [
        str(Path.home() / ".local" / "bin"),
        "/opt/homebrew/bin",
        "/usr/local/bin",
    ]
    env["PATH"] = ":".join(additions + [env.get("PATH", "")])
    return env


def _install(root: Path) -> None:
    system = platform.system()
    system_scope = system == "Linux" and os.geteuid() == 0
    installer = ["/bin/bash", str(root / "install.sh")]
    if system_scope:
        installer.append("--system")
    result = _run(installer, cwd=root, env=_install_environment())
    if result.returncode != 0:
        raise RuntimeError("EtherGPT installer failed")

    new_cli = root / ".venv" / "bin" / "ethergpt"
    if not new_cli.exists():
        raise RuntimeError(f"Updated EtherGPT command was not created: {new_cli}")
    scope = "system" if system_scope else "user"
    service = _run(
        [str(new_cli), "service", "install", "--scope", scope],
        cwd=root,
        env=_install_environment(),
    )
    if service.returncode != 0:
        raise RuntimeError("Updated EtherGPT service installation failed")
    if system == "Linux":
        restarted = _run(
            [str(new_cli), "service", "restart"],
            cwd=root,
            env=_install_environment(),
        )
        if restarted.returncode != 0:
            raise RuntimeError("Updated EtherGPT service restart failed")


def update() -> int:
    root = find_source_root()
    cloned = False
    if root is None:
        root = default_source_root()
        if root.exists() and any(root.iterdir()):
            raise RuntimeError(
                f"Update source path exists but is not an EtherGPT Git checkout: {root}"
            )
        root.parent.mkdir(parents=True, exist_ok=True)
        clone = _run(["git", "clone", OFFICIAL_REPOSITORY, str(root)])
        if clone.returncode != 0:
            raise RuntimeError("Could not clone the EtherGPT repository")
        cloned = True

    print(f"EtherGPT source: {root}")
    print(f"Installed version: {__version__}")
    changed = _fetch_and_fast_forward(root) if not cloned else True
    available = source_version(root)
    print(f"Available version: {available}")

    if not changed and available == __version__:
        print("EtherGPT is already up to date.")
        return 0

    _install(root)
    print(f"EtherGPT updated successfully: {__version__} -> {available}")
    return 0
