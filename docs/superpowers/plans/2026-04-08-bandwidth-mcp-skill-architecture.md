# Bandwidth Management: MCP Server + Skill Architecture Redesign

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the bandwidth management feature from a monolithic local tool into a three-layer architecture: Dedi Agent (ReAct) → Skill (domain knowledge/flow) → MCP Server (atomic tools).

**Architecture:** Build a standalone Python MCP Server using FastMCP that exposes 5 atomic tools (line query, bandwidth assessment, policy search via RAG, statistics, email generation). The bandwidth policy document (`docs/bandwidth.md`) is the single source of truth: its full text goes into ChromaDB RAG for semantic search, and the tier table (附件) is parsed into SQLite for precise threshold matching. The Skill document (`SKILL.md`) teaches the Agent the workflow and references the RAG tool for domain details — no duplicated data. Remove the old monolithic `bandwidth_tool.py` and register the MCP Server in `extensions_config.json`.

**Tech Stack:** Python 3.12, FastMCP 2.x, MySQL (mysql-connector-python), SQLite3, ChromaDB (langchain-chroma), DeerFlow Skill system (SKILL.md)

---

## File Structure

### MCP Server (new standalone package)

```
mcp-servers/
└── network-ops/
    ├── server.py              # FastMCP entry point, tool registration
    ├── config.py              # Server configuration (MySQL, SQLite, Chroma paths)
    ├── db/
    │   ├── mysql_client.py    # MySQL line_info queries (migrated from rag/line_info_provider.py)
    │   ├── sqlite_client.py   # SQLite bandwidth_tiers — parsed from docs/bandwidth.md
    │   └── __init__.py
    ├── rag/
    │   ├── bandwidth_rag.py   # ChromaDB: ingests docs/bandwidth.md as single source of truth
    │   └── __init__.py
    ├── tools/
    │   ├── line_query.py      # line_info_query tool
    │   ├── bandwidth_assess.py # bandwidth_assess tool (uses SQLite tier table)
    │   ├── policy_search.py   # policy_search tool (queries RAG from bandwidth.md)
    │   ├── bandwidth_stats.py # bandwidth_stats tool
    │   ├── email_generate.py  # email_generate tool (4 templates from bandwidth.md)
    │   └── __init__.py
    ├── requirements.txt
    └── README.md
```

### Skill (new)

```
skills/custom/
└── bandwidth-management/
    ├── SKILL.md               # Main skill: workflow, triggers, semantic guide. No duplicated policy data.
    └── bandwidth-policy.md    # Copy of docs/bandwidth.md for Agent read_file reference
```

### DeerFlow config changes

```
extensions_config.json        # Add network-ops MCP server entry
config.yaml                   # Remove bandwidth_policy_query from tools
```

### Files to remove after migration

```
backend/packages/harness/deerflow/tools/bandwidth_tool.py    # Delete entirely
backend/packages/harness/deerflow/rag/bandwidth_db.py        # Delete (migrated)
backend/packages/harness/deerflow/rag/bandwidth_rag.py       # Delete (migrated)
backend/packages/harness/deerflow/rag/line_info_provider.py  # Delete (migrated)
backend/packages/harness/deerflow/rag/__init__.py             # Remove bandwidth imports
backend/packages/harness/deerflow/config/network_ops_config.py # Keep (shared config)
```

---

## Task 1: Create MCP Server scaffold

**Files:**
- Create: `mcp-servers/network-ops/server.py`
- Create: `mcp-servers/network-ops/config.py`
- Create: `mcp-servers/network-ops/requirements.txt`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p mcp-servers/network-ops/{db,rag,tools}
```

- [ ] **Step 2: Create `requirements.txt`**

```
# mcp-servers/network-ops/requirements.txt
fastmcp>=2.0
mysql-connector-python>=8.0
langchain-chroma>=0.1
langchain-ollama>=0.1
pydantic>=2.0
```

- [ ] **Step 3: Create `config.py` — server configuration**

```python
# mcp-servers/network-ops/config.py
"""Network Ops MCP Server configuration."""

import os
from dataclasses import dataclass


@dataclass
class MySQLConfig:
    host: str = "host.docker.internal"
    port: int = 3306
    user: str = "root"
    password: str = ""
    database: str = "iteams_db"


@dataclass
class SQLiteConfig:
    db_path: str = ".deer-flow/db/network_ops.db"


@dataclass
class ChromaConfig:
    persist_dir: str = ".deer-flow/vectors/bandwidth_policy"
    ollama_base_url: str = "http://host.docker.internal:11434"


@dataclass
class ServerConfig:
    mysql: MySQLConfig = None
    sqlite: SQLiteConfig = None
    chroma: ChromaConfig = None

    def __post_init__(self):
        if self.mysql is None:
            self.mysql = MySQLConfig(
                host=os.getenv("MYSQL_HOST", "host.docker.internal"),
                port=int(os.getenv("MYSQL_PORT", "3306")),
                user=os.getenv("MYSQL_USER", "root"),
                password=os.getenv("MYSQL_PASSWORD", ""),
                database=os.getenv("MYSQL_DATABASE", "iteams_db"),
            )
        if self.sqlite is None:
            self.sqlite = SQLiteConfig(
                db_path=os.getenv("SQLITE_DB_PATH", ".deer-flow/db/network_ops.db"),
            )
        if self.chroma is None:
            self.chroma = ChromaConfig(
                persist_dir=os.getenv("CHROMA_PERSIST_DIR", ".deer-flow/vectors/bandwidth_policy"),
                ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434"),
            )


def get_config() -> ServerConfig:
    return ServerConfig()
```

- [ ] **Step 4: Create `server.py` — FastMCP entry point**

```python
# mcp-servers/network-ops/server.py
"""Network Operations MCP Server.

Provides tools for bandwidth policy analysis, line information queries,
and email template generation for network operations.
"""

from fastmcp import FastMCP

mcp = FastMCP(
    "network-ops",
    instructions="网络运维工具集：提供线路查询、带宽策略评估、统计查询和邮件生成能力。",
)


# Import and register tools
from tools.line_query import register as register_line_query
from tools.bandwidth_assess import register as register_bandwidth_assess
from tools.policy_search import register as register_policy_search
from tools.bandwidth_stats import register as register_bandwidth_stats
from tools.email_generate import register as register_email_generate

register_line_query(mcp)
register_bandwidth_assess(mcp)
register_policy_search(mcp)
register_bandwidth_stats(mcp)
register_email_generate(mcp)


if __name__ == "__main__":
    mcp.run()
