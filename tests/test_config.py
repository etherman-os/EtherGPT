from pathlib import Path

import pytest

from ethergpt.config import (
    default_config,
    load_config,
    resolve_access_path,
    save_config,
    server_mcp_config,
    setup_status,
    validate_tunnel_id,
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


def test_setup_status_lists_missing_connection_fields() -> None:
    config = default_config()
    state = setup_status(config, runtime_key_configured=False)
    assert state["complete"] is False
    assert state["missing"] == [
        "tunnel_id",
        "runtime_api_key",
        "full_access_acknowledgement",
    ]

    config["tunnel"]["tunnel_id"] = "tunnel_" + "a" * 32
    config["access"]["acknowledged_full_access"] = True
    state = setup_status(config, runtime_key_configured=True)
    assert state["complete"] is True
    assert state["missing"] == []


def test_tunnel_id_validation() -> None:
    assert validate_tunnel_id("tunnel_" + "0" * 32).startswith("tunnel_")
    with pytest.raises(ValueError, match="Tunnel ID"):
        validate_tunnel_id("not-a-tunnel")
