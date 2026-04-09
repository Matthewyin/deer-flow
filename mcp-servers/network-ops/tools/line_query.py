import logging
from typing import Optional, Any
from fastmcp import FastMCP
from db.mysql_client import MySQLClient
from config import get_config

logger = logging.getLogger(__name__)

_client: Optional[MySQLClient] = None


def _get_client() -> MySQLClient:
    global _client
    if _client is None:
        config = get_config()
        _client = MySQLClient(config.mysql)
    return _client


def register(mcp: FastMCP):
    @mcp.tool()
    async def line_info_query(
        local_site: Optional[str] = None,
        remote_name: Optional[str] = None,
        provider: Optional[str] = None,
        purpose: Optional[str] = None,
        bandwidth: Optional[str] = None,
        description: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """查询专线线路信息。支持结构化参数或自然语言描述。"""
        client = _get_client()

        # Check if any structured parameters are provided
        has_structured = any([local_site, remote_name, provider, purpose, bandwidth])

        if description and not has_structured:
            return await client.search_by_llm(description)

        return client.search_lines(
            local_site=local_site,
            remote_name=remote_name,
            provider=provider,
            purpose=purpose,
            bandwidth=bandwidth,
        )