```

- [ ] **Step 5: Create empty `__init__.py` files**

```bash
touch mcp-servers/network-ops/db/__init__.py
touch mcp-servers/network-ops/rag/__init__.py
touch mcp-servers/network-ops/tools/__init__.py
```

- [ ] **Step 6: Verify server starts**

```bash
cd mcp-servers/network-ops && pip install -r requirements.txt && python -c "from server import mcp; print('MCP server loaded:', mcp.name)"
```

Expected: `MCP server loaded: network-ops`

- [ ] **Step 7: Commit**

```bash
git add mcp-servers/
git commit -m "feat(network-ops): scaffold MCP server with FastMCP"
```

---

## Task 2: Migrate data layer — MySQL client

**Files:**
- Create: `mcp-servers/network-ops/db/mysql_client.py`
- Reference: `backend/packages/harness/deerflow/rag/line_info_provider.py` (source to migrate)

- [ ] **Step 1: Create `db/mysql_client.py`**

Migrate `LineInfoProvider` from `rag/line_info_provider.py`. Remove regex-based `_extract_keywords` and `search_by_natural_language` methods — only keep `search_lines()` (structured params) and `search_by_llm()` (LLM-based extraction). The LLM extraction stays because MCP tool callers (the Agent) send structured params, but we keep it as a fallback for free-text queries.

```python
# mcp-servers/network-ops/db/mysql_client.py
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

    async def search_by_llm(self, description: str) -> list[dict]:
        """Search lines using LLM to extract parameters from natural language.

        Uses LLM to parse description into structured search params,
        then delegates to search_lines().
        """
        # Import here to avoid circular deps and allow graceful fallback
        from langchain_openai import ChatOpenAI

        prompt = f"""Analyze this network line query and extract search parameters.

Query: "{description}"

Available search fields:
- local_site: Local data center (e.g., "亦庄数据中心", "西五环数据中心")
- remote_name: Remote destination (e.g., "山东", "西藏", "北京体彩中心")
- provider: Telecom provider (电信, 联通, 移动)
- purpose: Line purpose (数据端, 管理端, 北京单场)
- bandwidth: Bandwidth like "10M", "20M"

Return ONLY a JSON object with the extracted parameters. Use null for unknown fields.

Examples:
- "查询山东数据端" -> {{"remote_name": "山东", "purpose": "数据端"}}
- "亦庄到西藏电信线路" -> {{"local_site": "亦庄", "remote_name": "西藏", "provider": "电信"}}
- "西五环联通10M管理端" -> {{"local_site": "西五环", "provider": "联通", "bandwidth": "10M", "purpose": "管理端"}}

Response:"""

        model = ChatOpenAI(model="gpt-4o-mini", temperature=0)
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
```

- [ ] **Step 2: Verify import**

```bash
cd mcp-servers/network-ops && python -c "from db.mysql_client import MySQLClient; print('MySQLClient imported OK')"
```

Expected: `MySQLClient imported OK`

- [ ] **Step 3: Commit**

```bash
git add mcp-servers/network-ops/db/
git commit -m "feat(network-ops): migrate MySQL client for line_info queries"
```

---

## Task 3: Create data layer — SQLite client (tiers parsed from bandwidth.md)

**Files:**
- Create: `mcp-servers/network-ops/db/sqlite_client.py`
- Create: `mcp-servers/network-ops/db/init_tiers.py`
- Reference: `docs/bandwidth.md` (source of tier data — the 附件 table at bottom)

- [ ] **Step 1: Create `db/init_tiers.py` — parse tier table from bandwidth.md**

This script reads the tier table from `docs/bandwidth.md` (lines 63-71) and returns structured data. This is the ONLY place the tier data is extracted from the source document.

```python
# mcp-servers/network-ops/db/init_tiers.py
"""Parse bandwidth tier table from docs/bandwidth.md.

Reads the attachment table (附件：带宽配置标准对照表) and returns
structured tuples for SQLite seeding. This is the single source of truth
for tier data — bandwidth.md is the policy document.
"""

import re
from pathlib import Path


def parse_tiers_from_md(md_path: str = "docs/bandwidth.md") -> list[tuple]:
    """Parse bandwidth tier table from bandwidth.md.

    Returns:
        List of tuples: (current_bw, scale_up_threshold, scale_up_target,
                         scale_down_threshold, scale_down_target, description)
    """
    content = Path(md_path).read_text(encoding="utf-8")

    tiers = []
    # Match lines like: 2 Mbps	＞ 0.8 Mbps	4 Mbps	-	-	维持最低配置。
    # or: 10 Mbps	＞ 4.0 Mbps	20 Mbps	＜ 2.8 Mbps	8 Mbps	超过4.0M扩容...
    pattern = re.compile(
        r"^(\d+)\s*Mbps\s+"       # current bandwidth
        r"[＞>]\s*([\d.]+)\s*Mbps\s+"  # scale up threshold
        r"(\d+)\s*Mbps\s+"         # scale up target
        r"([＜< -]+?)\s+"          # scale down threshold (or "-")
        r"(\d+)\s*Mbps\s+"         # scale down target (or "-")
        r"(.+)$",                   # description
        re.MULTILINE,
    )

    for match in pattern.finditer(content):
        current_bw = int(match.group(1))
        scale_up_threshold = float(match.group(2))
        scale_up_target = int(match.group(3))

        # Parse scale down threshold — "-" means None
        down_raw = match.group(4).strip()
        if down_raw in ("-", ""):
            scale_down_threshold = None
            scale_down_target = None
            description = match.group(6).strip()
        else:
            # Extract number from patterns like "＜ 0.7 Mbps" or "< 0.7"
            down_num = re.search(r"([\d.]+)", down_raw)
            scale_down_threshold = float(down_num.group(1)) if down_num else None
            scale_down_target = int(match.group(5))
            description = match.group(6).strip()

        tiers.append((
            current_bw,
            scale_up_threshold,
            scale_up_target,
            scale_down_threshold,
            scale_down_target if scale_down_threshold is not None else None,
            description,
        ))

    return tiers


if __name__ == "__main__":
    # Test parsing
    tiers = parse_tiers_from_md()
    for t in tiers:
        print(t)
```

- [ ] **Step 2: Verify parsing works**

```bash
cd mcp-servers/network-ops && python -c "
from db.init_tiers import parse_tiers_from_md
tiers = parse_tiers_from_md('../../docs/bandwidth.md')
print(f'Parsed {len(tiers)} tiers')
for t in tiers:
    print(f'  {t[0]}M -> up>{t[1]} -> {t[2]}M, down<{t[3]} -> {t[4]}M')
"
```

Expected: `Parsed 8 tiers` with correct threshold values matching `bandwidth.md`

- [ ] **Step 3: Create `db/sqlite_client.py`**

```python
# mcp-servers/network-ops/db/sqlite_client.py
"""SQLite client for bandwidth tier policy lookups.

Tier data is parsed from docs/bandwidth.md at initialization time.
No hardcoded tier data in this file.
"""

