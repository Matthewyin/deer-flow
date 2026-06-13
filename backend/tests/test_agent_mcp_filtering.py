from types import SimpleNamespace

from langchain_core.tools import tool

from deerflow.config.extensions_config import ExtensionsConfig, McpServerConfig
from deerflow.tools.tools import get_available_tools


@tool
def network_ops_query() -> str:
    """Network ops tool."""
    return "network"


@tool
def outbound_message_send() -> str:
    """Outbound message tool."""
    return "outbound"


@tool
def world_cup_status() -> str:
    """World cup tool."""
    return "worldcup"


def _fake_config():
    return SimpleNamespace(
        tools=[],
        models=[],
        tool_search=SimpleNamespace(enabled=False),
        get_model_config=lambda name: None,
    )


def test_get_available_tools_filters_mcp_tools_by_server_prefix(monkeypatch):
    network_ops_query.name = "network-ops_line_query"
    outbound_message_send.name = "outbound-message_wecom_group_bot_send"
    world_cup_status.name = "world-cup_world_cup_status"

    monkeypatch.setattr("deerflow.tools.tools.get_app_config", _fake_config)
    monkeypatch.setattr(
        "deerflow.config.extensions_config.ExtensionsConfig.from_file",
        classmethod(
            lambda cls: ExtensionsConfig(
                mcp_servers={
                    "network-ops": McpServerConfig(enabled=True),
                    "outbound-message": McpServerConfig(enabled=True),
                    "world-cup": McpServerConfig(enabled=True),
                },
                skills={},
            )
        ),
    )
    monkeypatch.setattr(
        "deerflow.mcp.cache.get_cached_mcp_tools",
        lambda: [network_ops_query, outbound_message_send, world_cup_status],
    )

    tools = get_available_tools(
        include_mcp=True,
        subagent_enabled=False,
        mcp_servers=["network-ops", "outbound-message"],
    )

    names = [item.name for item in tools]
    assert "network-ops_line_query" in names
    assert "outbound-message_wecom_group_bot_send" in names
    assert "world-cup_world_cup_status" not in names
