from pathlib import Path

import pytest

from ethergpt import updater


def test_git_root_walks_up_from_package_file(tmp_path: Path) -> None:
    root = tmp_path / "EtherGPT"
    package = root / "src" / "ethergpt"
    package.mkdir(parents=True)
    (root / ".git").mkdir()
    (root / "pyproject.toml").write_text('[project]\nversion = "9.8.7"\n')
    module = package / "updater.py"
    module.write_text("")
    assert updater._git_root(module) == root
    assert updater.source_version(root) == "9.8.7"


def test_dirty_checkout_is_refused(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(updater, "_output", lambda command, cwd: " M README.md")
    with pytest.raises(RuntimeError, match="local changes"):
        updater._ensure_clean_checkout(tmp_path)


def test_default_root_for_root_linux(monkeypatch) -> None:
    monkeypatch.setattr(updater.platform, "system", lambda: "Linux")
    monkeypatch.setattr(updater.os, "geteuid", lambda: 0)
    assert updater.default_source_root() == Path("/opt/ethergpt-source")
