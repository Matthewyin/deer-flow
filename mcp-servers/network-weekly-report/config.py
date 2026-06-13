"""网络周报 MCP Server 配置。"""

import os
from dataclasses import dataclass


@dataclass
class ServerConfig:
    report_script_path: str
    default_output_filename: str


def get_config() -> ServerConfig:
    return ServerConfig(
        report_script_path=os.getenv(
            "NETWORK_WEEKLY_REPORT_SCRIPT_PATH",
            "/app/skills/custom/network-weekly-report/scripts/gen_report.py",
        ),
        default_output_filename=os.getenv(
            "NETWORK_WEEKLY_REPORT_DEFAULT_OUTPUT_FILENAME",
            "带宽曲线报告.html",
        ),
    )
