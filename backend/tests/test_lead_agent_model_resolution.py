"""Tests for lead agent runtime model resolution behavior."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from deerflow.agents.lead_agent import agent as lead_agent_module
from deerflow.config.app_config import AppConfig
from deerflow.config.model_config import ModelConfig
from deerflow.config.sandbox_config import SandboxConfig
from deerflow.config.summarization_config import SummarizationConfig


def _make_app_config(models: list[ModelConfig]) -> AppConfig:
    return AppConfig(
        models=models,
        sandbox=SandboxConfig(use="deerflow.sandbox.local:LocalSandboxProvider"),
    )


def _make_model(name: str, *, supports_thinking: bool) -> ModelConfig:
    return ModelConfig(
        name=name,
        display_name=name,
        description=None,
        use="langchain_openai:ChatOpenAI",
        model=name,
        supports_thinking=supports_thinking,
        supports_vision=False,
    )


def test_resolve_model_name_falls_back_to_default(monkeypatch, caplog):
    app_config = _make_app_config(
        [
            _make_model("default-model", supports_thinking=False),
            _make_model("other-model", supports_thinking=True),
        ]
    )

    monkeypatch.setattr(lead_agent_module, "get_app_config", lambda: app_config)

    with caplog.at_level("WARNING"):
        resolved = lead_agent_module._resolve_model_name("missing-model")

    assert resolved == "default-model"
    assert "fallback to default model 'default-model'" in caplog.text


def test_resolve_model_name_uses_default_when_none(monkeypatch):
    app_config = _make_app_config(
        [
            _make_model("default-model", supports_thinking=False),
            _make_model("other-model", supports_thinking=True),
        ]
    )

    monkeypatch.setattr(lead_agent_module, "get_app_config", lambda: app_config)

    resolved = lead_agent_module._resolve_model_name(None)

    assert resolved == "default-model"


def test_resolve_model_name_raises_when_no_models_configured(monkeypatch):
    app_config = _make_app_config([])

    monkeypatch.setattr(lead_agent_module, "get_app_config", lambda: app_config)

    with pytest.raises(
        ValueError,
        match="No chat models are configured",
    ):
        lead_agent_module._resolve_model_name("missing-model")


def test_runtime_config_reads_context_and_keeps_configurable_override():
    runtime_config = lead_agent_module._get_runtime_config(
        {
            "context": {"agent_name": "worldcup", "model_name": "context-model"},
            "configurable": {"model_name": "config-model"},
        }
    )

    assert runtime_config["agent_name"] == "worldcup"
    assert runtime_config["model_name"] == "config-model"


def test_make_lead_agent_disables_thinking_when_model_does_not_support_it(monkeypatch):
    app_config = _make_app_config([_make_model("safe-model", supports_thinking=False)])

    import deerflow.tools as tools_module

    monkeypatch.setattr(lead_agent_module, "get_app_config", lambda: app_config)
    monkeypatch.setattr(tools_module, "get_available_tools", lambda **kwargs: [])
    monkeypatch.setattr(lead_agent_module, "_build_middlewares", lambda config, model_name, agent_name=None: [])

    captured: dict[str, object] = {}

    def _fake_create_chat_model(*, name, thinking_enabled, reasoning_effort=None):
        captured["name"] = name
        captured["thinking_enabled"] = thinking_enabled
        captured["reasoning_effort"] = reasoning_effort
        return object()

    monkeypatch.setattr(lead_agent_module, "create_chat_model", _fake_create_chat_model)
    monkeypatch.setattr(lead_agent_module, "create_agent", lambda **kwargs: kwargs)

    result = lead_agent_module.make_lead_agent(
        {
            "configurable": {
                "model_name": "safe-model",
                "thinking_enabled": True,
                "is_plan_mode": False,
                "subagent_enabled": False,
            }
        }
    )

    assert captured["name"] == "safe-model"
    assert captured["thinking_enabled"] is False
    assert result["model"] is not None


def test_make_lead_agent_accepts_runtime_context(monkeypatch):
    app_config = _make_app_config([_make_model("safe-model", supports_thinking=False)])

    import deerflow.tools as tools_module

    monkeypatch.setattr(lead_agent_module, "get_app_config", lambda: app_config)
    monkeypatch.setattr(tools_module, "get_available_tools", lambda **kwargs: [])
    monkeypatch.setattr(lead_agent_module, "_build_middlewares", lambda config, model_name, agent_name=None: [])
    captured: dict[str, object] = {}

    def _fake_load_agent_config(agent_name):
        captured["agent_name"] = agent_name
        return type("AgentConfig", (), {"model": None, "tool_groups": None, "skills": []})()

    monkeypatch.setattr(lead_agent_module, "load_agent_config", _fake_load_agent_config)
    monkeypatch.setattr(lead_agent_module, "create_chat_model", lambda **kwargs: object())
    monkeypatch.setattr(lead_agent_module, "create_agent", lambda **kwargs: kwargs)

    result = lead_agent_module.make_lead_agent(
        {
            "context": {
                "agent_name": "worldcup",
                "model_name": "safe-model",
                "thinking_enabled": False,
            }
        }
    )

    assert captured["agent_name"] == "worldcup"
    assert result["model"] is not None


def test_make_lead_agent_disables_subagents_when_custom_agent_restricts_tool_groups(monkeypatch):
    app_config = _make_app_config([_make_model("safe-model", supports_thinking=False)])

    import deerflow.tools as tools_module

    monkeypatch.setattr(lead_agent_module, "get_app_config", lambda: app_config)
    monkeypatch.setattr(lead_agent_module, "_build_middlewares", lambda config, model_name, agent_name=None: [])
    monkeypatch.setattr(lead_agent_module, "load_agent_config", lambda agent_name: type("AgentConfig", (), {"model": None, "tool_groups": [], "skills": []})())
    monkeypatch.setattr(lead_agent_module, "create_chat_model", lambda **kwargs: object())
    monkeypatch.setattr(lead_agent_module, "create_agent", lambda **kwargs: kwargs)

    captured: dict[str, object] = {}

    def _fake_get_available_tools(**kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr(tools_module, "get_available_tools", _fake_get_available_tools)

    lead_agent_module.make_lead_agent(
        {
            "configurable": {
                "agent_name": "worldcup",
                "model_name": "safe-model",
                "thinking_enabled": False,
                "subagent_enabled": True,
            }
        }
    )

    assert captured["groups"] == []
    assert captured["subagent_enabled"] is False


def test_make_lead_agent_passes_custom_agent_mcp_servers(monkeypatch):
    app_config = _make_app_config([_make_model("safe-model", supports_thinking=False)])

    import deerflow.tools as tools_module

    monkeypatch.setattr(lead_agent_module, "get_app_config", lambda: app_config)
    monkeypatch.setattr(lead_agent_module, "_build_middlewares", lambda config, model_name, agent_name=None: [])
    monkeypatch.setattr(
        lead_agent_module,
        "load_agent_config",
        lambda agent_name: type("AgentConfig", (), {"model": None, "tool_groups": None, "mcp_servers": ["network-ops", "outbound-message"], "skills": []})(),
    )
    monkeypatch.setattr(lead_agent_module, "create_chat_model", lambda **kwargs: object())
    monkeypatch.setattr(lead_agent_module, "create_agent", lambda **kwargs: kwargs)

    captured: dict[str, object] = {}

    def _fake_get_available_tools(**kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr(tools_module, "get_available_tools", _fake_get_available_tools)

    lead_agent_module.make_lead_agent(
        {
            "configurable": {
                "agent_name": "dedi",
                "model_name": "safe-model",
                "thinking_enabled": False,
            }
        }
    )

    assert captured["mcp_servers"] == ["network-ops", "outbound-message"]


def test_make_lead_agent_disables_subagents_when_custom_agent_restricts_mcp_servers(monkeypatch):
    app_config = _make_app_config([_make_model("safe-model", supports_thinking=False)])

    import deerflow.tools as tools_module

    monkeypatch.setattr(lead_agent_module, "get_app_config", lambda: app_config)
    monkeypatch.setattr(lead_agent_module, "_build_middlewares", lambda config, model_name, agent_name=None: [])
    monkeypatch.setattr(
        lead_agent_module,
        "load_agent_config",
        lambda agent_name: type("AgentConfig", (), {"model": None, "tool_groups": None, "mcp_servers": ["network-ops"], "skills": []})(),
    )
    monkeypatch.setattr(lead_agent_module, "create_chat_model", lambda **kwargs: object())
    monkeypatch.setattr(lead_agent_module, "create_agent", lambda **kwargs: kwargs)

    captured: dict[str, object] = {}

    def _fake_get_available_tools(**kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr(tools_module, "get_available_tools", _fake_get_available_tools)

    lead_agent_module.make_lead_agent(
        {
            "configurable": {
                "agent_name": "dedi",
                "model_name": "safe-model",
                "thinking_enabled": False,
                "subagent_enabled": True,
            }
        }
    )

    assert captured["mcp_servers"] == ["network-ops"]
    assert captured["subagent_enabled"] is False


def test_build_middlewares_uses_resolved_model_name_for_vision(monkeypatch):
    app_config = _make_app_config(
        [
            _make_model("stale-model", supports_thinking=False),
            ModelConfig(
                name="vision-model",
                display_name="vision-model",
                description=None,
                use="langchain_openai:ChatOpenAI",
                model="vision-model",
                supports_thinking=False,
                supports_vision=True,
            ),
        ]
    )

    monkeypatch.setattr(lead_agent_module, "get_app_config", lambda: app_config)
    monkeypatch.setattr(lead_agent_module, "_create_summarization_middleware", lambda: None)
    monkeypatch.setattr(lead_agent_module, "_create_todo_list_middleware", lambda is_plan_mode: None)

    middlewares = lead_agent_module._build_middlewares({"configurable": {"model_name": "stale-model", "is_plan_mode": False, "subagent_enabled": False}}, model_name="vision-model", custom_middlewares=[MagicMock()])

    assert any(isinstance(m, lead_agent_module.ViewImageMiddleware) for m in middlewares)
    # verify the custom middleware is injected correctly
    assert len(middlewares) > 0 and isinstance(middlewares[-2], MagicMock)


def test_create_summarization_middleware_uses_configured_model_alias(monkeypatch):
    monkeypatch.setattr(
        lead_agent_module,
        "get_summarization_config",
        lambda: SummarizationConfig(enabled=True, model_name="model-masswork"),
    )

    captured: dict[str, object] = {}
    fake_model = object()

    def _fake_create_chat_model(*, name=None, thinking_enabled, reasoning_effort=None):
        captured["name"] = name
        captured["thinking_enabled"] = thinking_enabled
        captured["reasoning_effort"] = reasoning_effort
        return fake_model

    monkeypatch.setattr(lead_agent_module, "create_chat_model", _fake_create_chat_model)
    monkeypatch.setattr(lead_agent_module, "SummarizationMiddleware", lambda **kwargs: kwargs)

    middleware = lead_agent_module._create_summarization_middleware()

    assert captured["name"] == "model-masswork"
    assert captured["thinking_enabled"] is False
    assert middleware["model"] is fake_model
