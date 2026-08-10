from pathlib import Path

import pytest
from fastmcp import Client
from mcp.types import ImageContent
from starlette.testclient import TestClient

from ethergpt import gateway as gateway_module
from ethergpt.config import default_config, load_config, save_config
from ethergpt.gateway import DASHBOARD_HTML, create_gateway


@pytest.fixture
def configured_gateway(tmp_path: Path):
    sample = Path(__file__).parent / "fixtures" / "sample_mcp.py"
    config = default_config()
    config["access"]["acknowledged_full_access"] = True
    config["name"] = "Test Gateway"
    config["servers"]["sample"] = {
        "type": "stdio",
        "command": [str(Path(__import__("sys").executable)), str(sample)],
        "enabled": True,
        "expose": "dynamic",
    }
    path = tmp_path / "config.json"
    save_config(config, path)
    return create_gateway(path)


async def test_gateway_host_and_registry_tools(configured_gateway) -> None:
    async with Client(configured_gateway) as client:
        tools = await client.list_tools()
        names = {tool.name for tool in tools}
        assert "host_info" in names
        assert "host_exec" in names
        assert "mcp_servers" in names
        assert "mcp_tools" in names
        assert "mcp_find_tools" in names
        assert "mcp_call" in names
        assert "mcp_probe" in names
        assert "host_replace_text" in names
        assert "host_process_start" in names


async def test_dynamic_child_tool_call(configured_gateway) -> None:
    async with Client(configured_gateway) as client:
        listed = await client.call_tool("mcp_tools", {"server_name": "sample"})
        tool_names = {tool["name"] for tool in listed.data["tools"]}
        assert "echo" in tool_names
        result = await client.call_tool(
            "mcp_call",
            {
                "server_name": "sample",
                "tool_name": "echo",
                "arguments": {"text": "hello"},
            },
        )
        assert result.data["result"]["data"] == {"echo": "hello"}


async def test_dynamic_child_image_is_forwarded_as_top_level_content(
    configured_gateway,
) -> None:
    async with Client(configured_gateway) as client:
        result = await client.call_tool(
            "mcp_call",
            {
                "server_name": "sample",
                "tool_name": "screenshot",
                "arguments": {},
            },
        )

    images = [item for item in result.content if isinstance(item, ImageContent)]
    assert len(images) == 1
    assert images[0].mimeType == "image/png"
    assert images[0].data
    assert result.data["server"] == "sample"
    assert result.data["tool"] == "screenshot"
    assert "content" not in result.data["result"]


async def test_find_tools_across_dynamic_servers(configured_gateway) -> None:
    async with Client(configured_gateway) as client:
        result = await client.call_tool("mcp_find_tools", {"query": "echo"})
        assert result.data["total_matches"] == 1
        assert result.data["matches"][0]["server"] == "sample"
        assert result.data["matches"][0]["name"] == "echo"


async def test_host_exec(configured_gateway) -> None:
    async with Client(configured_gateway) as client:
        result = await client.call_tool(
            "host_exec", {"command": "printf gateway-ok", "timeout_seconds": 5}
        )
        assert result.data["ok"] is True
        assert result.data["stdout"] == "gateway-ok"


async def test_scoped_mode_blocks_arbitrary_shell(tmp_path: Path) -> None:
    config = default_config()
    config["access"]["mode"] = "scoped"
    config["access"]["acknowledged_full_access"] = False
    config["access"]["allowed_roots"] = [str(tmp_path)]
    path = tmp_path / "config.json"
    save_config(config, path)
    async with Client(create_gateway(path)) as client:
        result = await client.call_tool(
            "host_exec", {"command": "pwd"}, raise_on_error=False
        )
    assert result.is_error is True
    assert "disabled in scoped mode" in str(result.content)


async def test_host_write_and_replace(configured_gateway, tmp_path: Path) -> None:
    target = tmp_path / "hello.txt"
    async with Client(configured_gateway) as client:
        written = await client.call_tool(
            "host_write_file", {"path": str(target), "content": "hello world"}
        )
        assert written.data["ok"] is True
        replaced = await client.call_tool(
            "host_replace_text",
            {"path": str(target), "old_text": "world", "new_text": "ChatGPT"},
        )
        assert replaced.data["replacements"] == 1
    assert target.read_text() == "hello ChatGPT"


async def test_background_process_lifecycle(configured_gateway) -> None:
    async with Client(configured_gateway) as client:
        started = await client.call_tool(
            "host_process_start", {"command": "printf ready; sleep 30"}
        )
        process_id = started.data["process_id"]
        await __import__("asyncio").sleep(0.1)
        output = await client.call_tool("host_process_read", {"process_id": process_id})
        assert "ready" in output.data["output"]
        stopped = await client.call_tool("host_process_stop", {"process_id": process_id})
        assert stopped.data["ok"] is True


async def test_probe_updates_runtime_status(configured_gateway) -> None:
    async with Client(configured_gateway) as client:
        probe = await client.call_tool("mcp_probe", {"server_name": "sample"})
        assert probe.data["status"] == "connected"
        assert probe.data["tool_count"] == 3
        status = await client.call_tool("gateway_status", {})
        assert status.data["servers"]["sample"]["runtime_status"] == "connected"


def test_dashboard_uses_enabled_disabled_toggle() -> None:
    assert "enabledLabel = server.enabled ? 'Enabled' : 'Disabled'" in DASHBOARD_HTML
    assert ">Probe</button>" not in DASHBOARD_HTML
    assert "Setup required — press here" in DASHBOARD_HTML
    assert "Tunnel runtime API key" in DASHBOARD_HTML
    assert "fetch('/api/setup'" in DASHBOARD_HTML


def test_dashboard_setup_saves_connection_without_exposing_key(
    monkeypatch, tmp_path: Path
) -> None:
    key_store = {"value": None}
    monkeypatch.setattr(gateway_module, "get_runtime_key", lambda: key_store["value"])
    monkeypatch.setattr(
        gateway_module,
        "set_runtime_key",
        lambda value: key_store.__setitem__("value", value),
    )
    path = tmp_path / "config.json"
    save_config(default_config(), path)
    app = create_gateway(path).http_app()

    with TestClient(app) as client:
        before = client.get("/readyz")
        assert before.json()["status"] == "setup_required"
        response = client.post(
            "/api/setup",
            json={
                "name": "My Test Mac",
                "tunnel_id": "tunnel_" + "b" * 32,
                "runtime_key": "secret-runtime-key",
                "access_mode": "full",
                "acknowledge_full_access": True,
            },
        )
        status = client.get("/api/status").json()

    assert response.status_code == 200
    assert response.json()["setup"]["complete"] is True
    assert "secret-runtime-key" not in response.text
    assert status["setup_complete"] is True
    assert status["setup"]["runtime_key_configured"] is True
    assert load_config(path)["access"]["acknowledged_full_access"] is True
    assert key_store["value"] == "secret-runtime-key"


async def test_direct_child_tools_are_namespaced(tmp_path: Path) -> None:
    sample = Path(__file__).parent / "fixtures" / "sample_mcp.py"
    config = default_config()
    config["access"]["acknowledged_full_access"] = True
    config["servers"]["sample"] = {
        "type": "stdio",
        "command": [str(Path(__import__("sys").executable)), str(sample)],
        "enabled": True,
        "expose": "direct",
    }
    path = tmp_path / "config.json"
    save_config(config, path)
    gateway = create_gateway(path)
    async with Client(gateway) as client:
        names = {tool.name for tool in await client.list_tools()}
        assert "sample_echo" in names
        assert "sample_add" in names
