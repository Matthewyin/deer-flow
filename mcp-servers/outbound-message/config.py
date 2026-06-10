"""外发消息 MCP Server 配置。"""

import json
import os
import re
from dataclasses import dataclass


def _parse_webhook_urls(value: str) -> list[str]:
    value = value.strip()
    if not value:
        return []

    if value.startswith("["):
        parsed = json.loads(value)
        if not isinstance(parsed, list):
            raise ValueError("WECOM_GROUP_BOT_WEBHOOK_URLS must be a JSON array or separator-delimited string")
        return [str(item).strip() for item in parsed if str(item).strip()]

    return [item.strip() for item in re.split(r"[\n,;，；]+", value) if item.strip()]


@dataclass
class WeComGroupBotConfig:
    webhook_urls: list[str]
    timeout_seconds: int = 10


@dataclass
class ServerConfig:
    wecom_group_bot: WeComGroupBotConfig


def get_config() -> ServerConfig:
    webhook_urls = _parse_webhook_urls(os.getenv("WECOM_GROUP_BOT_WEBHOOK_URLS", ""))
    timeout_seconds = int(os.getenv("WECOM_GROUP_BOT_TIMEOUT_SECONDS", "10"))
    return ServerConfig(
        wecom_group_bot=WeComGroupBotConfig(
            webhook_urls=webhook_urls,
            timeout_seconds=timeout_seconds,
        )
    )
