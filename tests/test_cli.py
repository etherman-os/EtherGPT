from ethergpt.cli import build_parser


def test_bare_ethergpt_defaults_to_power_on() -> None:
    args = build_parser().parse_args([])
    assert args.action is None


def test_power_commands_parse() -> None:
    assert build_parser().parse_args(["on"]).action == "on"
    assert build_parser().parse_args(["off"]).action == "off"


def test_update_command_parses() -> None:
    assert build_parser().parse_args(["update"]).action == "update"