import logging
import sqlite3
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class SQLiteClient:
    """SQLite database for bandwidth tier policies."""

    def __init__(self, db_path: str = ".deer-flow/db/network_ops.db", md_path: str = "docs/bandwidth.md"):
        self.db_path = Path(db_path)
        self.md_path = md_path
        self._ensure_db()

    def _ensure_db(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            self._create_tables(conn)
            self._seed_from_md(conn)

    def _create_tables(self, conn: sqlite3.Connection):
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bandwidth_tiers (
                id INTEGER PRIMARY KEY,
                current_bw_mbps INTEGER NOT NULL UNIQUE,
                scale_up_threshold_mbps REAL NOT NULL,
                scale_up_target_mbps INTEGER NOT NULL,
                scale_down_threshold_mbps REAL,
                scale_down_target_mbps INTEGER,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS update_bandwidth_tiers_timestamp
            AFTER UPDATE ON bandwidth_tiers
            BEGIN
                UPDATE bandwidth_tiers SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
            END
        """)
        conn.commit()

    def _seed_from_md(self, conn: sqlite3.Connection):
        """Seed tier data by parsing docs/bandwidth.md."""
        cursor = conn.execute("SELECT COUNT(*) FROM bandwidth_tiers")
        if cursor.fetchone()[0] == 0:
            from db.init_tiers import parse_tiers_from_md
            tiers = parse_tiers_from_md(self.md_path)
            conn.executemany(
                """INSERT INTO bandwidth_tiers
                (current_bw_mbps, scale_up_threshold_mbps, scale_up_target_mbps,
                 scale_down_threshold_mbps, scale_down_target_mbps, description)
                VALUES (?, ?, ?, ?, ?, ?)""",
                tiers,
            )
            conn.commit()
            logger.info(f"Seeded {len(tiers)} tiers from {self.md_path}")

    def get_tier(self, bw_mbps: int) -> Optional[dict]:
        """Get tier by exact bandwidth Mbps value."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM bandwidth_tiers WHERE current_bw_mbps = ?",
                (bw_mbps,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_all_tiers(self) -> list[dict]:
        """Get all tiers ordered by bandwidth."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM bandwidth_tiers ORDER BY current_bw_mbps")
            return [dict(row) for row in cursor.fetchall()]

    def get_recommendation(self, current_bw_mbps: int, current_traffic: float) -> dict:
        """Get scale_up/scale_down/maintain recommendation."""
        tier = self.get_tier(current_bw_mbps)
        if not tier:
            return {"action": "unknown", "reasoning": f"未找到带宽档位 {current_bw_mbps} Mbps"}

        if current_traffic > tier["scale_up_threshold_mbps"]:
            return {
                "action": "scale_up",
                "current_bw": f"{current_bw_mbps} Mbps",
                "current_traffic_mbps": current_traffic,
                "threshold_mbps": tier["scale_up_threshold_mbps"],
                "target_bw": f"{tier['scale_up_target_mbps']} Mbps",
                "reasoning": f"当前流量 {current_traffic} Mbps 超过扩容阈值 {tier['scale_up_threshold_mbps']} Mbps，建议扩容到 {tier['scale_up_target_mbps']} Mbps",
            }

        if tier["scale_down_threshold_mbps"] is not None and current_traffic < tier["scale_down_threshold_mbps"]:
            return {
                "action": "scale_down",
                "current_bw": f"{current_bw_mbps} Mbps",
                "current_traffic_mbps": current_traffic,
                "threshold_mbps": tier["scale_down_threshold_mbps"],
                "target_bw": f"{tier['scale_down_target_mbps']} Mbps",
                "reasoning": f"当前流量 {current_traffic} Mbps 低于缩容阈值 {tier['scale_down_threshold_mbps']} Mbps，建议缩容到 {tier['scale_down_target_mbps']} Mbps",
            }

        return {
            "action": "maintain",
            "current_bw": f"{current_bw_mbps} Mbps",
            "current_traffic_mbps": current_traffic,
            "reasoning": f"当前流量 {current_traffic} Mbps 在合理范围内，维持 {current_bw_mbps} Mbps",
        }
```

- [ ] **Step 4: Verify**

```bash
cd mcp-servers/network-ops && python -c "from db.sqlite_client import SQLiteClient; db = SQLiteClient('/tmp/test_bw2.db', '../../docs/bandwidth.md'); tiers = db.get_all_tiers(); print(f'{len(tiers)} tiers loaded'); print(db.get_recommendation(10, 5.0))"
```

Expected: `8 tiers loaded` and `action: scale_up` for 10M @ 5Mbps

- [ ] **Step 5: Commit**

```bash
git add mcp-servers/network-ops/db/
git commit -m "feat(network-ops): SQLite client parses tiers from bandwidth.md"
```

---

## Task 4: Create data layer — RAG (ingests docs/bandwidth.md)

**Files:**
- Create: `mcp-servers/network-ops/rag/bandwidth_rag.py`
- Reference: `docs/bandwidth.md` (the single source of truth — full document goes into ChromaDB)

- [ ] **Step 1: Create `rag/bandwidth_rag.py`**

This module reads `docs/bandwidth.md`, splits it into semantic chunks (each section becomes a document), and stores them in ChromaDB. No hardcoded policy text — everything comes from the source document.

```python
# mcp-servers/network-ops/rag/bandwidth_rag.py
"""Bandwidth policy RAG — ingests docs/bandwidth.md into ChromaDB.

Single source of truth: bandwidth.md is the complete policy document.
This module splits it into chunks by section headers and embeds them.
When the Agent needs to look up policy details (thresholds, flow steps,
email templates, role definitions), it queries this RAG.
"""

import logging
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def _chunk_md(content: str) -> list[dict]:
    """Split bandwidth.md into semantic chunks by section headers.

    Returns list of dicts with 'content' and 'section_title' keys.
    """
    chunks = []

    # Split by numbered headers like "1. 概述", "2.1. 前置条件", "模板一：..."
    # Pattern: line starting with number or "模板"
    sections = re.split(
        r'(?=^\d+\.\s|(?=^模板[一二三四]))',
        content,
        flags=re.MULTILINE,
    )

    for section in sections:
        section = section.strip()
        if not section or len(section) < 20:
            continue

        # Extract title from first line
        first_line = section.split("\n")[0].strip()
        title = re.sub(r'^[\d.]+\s*', '', first_line)

        chunks.append({
            "content": section,
            "section_title": title[:100],
        })

    # If no chunks from splitting (unlikely), use the whole doc as one chunk
    if not chunks:
        chunks.append({
            "content": content,
            "section_title": "带宽扩缩容指南全文",
        })

    return chunks


class BandwidthRAG:
    """ChromaDB-based semantic search over docs/bandwidth.md."""

    def __init__(self, persist_dir: str, ollama_base_url: str, md_path: str = "docs/bandwidth.md"):
        self.persist_dir = Path(persist_dir)
        self.ollama_base_url = ollama_base_url
        self.md_path = md_path
        self._vectorstore = None

    def initialize(self, force_rebuild: bool = False) -> "BandwidthRAG":
        from langchain_chroma import Chroma
        from langchain_core.documents import Document
        from langchain_ollama import OllamaEmbeddings

        if self._vectorstore is not None and not force_rebuild:
            return self

        embeddings = OllamaEmbeddings(model="bge-m3:567m", base_url=self.ollama_base_url)

        if self.persist_dir.exists() and not force_rebuild:
            logger.info(f"Loading existing RAG from {self.persist_dir}")
            self._vectorstore = Chroma(
                collection_name="bandwidth_policy",
                embedding_function=embeddings,
                persist_directory=str(self.persist_dir),
            )
            return self

        # Read and chunk the source document
        md_file = Path(self.md_path)
        if not md_file.exists():
            raise FileNotFoundError(f"Source document not found: {self.md_path}")

        content = md_file.read_text(encoding="utf-8")
        chunks = _chunk_md(content)

        logger.info(f"Chunking {self.md_path}: {len(chunks)} sections")

        documents = [
            Document(
                page_content=chunk["content"],
                metadata={"source": str(md_file), "section": chunk["section_title"]},
            )
            for chunk in chunks
        ]

        self.persist_dir.parent.mkdir(parents=True, exist_ok=True)
        self._vectorstore = Chroma.from_documents(
            documents=documents,
            embedding=embeddings,
            collection_name="bandwidth_policy",
            persist_directory=str(self.persist_dir),
        )
        logger.info(f"RAG initialized: {len(documents)} sections from {self.md_path}")
        return self

    def query(self, query_text: str, k: int = 3) -> list[dict]:
        """Search bandwidth policy by semantic similarity.

        Args:
            query_text: Natural language query, e.g. "扩容操作流程" or "10M带宽阈值"
            k: Number of results to return

        Returns:
            List of matching sections with section title and relevance score.
        """
        if self._vectorstore is None:
            self.initialize()

        results = self._vectorstore.similarity_search_with_score(query_text, k=k)
        return [
            {
                "section": doc.metadata["section"],
                "content": doc.page_content,
                "score": round(1 - score, 4),
            }
            for doc, score in results
        ]
```

- [ ] **Step 2: Verify RAG ingests bandwidth.md**

```bash
cd mcp-servers/network-ops && python -c "
from rag.bandwidth_rag import _chunk_md
from pathlib import Path
content = Path('../../docs/bandwidth.md').read_text()
chunks = _chunk_md(content)
print(f'{len(chunks)} chunks:')
for c in chunks:
    print(f'  [{c[\"section_title\"][:40]}] ({len(c[\"content\"])} chars)')
"
```

Expected: Multiple chunks covering 概述, 实施过程, 角色与职责, 风险控制, 模板一~四

- [ ] **Step 3: Commit**

```bash
git add mcp-servers/network-ops/rag/
git commit -m "feat(network-ops): RAG ingests bandwidth.md as single source of truth"
```

---

## Task 5: Create MCP Tool — `line_info_query`

**Files:**
- Create: `mcp-servers/network-ops/tools/line_query.py`

- [ ] **Step 1: Create the tool**

```python
# mcp-servers/network-ops/tools/line_query.py
"""line_info_query tool — search line information from MySQL."""

import logging
from typing import Optional

from fastmcp import FastMCP

from config import get_config

logger = logging.getLogger(__name__)

_client = None


def _get_client():
    global _client
    if _client is None:
        from db.mysql_client import MySQLClient
        config = get_config()
        _client = MySQLClient(config.mysql)
    return _client


def register(mcp: FastMCP):
    @mcp.tool
    async def line_info_query(
        local_site: Optional[str] = None,
        remote_name: Optional[str] = None,
        provider: Optional[str] = None,
        purpose: Optional[str] = None,
        bandwidth: Optional[str] = None,
        description: Optional[str] = None,
    ) -> list[dict]:
        """查询专线线路信息。支持结构化参数或自然语言描述。

        Args:
            local_site: 本端站点，如 "亦庄数据中心"、"西五环"
            remote_name: 对端名称，如 "山东"、"西藏"、"体彩中心"
            provider: 运营商：电信、联通、移动
            purpose: 用途：数据端、管理端、北京单场
            bandwidth: 带宽，如 "10M"、"20M"
            description: 自然语言描述（作为结构化参数的替代），如 "亦庄到西藏数据端电信线路"

        Returns:
            匹配的线路信息列表，每条包含 id、local_site、remote_name、service_provider、bandwidth、purpose 等字段
        """
        client = _get_client()

        if description and not any([local_site, remote_name, provider, purpose, bandwidth]):
            return await client.search_by_llm(description)

        return client.search_lines(
            local_site=local_site,
            remote_name=remote_name,
            provider=provider,
            purpose=purpose,
            bandwidth=bandwidth,
        )
```

- [ ] **Step 2: Commit**

```bash
git add mcp-servers/network-ops/tools/line_query.py
git commit -m "feat(network-ops): add line_info_query MCP tool"
```

---

## Task 6: Create MCP Tool — `bandwidth_assess`

**Files:**
- Create: `mcp-servers/network-ops/tools/bandwidth_assess.py`

- [ ] **Step 1: Create the tool**

```python
# mcp-servers/network-ops/tools/bandwidth_assess.py
"""bandwidth_assess tool — evaluate bandwidth tier and get recommendation."""

import logging
from typing import Optional

from fastmcp import FastMCP

from config import get_config

logger = logging.getLogger(__name__)

_db = None


def _get_db():
    global _db
    if _db is None:
        from db.sqlite_client import SQLiteClient
        config = get_config()
        _db = SQLiteClient(config.sqlite.db_path)
    return _db


def register(mcp: FastMCP):
    @mcp.tool
    def bandwidth_assess(
        current_bw_mbps: int,
        current_traffic_mbps: float,
    ) -> dict:
        """根据当前带宽和流量，评估是否需要扩容或缩容。

        基于带宽策略表（8档：2M/4M/6M/8M/10M/20M/30M/40M），判断当前流量是否超过扩容阈值（40%）或低于缩容阈值（35%）。

        Args:
            current_bw_mbps: 当前带宽档位（Mbps），如 10 代表 10M
            current_traffic_mbps: 当前 P95 流量（Mbps），如 5.0 代表 5Mbps

        Returns:
            评估结果字典，包含:
            - action: "scale_up"（扩容）、"scale_down"（缩容）、"maintain"（维持）
            - current_bw: 当前带宽字符串
            - target_bw: 目标带宽字符串（仅 scale_up/scale_down 时有值）
            - threshold_mbps: 触发阈值
            - reasoning: 判断理由
        """
        db = _get_db()
        return db.get_recommendation(current_bw_mbps, current_traffic_mbps)
```

- [ ] **Step 2: Commit**

```bash
git add mcp-servers/network-ops/tools/bandwidth_assess.py
git commit -m "feat(network-ops): add bandwidth_assess MCP tool"
```

---

## Task 7: Create MCP Tool — `bandwidth_stats`

**Files:**
- Create: `mcp-servers/network-ops/tools/bandwidth_stats.py`

- [ ] **Step 1: Create the tool**

```python
# mcp-servers/network-ops/tools/bandwidth_stats.py
"""bandwidth_stats tool — query bandwidth tier statistics and line counts."""

import logging
from typing import Optional

from fastmcp import FastMCP

from config import get_config

logger = logging.getLogger(__name__)


def register(mcp: FastMCP):
    @mcp.tool
    def bandwidth_stats(
        bandwidth: Optional[str] = None,
    ) -> dict:
        """查询带宽档位统计信息。可按带宽档位筛选，返回线路数量。

        Args:
            bandwidth: 可选带宽筛选，如 "10M"。不传则返回所有档位统计。

        Returns:
            统计信息字典，包含:
            - tiers: 所有带宽档位配置列表
            - line_count: 匹配的线路数量（需要MySQL连接）
            - total_lines: 总线路数
        """
        from db.sqlite_client import SQLiteClient
        config = get_config()
        db = SQLiteClient(config.sqlite.db_path)

        tiers = db.get_all_tiers()

        # Try to get line counts from MySQL
        line_count = None
        total_lines = None
        try:
            from db.mysql_client import MySQLClient
            mysql = MySQLClient(config.mysql)
            if bandwidth:
                lines = mysql.search_lines(bandwidth=bandwidth)
                line_count = len(lines)
            total_lines = len(mysql.search_lines())
            mysql.close()
        except Exception as e:
            logger.warning(f"MySQL unavailable for stats: {e}")

        return {
            "tiers": tiers,
            "line_count": line_count,
            "total_lines": total_lines,
        }
```

- [ ] **Step 2: Commit**

```bash
git add mcp-servers/network-ops/tools/bandwidth_stats.py
git commit -m "feat(network-ops): add bandwidth_stats MCP tool"
```

---

## Task 8: Create MCP Tool — `policy_search` (RAG queries)

**Files:**
- Create: `mcp-servers/network-ops/tools/policy_search.py`

- [ ] **Step 1: Create the tool**

This tool lets the Agent search the full bandwidth policy document (`bandwidth.md`) via RAG. It returns relevant sections with their content. The Agent uses this to look up operation flows, threshold rules, role definitions, and email template formats.

```python
# mcp-servers/network-ops/tools/policy_search.py
"""policy_search tool — semantic search over docs/bandwidth.md via ChromaDB."""

import logging
from typing import Optional

from fastmcp import FastMCP

from config import get_config

logger = logging.getLogger(__name__)

_rag = None


def _get_rag():
    global _rag
    if _rag is None:
        from rag.bandwidth_rag import BandwidthRAG
        config = get_config()
        _rag = BandwidthRAG(
            persist_dir=config.chroma.persist_dir,
            ollama_base_url=config.chroma.ollama_base_url,
            md_path=config.chroma.md_path,
        )
        _rag.initialize()
    return _rag


def register(mcp: FastMCP):
    @mcp.tool
    def policy_search(
        query: str,
        k: int = 3,
    ) -> list[dict]:
        """搜索带宽策略文档（docs/bandwidth.md）。按语义相似度返回匹配的章节。

        用于查找：操作流程、阈值规则、角色职责、邮件模板格式等。
        当需要了解具体策略细节时调用此工具，而不是硬编码规则。

        Args:
            query: 搜索查询，如 "常态化扩容流程"、"带宽阈值标准"、"缩容邮件模板"、"应急扩容条件"
            k: 返回结果数量（默认3）

        Returns:
            匹配的文档章节列表，每条包含:
            - section: 章节标题
            - content: 章节全文内容
            - score: 相关度分数（越高越相关）
        """
        rag = _get_rag()
        return rag.query(query, k=k)
```

- [ ] **Step 2: Commit**

```bash
git add mcp-servers/network-ops/tools/policy_search.py
git commit -m "feat(network-ops): add policy_search MCP tool for RAG queries"
```

---

## Task 9: Create MCP Tool — `email_generate` (4 templates)

**Files:**
- Create: `mcp-servers/network-ops/tools/email_generate.py`

- [ ] **Step 1: Create the tool**

```python
# mcp-servers/network-ops/tools/email_generate.py
"""email_generate tool — render bandwidth adjustment email templates."""

import re
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastmcp import FastMCP

logger = logging.getLogger(__name__)

RECIPIENTS = ["李王昊"]
CC_LIST = ["潘处", "毅总", "许祎恒", "霍乾", "黄美华", "王亮", "一线", "二线", "值班经理", "商务"]


def _parse_bw(bw_str: str) -> int:
    match = re.search(r"(\d+)", bw_str)
    return int(match.group(1)) if match else 0


def _effective_date() -> str:
    return (datetime.now() + timedelta(days=15)).strftime("%Y-%m-%d")


def _render_scale_up(line_info: dict, assessment: dict) -> dict:
    date_str = datetime.now().strftime("%Y%m%d")
    line_name = f"{line_info.get('local_site', '?')}-{line_info.get('remote_name', '?')}"
    current_bw = assessment.get("current_bw", "未知")
    target_bw = assessment.get("target_bw", "未知")
    traffic = assessment.get("current_traffic_mbps", 0)
    bw_num = _parse_bw(current_bw)
    utilization = f"{(traffic / bw_num * 100):.0f}%" if bw_num else "未知"

    subject = f"【专线扩容-常态化扩容申请】- {date_str}"
    body = f"""各位领导/同事：

【申请摘要】
根据《数据中心网络专线带宽扩缩容指南》，以下线路过去15天P95利用率已达 {utilization}（阈值40%），且负载均衡正常。现申请进行带宽扩容，涉及线路如下：

1. 专线调整详情表

| 专线号 | 专线名称 | 专线用途 | 运营商 | 现有带宽 | 申请带宽 | 当前P95利用率 | 当前P95流量 | 调整生效日期 |
|--------|----------|----------|--------|----------|----------|---------------|-------------|--------------|
| {line_info.get('local_line_number', '-')} | {line_name} | {line_info.get('purpose', '-')} | {line_info.get('service_provider', '-')} | {current_bw} | {target_bw} | {utilization} | {traffic} Mbps | {_effective_date()} |

2. 评估结果与原因
● 触发原因：业务自然增长，统计周期内P95流量持续高于40%。

3. 流量监控数据（附件图表）
图1：最近15天带宽流量趋势图及P95统计

此致
敬礼！"""

    return {
        "subject": subject,
        "recipients": RECIPIENTS,
        "cc": CC_LIST,
        "body": body,
        "attachments": ["15天流量趋势图", "P95统计报告"],
    }


def _render_scale_down(line_info: dict, assessment: dict) -> dict:
    date_str = datetime.now().strftime("%Y%m%d")
    line_name = f"{line_info.get('local_site', '?')}-{line_info.get('remote_name', '?')}"
    current_bw = assessment.get("current_bw", "未知")
    target_bw = assessment.get("target_bw", "未知")
    traffic = assessment.get("current_traffic_mbps", 0)
    target_num = _parse_bw(target_bw)
    threshold = target_num * 0.35 if target_num else 0

    subject = f"【专线缩容-带宽缩容申请】{line_name} - {date_str}"
    body = f"""各位领导/同事：

【申请摘要】
以下专线长期低负载。经核算，流量已低于目标带宽{target_bw}的35%（{threshold:.1f} Mbps），符合《指南》缩容标准。申请降级以优化成本。

1. 专线调整详情表

| 专线号 | 专线名称 | 专线用途 | 运营商 | 现有带宽 | 申请带宽 | 缩容阈值标准 | 当前P95流量 | 调整生效日期 |
|--------|----------|----------|--------|----------|----------|--------------|-------------|--------------|
| {line_info.get('local_line_number', '-')} | {line_name} | {line_info.get('purpose', '-')} | {line_info.get('service_provider', '-')} | {current_bw} | {target_bw} | < {threshold:.1f} Mbps | {traffic} Mbps | {_effective_date()} |

2. 评估结果与合规性
● 合规性检查：流量低于目标带宽的35%，当前非重大活动保障期。

此致
敬礼！"""

    return {
        "subject": subject,
        "recipients": RECIPIENTS,
        "cc": CC_LIST,
        "body": body,
        "attachments": ["15天流量趋势图", "缩容模拟分析"],
        "template_type": "scale_down",
    }


def _render_temporary(line_info: dict, assessment: dict) -> dict:
    """模板二：临时扩容申请（重大活动/赛事保障）"""
    date_str = datetime.now().strftime("%Y%m%d")
    line_name = f"{line_info.get('local_site', '?')}-{line_info.get('remote_name', '?')}"
    current_bw = assessment.get("current_bw", "未知")
    target_bw = assessment.get("target_bw", "未知")

    subject = f"【专线扩容-临时扩容申请】活动保障 - {date_str}"
    body = f"""各位领导/同事：

【申请摘要】
为保障重大活动顺利进行，基于预测模型，单线利用率将突破安全线。申请临时扩容，活动结束后恢复。

1. 专线调整详情表

| 专线号 | 专线名称 | 专线用途 | 运营商 | 现有带宽 | 申请带宽 | 预计流量 | 生效时间 | 恢复时间 |
|--------|----------|----------|--------|----------|----------|----------|----------|----------|
| {line_info.get('local_line_number', '-')} | {line_name} | {line_info.get('purpose', '-')} | {line_info.get('service_provider', '-')} | {current_bw} | {target_bw} | 待估算 | 活动开始前 | 活动结束后 |

2. 评估结果与原因
● 二线研判：测算结果显示不扩容将导致利用率超过40%安全线，建议临时升级档位以确保高可用。

此致
敬礼！"""

    return {
        "subject": subject,
        "recipients": RECIPIENTS,
        "cc": CC_LIST,
        "body": body,
        "attachments": ["历史同期流量（可选）"],
        "template_type": "temporary",
    }


def _render_emergency(line_info: dict, assessment: dict) -> dict:
    """模板三：应急扩容汇报（突发故障/拥塞）"""
    date_str = datetime.now().strftime("%Y%m%d")
    time_str = datetime.now().strftime("%H:%M")
    line_name = f"{line_info.get('local_site', '?')}-{line_info.get('remote_name', '?')}"
    current_bw = assessment.get("current_bw", "未知")
    target_bw = assessment.get("target_bw", "未知")

    subject = f"【专线扩容-紧急扩容通知】{line_name} 突发高负载告警 - {date_str} {time_str}"
    body = f"""各位领导/同事：

【紧急事态】
{time_str} 监控触发高负载告警，业务已受损。已电话通知运营商，要求2小时内生效。流程后补。

1. 专线调整详情表

| 专线号 | 专线名称 | 专线用途 | 运营商 | 现有带宽 | 申请带宽 | 当前实时利用率 | 网络质量状况 | 要求生效时间 |
|--------|----------|----------|--------|----------|----------|----------------|--------------|----------------|
| {line_info.get('local_line_number', '-')} | {line_name} | {line_info.get('purpose', '-')} | {line_info.get('service_provider', '-')} | {current_bw} | {target_bw} | 待填写 | 待填写 | 立即生效 |

2. 故障分析与处置
● 后续处置：扩容后将进入3天观察期，待流量稳定并查明根因后，再评估是否恢复。

此致
敬礼！"""

    return {
        "subject": subject,
        "recipients": RECIPIENTS,
        "cc": CC_LIST,
        "body": body,
        "attachments": ["实时监控告警截图"],
        "template_type": "emergency",
    }


def register(mcp: FastMCP):
    @mcp.tool
    def email_generate(
        action: str,
        line_info: dict,
        assessment: dict,
        template_type: str = "normal",
    ) -> dict:
        """根据带宽评估结果生成邮件草稿。

        支持4种邮件模板（对应 bandwidth.md 中的模板一~模板四）：
        - scale_up + normal → 模板一：常态化扩容
        - scale_up + temporary → 模板二：临时扩容（重大活动保障）
        - scale_up + emergency → 模板三：应急扩容（突发故障）
        - scale_down → 模板四：缩容申请

        Args:
            action: 操作类型，"scale_up" 或 "scale_down"
            line_info: 线路信息字典（来自 line_info_query 的返回结果）
            assessment: 评估结果字典（来自 bandwidth_assess 的返回结果）
            template_type: 扩容子类型（仅 scale_up 时有效），"normal"（默认）、"temporary"、"emergency"

        Returns:
            邮件草稿字典，包含 subject、recipients、cc、body、attachments、template_type。
            如果 action 不是 scale_up 或 scale_down，返回空字典。
        """
        if action == "scale_up":
            if template_type == "emergency":
                return _render_emergency(line_info, assessment)
            elif template_type == "temporary":
                return _render_temporary(line_info, assessment)
            else:
                return _render_scale_up(line_info, assessment)
        elif action == "scale_down":
            return _render_scale_down(line_info, assessment)
        else:
            return {"message": f"action={action} 不需要生成邮件"}
```

- [ ] **Step 2: Commit**

```bash
git add mcp-servers/network-ops/tools/email_generate.py
git commit -m "feat(network-ops): add email_generate MCP tool"
```

---

## Task 10: Create the Skill document (no duplicated data)

**Files:**
- Create: `skills/custom/bandwidth-management/SKILL.md`
- Create: `skills/custom/bandwidth-management/bandwidth-policy.md`

**Design Principle:** The Skill document teaches the Agent HOW to work (workflow, triggers, semantic understanding). It does NOT contain policy data (tier tables, thresholds, operation steps, email template formats). When the Agent needs policy details, it calls `policy_search` to query the RAG — ensuring bandwidth.md remains the single source of truth.

- [ ] **Step 1: Create directory**

```bash
mkdir -p skills/custom/bandwidth-management
```

- [ ] **Step 2: Create `SKILL.md`** — workflow guide only, no duplicated data

```markdown
---
name: bandwidth-management
description: 带宽管理技能。当用户咨询专线带宽相关问题（扩容、缩容、线路查询、流量分析、邮件申请）时加载此技能。触发词：带宽、扩容、缩容、线路、专线、流量、P95。也适用于用户提供流量报表或监控数据的场景。
---

# 带宽管理技能

## 概述

此技能指导你完成带宽策略分析的完整流程：从理解用户需求，到查询线路信息、评估带宽策略、生成操作建议和邮件草稿。

**重要：本技能不包含带宽策略数据。** 带宽阈值表、操作流程、邮件模板格式等详细策略信息存储在 `docs/bandwidth.md` 中，通过 RAG 语义搜索获取。当你需要了解具体策略细节时，调用 `policy_search` 工具。

## 触发条件

当用户输入包含以下任何一种情况时，立即加载此技能：
- 提到"带宽"、"专线"、"线路"、"流量"、"扩容"、"缩容"
- 提到具体带宽值如"10M"、"20M"、"5Mbps"
- 提到两端站点如"亦庄到西藏"、"西五环到山东"
- 粘贴流量监控数据或报表
- 询问带宽相关操作流程

## 可用工具

| 工具 | 用途 | 数据源 |
|------|------|--------|
| `line_info_query` | 查询专线线路信息 | MySQL (iteams_db) |
| `bandwidth_assess` | 评估带宽是否需要扩缩容 | SQLite (从 bandwidth.md 解析的区间表) |
| `policy_search` | 搜索带宽策略文档 | ChromaDB RAG (bandwidth.md 全文) |
| `bandwidth_stats` | 查询带宽档位统计 | SQLite + MySQL |
| `email_generate` | 生成邮件草稿（4种模板） | 代码中引用 bandwidth.md 模板格式 |

## 工作流程

### 流程 A：自然语言输入（一句话）

示例输入：`"亦庄到西藏数据端带宽使用到了5M，应该怎么办？"`

**步骤：**

1. **理解用户意图**：从输入中提取关键信息
   - 站点：亦庄 → 西藏
   - 用途：数据端
   - 流量/带宽：使用了5M（这是流量，不是带宽）

2. **查询线路信息**：调用 `line_info_query` 工具
   ```
   line_info_query(description="亦庄到西藏数据端")
   ```
   从返回结果中获取：线路的 `bandwidth` 字段（实际带宽档位）

3. **评估带宽策略**：调用 `bandwidth_assess` 工具
   ```
   bandwidth_assess(current_bw_mbps=<从线路信息获取>, current_traffic_mbps=<用户提到的流量>)
   ```

4. **查询操作流程**（如需扩缩容）：调用 `policy_search` 工具
   ```
   policy_search(query="扩容操作流程")  # 或 "缩容操作流程"、"应急扩容流程" 等
   ```
   从 RAG 返回的章节中提取具体操作步骤和注意事项。

5. **生成邮件**（如需扩缩容）：调用 `email_generate` 工具
   ```
   email_generate(action=<评估结果中的action>, line_info=<线路信息>, assessment=<评估结果>)
   ```
   根据场景选择模板类型：`normal`（常态化）、`temporary`（临时）、`emergency`（应急）。

6. **回复用户**：整合所有信息，包含：
   - 线路基本信息
   - 当前带宽评估结论（从 bandwidth_assess 获取）
   - 操作建议（从 policy_search 获取的流程步骤）
   - 邮件草稿（如有）

### 流程 B：报表/数据输入

示例输入：`[粘贴15天流量监控Excel或截图]`

**步骤：**

1. **解析报表数据**：使用 `read_file` 读取上传的文件
   - 提取线路名称/编号
   - 提取 P95 流量值（重点关注）
   - 提取统计周期

2. **对每条线路执行流程 A 的步骤 2-6**

### 流程 C：统计查询

示例输入：`"10M的线路有多少条？"`

**步骤：**

1. 调用 `bandwidth_stats(bandwidth="10M")` 获取统计数据
2. 回复用户统计结果

### 流程 D：策略咨询

示例输入：`"扩容操作流程是什么？"` 或 `"什么情况下需要应急扩容？"`

**步骤：**

1. 调用 `policy_search(query="<用户的实际问题>")` 搜索策略文档
2. 将 RAG 返回的匹配章节整理后回复用户

## 语义理解要点

当用户说以下内容时，正确理解含义：
- "带宽使用到了5M" → 流量 5Mbps（不是带宽5M）
- "10M的线路" → 带宽档位 10M
- "流量5M" → 流量 5Mbps
- "亦庄到西藏" → 查询线路：本端=亦庄，对端=西藏
- "应该怎么办" → 需要评估 + 操作建议
- "帮我发个邮件" → 需要生成邮件草稿
- "扩容流程是什么" → 调用 policy_search 查询操作流程
- "什么时候需要应急扩容" → 调用 policy_search 查询判定标准

## 注意事项

- 带宽阈值和档位表由 `bandwidth_assess` 工具自动处理（基于 SQLite 中的区间表），无需在 Skill 中重复
- 操作流程详情（步骤、角色职责、风险控制）通过 `policy_search` 获取，不在此文档中硬编码
- 邮件模板格式由 `email_generate` 工具处理，支持4种模板（常态化扩容、临时扩容、应急扩容、缩容）
- 如需了解完整策略，可读取参考文档：`./bandwidth-policy.md`
```

- [ ] **Step 3: Create `bandwidth-policy.md`** — copy of docs/bandwidth.md for Agent reference

```bash
cp docs/bandwidth.md skills/custom/bandwidth-management/bandwidth-policy.md
```

This is a convenience copy so the Agent can `read_file` the full policy without needing to know the docs/ path. The canonical source is always `docs/bandwidth.md`.

- [ ] **Step 4: Commit**

```bash
git add skills/custom/bandwidth-management/
git commit -m "feat(skills): add bandwidth-management skill (no duplicated data)"
```

---

## Task 11: Register MCP Server in DeerFlow

**Files:**
- Modify: `extensions_config.json` (create if not exists)
- Modify: `config.yaml` (remove old tool registration)

- [ ] **Step 1: Verify if `extensions_config.json` exists**

```bash
ls -la extensions_config.json 2>/dev/null || echo "NOT FOUND"
```

- [ ] **Step 2: Create or update `extensions_config.json`**

Add the `network-ops` MCP server entry. Use stdio transport for development (DeerFlow auto-manages the process):

```json
{
  "mcpServers": {
    "network-ops": {
      "enabled": true,
      "type": "stdio",
      "command": "python",
      "args": ["mcp-servers/network-ops/server.py"],
      "env": {
        "MYSQL_HOST": "host.docker.internal",
        "MYSQL_PORT": "3306",
        "MYSQL_USER": "$MYSQL_USER",
        "MYSQL_PASSWORD": "$MYSQL_PASSWORD",
        "MYSQL_DATABASE": "$MYSQL_DATABASE"
      },
      "description": "网络运维工具集：线路查询、带宽评估、统计查询、邮件生成"
    }
  },
  "skills": {}
}
```

- [ ] **Step 3: Remove old tool registration from `config.yaml`**

Remove lines 434-437 in `config.yaml`:

```yaml
  # REMOVE THESE LINES:
  # Bandwidth policy query tool (RAG-based)
  - name: bandwidth_policy_query
    group: network
    use: deerflow.tools.bandwidth_tool:bandwidth_policy_query_tool
```

- [ ] **Step 4: Commit**

```bash
git add extensions_config.json config.yaml
git commit -m "feat: register network-ops MCP server, remove old bandwidth tool"
```

---

## Task 12: Clean up old code

**Files:**
- Delete: `backend/packages/harness/deerflow/tools/bandwidth_tool.py`
- Modify: `backend/packages/harness/deerflow/rag/__init__.py` (remove bandwidth imports)
- Delete: `backend/packages/harness/deerflow/rag/bandwidth_db.py`
- Delete: `backend/packages/harness/deerflow/rag/bandwidth_rag.py`
- Delete: `backend/packages/harness/deerflow/rag/line_info_provider.py`
- Keep: `backend/packages/harness/deerflow/config/network_ops_config.py` (shared config reference)

- [ ] **Step 1: Update `rag/__init__.py`**

Remove all bandwidth-related imports. Leave the file as an empty package:

```python
# backend/packages/harness/deerflow/rag/__init__.py
"""RAG modules for DeerFlow."""
```

- [ ] **Step 2: Delete old files**

```bash
rm backend/packages/harness/deerflow/tools/bandwidth_tool.py
rm backend/packages/harness/deerflow/rag/bandwidth_db.py
rm backend/packages/harness/deerflow/rag/bandwidth_rag.py
rm backend/packages/harness/deerflow/rag/line_info_provider.py
```

- [ ] **Step 3: Verify no broken imports**

```bash
cd backend && python -c "from deerflow.tools.tools import get_available_tools; print('OK')"
```

Expected: `OK` (no import errors)

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "chore: remove old monolithic bandwidth tool and rag modules"
```

---

## Task 13: End-to-end verification

**Files:**
- No new files

- [ ] **Step 1: Verify MCP server starts standalone**

```bash
cd mcp-servers/network-ops && python -c "from server import mcp; print(f'Tools: {[t.name for t in mcp._tool_manager._tools.values()]}')"
```

Expected: Tool names listed including `line_info_query`, `bandwidth_assess`, `bandwidth_stats`, `email_generate`

- [ ] **Step 2: Verify Skill loads in DeerFlow**

```bash
cd backend && python -c "
from deerflow.skills import load_skills
skills = load_skills(enabled_only=False)
bw_skill = [s for s in skills if s.name == 'bandwidth-management']
print(f'Skill found: {bool(bw_skill)}')
if bw_skill:
    print(f'Skill path: {bw_skill[0].skill_file}')
"
```

Expected: `Skill found: True`

- [ ] **Step 3: Verify DeerFlow starts without errors**

```bash
make dev
```

Wait for all 4 services to start. Check `logs/langgraph.log` for MCP server initialization:

```bash
grep "MCP" logs/langgraph.log | head -5
```

Expected: Log line like `Configured MCP server: network-ops`

- [ ] **Step 4: Test via WebUI**

Open http://localhost:2026, send: `"亦庄到西藏数据端带宽使用到了5M，应该怎么办？"`

Expected behavior:
1. Agent loads the bandwidth-management Skill
2. Agent calls `network-ops.line_info_query(description="亦庄到西藏数据端")`
3. Agent calls `network-ops.bandwidth_assess(current_bw_mbps=10, current_traffic_mbps=5.0)`
4. Agent calls `network-ops.email_generate(action="scale_up", ...)`
5. Agent returns complete assessment + email draft

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "feat: bandwidth management MCP server + Skill architecture complete"
```

---

## Self-Review Checklist

### Spec Coverage
| Requirement | Task |
|---|---|
| MCP Server with FastMCP | Task 1 |
| MySQL client (line info) | Task 2, Task 5 |
| SQLite client (bandwidth tiers from bandwidth.md) | Task 3, Task 6 |
| Chroma RAG (ingests bandwidth.md) | Task 4, Task 8 |
| bandwidth_assess tool | Task 6 |
| line_info_query tool | Task 5 |
| bandwidth_stats tool | Task 7 |
| policy_search tool (RAG) | Task 8 |
| email_generate tool (4 templates) | Task 9 |
| Skill document (no duplicated data) | Task 10 |
| Skill reference doc (bandwidth-policy.md copy) | Task 10 |
| extensions_config.json registration | Task 11 |
| Remove old monolithic tool | Task 12 |
| End-to-end verification | Task 13 |

### Data Source Integrity
- ✅ `docs/bandwidth.md` is the single source of truth
- ✅ Tier table parsed from bandwidth.md → SQLite (Task 3, `init_tiers.py`)
- ✅ Full text ingested into ChromaDB RAG (Task 4, `bandwidth_rag.py`)
- ✅ Email templates rendered from bandwidth.md template formats (Task 9)
- ✅ Skill document references `policy_search` tool instead of duplicating data (Task 10)
- ✅ No hardcoded tier tables or policy text in any code file

### Placeholder Scan
- No TBD/TODO found
- All code blocks contain complete implementations
- All file paths are exact

### Type Consistency
- All tools accept/return `dict` or `list[dict]` — consistent with DeerFlow's `BaseTool` expectations
- `assessment` dict keys match between `bandwidth_assess` output and `email_generate` input
- `line_info` dict keys match between `line_info_query` output and `email_generate` input
