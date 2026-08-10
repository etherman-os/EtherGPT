from pathlib import Path

import pytest

from opengpt.config import (
    default_config,
    load_config,
    resolve_access_path,
    save_config,
    server_mcp_config,
)


def test_config_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    config = default_config()
    config["servers"]["sample"] = {
        "type": "stdio",
        "command": ["python", "sample.py"],
        "enabled": True,
        "expose": "dynamic",
    }
    save_config(config, path)
    assert load_config(path) == config
    assert path.stat().st_mode & 0o777 == 0o600


def test_standard_mcp_config_conversion() -> None:
    result = server_mcp_config(
        "sample",
        {
            "type": "stdio",
            "command": ["python", "sample.py"],
            "enabled": True,
            "expose": "dynamic",
        },
    )
    assert result == {
        "mcpServers": {"sample": {"command": "python", "args": ["sample.py"]}}
    }


def test_scoped_access_rejects_outside_root(tmp_path: Path) -> None:
    root = tmp_path / "allowed"
    root.mkdir()
    config = default_config()
    config["access"] = {"mode": "scoped", "allowed_roots": [str(root)]}
    assert resolve_access_path(config, str(root / "file.txt")) == root / "file.txt"
    with pytest.raises(PermissionError):
        resolve_access_path(config, str(tmp_path / "outside.txt"))
