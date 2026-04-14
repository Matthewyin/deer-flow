"""MySQL client for line_info queries."""

import json
import logging
from typing import Optional

from config import MySQLConfig

logger = logging.getLogger(__name__)


class MySQLClient:
    """MySQL client for iteams_db.line_info table."""

    def __init__(self, config: MySQLConfig):
        self.config = config
        self._conn = None

    def _connect(self):
        if self._conn and self._conn.is_connected():
            return
        import mysql.connector

        self._conn = mysql.connector.connect(
            host=self.config.host,
            port=self.config.port,
            user=self.config.user,
            password=self.config.password,
            database=self.config.database,
        )
        logger.info(f"Connected to MySQL: {self.config.host}/{self.config.database}")

    def search_lines(
        self,
        local_site: Optional[str] = None,
        remote_name: Optional[str] = None,
        provider: Optional[str] = None,
        purpose: Optional[str] = None,
        bandwidth: Optional[str] = None,
    ) -> list[dict]:
        """Search lines with structured criteria.

        All parameters are optional. Non-None parameters are combined with AND logic.
        String parameters (except provider) use LIKE fuzzy matching.
        """
        self._connect()

        sql = """
            SELECT
                id, local_site, beijing_location, remote_name,
                service_provider, bandwidth, purpose,
                local_line_number, long_distance_number,
                business_type, line_state,
                created_at, updated_at
            FROM line_info
            WHERE 1=1
        """
        params = []

        if local_site:
            sql += " AND local_site LIKE %s"
            params.append(f"%{local_site}%")
        if remote_name:
            sql += " AND remote_name LIKE %s"
            params.append(f"%{remote_name}%")
        if provider:
            sql += " AND service_provider = %s"
            params.append(provider)
        if purpose:
            sql += " AND purpose LIKE %s"
            params.append(f"%{purpose}%")
        if bandwidth:
            sql += " AND bandwidth = %s"
            params.append(bandwidth)

        cursor = self._conn.cursor(dictionary=True)
        cursor.execute(sql, params)
        results = cursor.fetchall()
        cursor.close()
        return results

    async def search_by_llm(self, description: str, llm_config=None) -> list[dict]:
        """Search lines using LLM to extract parameters from natural language."""
        from langchain_openai import ChatOpenAI

        if llm_config is None:
            from config import get_config

            llm_config = get_config().llm

        prompt = f"""Analyze this network line query and extract search parameters.

Query: "{description}"

Available search fields:
- local_site: Local data center (e.g., "亦庄数据中心", "西五环数据中心")
- remote_name: Remote destination (e.g., "山东", "西藏", "北京XXX中心")
- provider: Telecom provider (电信, 联通, 移动)
- purpose: Line purpose (数据端, 管理端, 北京单场)
- bandwidth: Bandwidth like "10M", "20M"

Return ONLY a JSON object with the extracted parameters. Use null for unknown fields.

Examples:
- "查询山东数据端" -> {{"remote_name": "山东", "purpose": "数据端"}}
- "亦庄到西藏电信线路" -> {{"local_site": "亦庄", "remote_name": "西藏", "provider": "电信"}}
- "西五环联通10M管理端" -> {{"local_site": "西五环", "provider": "联通", "bandwidth": "10M", "purpose": "管理端"}}

Response:"""

        if not llm_config.api_key:
            logger.warning("No LLM API key configured, falling back to keyword search")
            return self.search_lines(
                remote_name=f"%{description}%", purpose=f"%{description}%"
            )

        kwargs = dict(model=llm_config.model, temperature=0, api_key=llm_config.api_key)
        if llm_config.base_url:
            kwargs["base_url"] = llm_config.base_url

        model = ChatOpenAI(**kwargs)
        response = await model.ainvoke([("human", prompt)])

        content = response.content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        params = json.loads(content)
        search_params = {k: v for k, v in params.items() if v is not None}

        logger.info(f"LLM extracted from '{description}': {search_params}")
        return self.search_lines(**search_params)

    def get_line_by_id(self, line_id: int) -> Optional[dict]:
        """Get line by ID."""
        self._connect()
        cursor = self._conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM line_info WHERE id = %s", (line_id,))
        result = cursor.fetchone()
        cursor.close()
        return result

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None
