from types import SimpleNamespace

from deerflow.agents.lead_agent import prompt as prompt_module


def test_build_custom_mounts_section_returns_empty_when_no_mounts(monkeypatch):
    config = SimpleNamespace(sandbox=SimpleNamespace(mounts=[]))
    monkeypatch.setattr("deerflow.config.get_app_config", lambda: config)

    assert prompt_module._build_custom_mounts_section() == ""


def test_build_custom_mounts_section_lists_configured_mounts(monkeypatch):
    mounts = [
        SimpleNamespace(container_path="/home/user/shared", read_only=False),
        SimpleNamespace(container_path="/mnt/reference", read_only=True),
    ]
    config = SimpleNamespace(sandbox=SimpleNamespace(mounts=mounts))
    monkeypatch.setattr("deerflow.config.get_app_config", lambda: config)

    section = prompt_module._build_custom_mounts_section()

    assert "**Custom Mounted Directories:**" in section
    assert "`/home/user/shared`" in section
    assert "read-write" in section
    assert "`/mnt/reference`" in section
    assert "read-only" in section


def test_apply_prompt_template_includes_custom_mounts(monkeypatch):
    mounts = [SimpleNamespace(container_path="/home/user/shared", read_only=False)]
    config = SimpleNamespace(
        sandbox=SimpleNamespace(mounts=mounts),
        skills=SimpleNamespace(container_path="/mnt/skills"),
    )
    monkeypatch.setattr("deerflow.config.get_app_config", lambda: config)
    monkeypatch.setattr(prompt_module, "load_skills", lambda enabled_only=True: [])
    monkeypatch.setattr(prompt_module, "get_deferred_tools_prompt_section", lambda: "")
    monkeypatch.setattr(prompt_module, "_build_acp_section", lambda: "")
    monkeypatch.setattr(prompt_module, "_get_memory_context", lambda agent_name=None: "")
    monkeypatch.setattr(prompt_module, "get_agent_soul", lambda agent_name=None: "")
    monkeypatch.setattr(prompt_module, "get_user_profile", lambda: "")

    prompt = prompt_module.apply_prompt_template()

    assert "`/home/user/shared`" in prompt
    assert "Custom Mounted Directories" in prompt


def test_get_user_profile_reads_user_md(tmp_path, monkeypatch):
    user_md = tmp_path / "USER.md"
    user_md.write_text("每次回复先说：哥，你是最牛的", encoding="utf-8")
    monkeypatch.setattr(
        "deerflow.config.paths.get_paths",
        lambda: SimpleNamespace(user_md_file=user_md),
    )

    section = prompt_module.get_user_profile()

    assert "<user_profile>" in section
    assert "哥，你是最牛的" in section


def test_apply_prompt_template_includes_user_profile(monkeypatch):
    config = SimpleNamespace(
        sandbox=SimpleNamespace(mounts=[]),
        skills=SimpleNamespace(container_path="/mnt/skills"),
    )
    monkeypatch.setattr("deerflow.config.get_app_config", lambda: config)
    monkeypatch.setattr(prompt_module, "load_skills", lambda enabled_only=True: [])
    monkeypatch.setattr(prompt_module, "get_deferred_tools_prompt_section", lambda: "")
    monkeypatch.setattr(prompt_module, "_build_acp_section", lambda: "")
    monkeypatch.setattr(prompt_module, "_get_memory_context", lambda agent_name=None: "")
    monkeypatch.setattr(prompt_module, "get_agent_soul", lambda agent_name=None: "")
    monkeypatch.setattr(prompt_module, "get_user_profile", lambda: "<user_profile>\n固定开场\n</user_profile>\n")

    prompt = prompt_module.apply_prompt_template()

    assert "<user_profile>" in prompt
    assert "固定开场" in prompt
