"""配置片段解析 MCP 工具。"""

from fastmcp import FastMCP

from tools.parse_config import parse_config_text


def register(mcp: FastMCP):
    @mcp.tool()
    def config_audit_parse_snippet(
        config_text: str,
        vendor: str,
        standard_zone: str,
        role: str,
        device_name: str = "",
        model: str = "",
        os_version: str = "",
        site_name: str = "",
        local_area_name: str = "",
    ) -> dict:
        """解析防火墙配置脚本片段，产出结构化事实供 LLM 解释。

        片段不能自动下发，必须结合完整配置和人工复核判断 least privilege、
        default deny 与日志覆盖。
        """
        config = parse_config_text(
            config_text,
            vendor,
            standard_zone,
            role,
            device_name=device_name,
            model=model,
            os_version=os_version,
            site_name=site_name,
            local_area_name=local_area_name,
        )
        return {
            "ok": True,
            "scope": "snippet",
            "uncertainty": (
                "当前输入只是配置脚本片段，缺少完整 security zones、inter-zone policy、"
                "默认拒绝和日志配置上下文，只能作为候选事实，不能直接下发或替代人工复核。"
            ),
            "config": config,
        }
