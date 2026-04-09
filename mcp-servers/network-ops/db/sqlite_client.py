import logging
import sqlite3
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Project root is 3 levels up from this file: db/sqlite_client.py -> network-ops -> mcp-servers -> project-root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def _resolve_path(path_str: str) -> str:
    """Resolve a path relative to project root if not absolute."""
    p = Path(path_str)
    if p.is_absolute():
        return str(p)
    return str(_PROJECT_ROOT / p)


def _parse_tiers_from_md(md_path: str = "docs/bandwidth.md") -> list[tuple]:
    """Parse bandwidth tier table from bandwidth.md."""
    import re

    resolved = _resolve_path(md_path)
    tiers = []
    content = Path(resolved).read_text(encoding="utf-8")

    for line in content.strip().split("\n"):
        if "当前单线带宽" in line or not line.strip():
            continue

        parts = [p.strip() for p in line.split("\t") if p.strip()]
        if len(parts) < 6:
            continue

        try:
            current_bw = int(parts[0].split()[0])
            scale_up_threshold = float(re.search(r"[\d.]+", parts[1]).group())
            scale_up_target = int(parts[2].split()[0])

            scale_down_threshold = None
            scale_down_target = None
            if parts[3] != "-":
                scale_down_threshold = float(re.search(r"[\d.]+", parts[3]).group())
            if parts[4] != "-":
                scale_down_target = int(parts[4].split()[0])

            description = parts[5]
            tiers.append(
                (
                    current_bw,
                    scale_up_threshold,
                    scale_up_target,
                    scale_down_threshold,
                    scale_down_target,
                    description,
                )
            )
        except (ValueError, AttributeError, IndexError):
            continue

    return tiers


class SQLiteClient:
    def __init__(self, db_path: str, md_path: str = "docs/bandwidth.md"):
        resolved_db = _resolve_path(db_path)
        Path(resolved_db).parent.mkdir(parents=True, exist_ok=True)
        self.db_path = resolved_db
        self.md_path = md_path
        with sqlite3.connect(self.db_path) as conn:
            self._create_tables(conn)
            self._seed_from_md(conn)

    def _create_tables(self, conn):
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
            CREATE TRIGGER IF NOT EXISTS update_bandwidth_tiers_updated_at
            AFTER UPDATE ON bandwidth_tiers
            BEGIN
                UPDATE bandwidth_tiers SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
            END;
        """)

    def _seed_from_md(self, conn):
        count = conn.execute("SELECT COUNT(*) FROM bandwidth_tiers").fetchone()[0]
        if count == 0:
            tiers = _parse_tiers_from_md(self.md_path)
            conn.executemany(
                """
                INSERT INTO bandwidth_tiers (
                    current_bw_mbps, scale_up_threshold_mbps, scale_up_target_mbps, 
                    scale_down_threshold_mbps, scale_down_target_mbps, description
                ) VALUES (?, ?, ?, ?, ?, ?)
            """,
                tiers,
            )
            conn.commit()

    def get_tier(self, bw_mbps: int) -> Optional[dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM bandwidth_tiers WHERE current_bw_mbps = ?", (bw_mbps,)
            ).fetchone()
            return dict(row) if row else None

    def get_all_tiers(self) -> list[dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            return [
                dict(row)
                for row in conn.execute(
                    "SELECT * FROM bandwidth_tiers ORDER BY current_bw_mbps ASC"
                )
            ]

    def get_recommendation(self, current_bw_mbps: int, current_traffic: float) -> dict:
        tier = self.get_tier(current_bw_mbps)
        if not tier:
            return {"action": "unknown", "reasoning": "带宽档位未找到"}

        if current_traffic > tier["scale_up_threshold_mbps"]:
            return {
                "action": "scale_up",
                "current_bw": current_bw_mbps,
                "current_traffic_mbps": current_traffic,
                "threshold_mbps": tier["scale_up_threshold_mbps"],
                "target_bw": tier["scale_up_target_mbps"],
                "reasoning": f"流量 {current_traffic} > 扩容阈值 {tier['scale_up_threshold_mbps']}，建议扩容至 {tier['scale_up_target_mbps']} Mbps",
            }

        if (
            tier["scale_down_threshold_mbps"] is not None
            and current_traffic < tier["scale_down_threshold_mbps"]
        ):
            return {
                "action": "scale_down",
                "current_bw": current_bw_mbps,
                "current_traffic_mbps": current_traffic,
                "threshold_mbps": tier["scale_down_threshold_mbps"],
                "target_bw": tier["scale_down_target_mbps"],
                "reasoning": f"流量 {current_traffic} < 缩容阈值 {tier['scale_down_threshold_mbps']}，建议缩容至 {tier['scale_down_target_mbps']} Mbps",
            }

        return {
            "action": "maintain",
            "current_bw": current_bw_mbps,
            "current_traffic_mbps": current_traffic,
            "reasoning": "流量在正常范围内，维持当前带宽配置",
        }
