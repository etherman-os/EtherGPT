from pathlib import Path

from ethergpt import cli
from ethergpt.cli import build_parser
from ethergpt.config import default_config, save_config


def test_bare_ethergpt_defaults_to_power_on() -> None:
    args = build_parser().parse_args([])
    assert args.action is None


def test_power_commands_parse() -> None:
    assert build_parser().parse_args(["on"]).action == "on"
    assert build_parser().parse_args(["off"]).action == "off"


def test_update_command_parses() -> None:
    assert build_parser().parse_args(["update"]).action == "update"


def test_setup_command_parses() -> None:
    args = build_parser().parse_args(["setup", "--if-needed"])
    assert args.action == "setup"
    assert args.if_needed is True


def test_runtime_fingerprint_ignores_dynamic_registry_changes(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(cli, "get_runtime_key", lambda: "test-key")
    path = tmp_path / "config.json"
    config = default_config()
    save_config(config, path)
    before = cli._runtime_snapshot(path)[3]

    config["servers"]["sample"] = {
        "type": "http",
        "url": "https://example.com/mcp",
        "enabled": True,
        "expose": "dynamic",
    }
    save_config(config, path)
    after_registry = cli._runtime_snapshot(path)[3]
    assert after_registry == before

    config["tunnel"]["tunnel_id"] = "tunnel_" + "c" * 32
    save_config(config, path)
    assert cli._runtime_snapshot(path)[3] != before
