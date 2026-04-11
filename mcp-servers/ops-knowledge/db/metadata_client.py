"""SQLite metadata client for ops-knowledge documents."""

import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def _resolve_path(path_str: str) -> str:
    """Resolve a path relative to project root if not absolute."""
    p = Path(path_str)
    if p.is_absolute():
        return str(p)
    return str(_PROJECT_ROOT / p)


class MetadataClient:
    """Manages document metadata and upload logs in SQLite."""

    def __init__(self, db_path: str):
        self.db_path = _resolve_path(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            self._create_tables(conn)

    def _create_tables(self, conn):
        conn.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                doc_id TEXT PRIMARY KEY,
                doc_type TEXT NOT NULL,
                title TEXT NOT NULL,
                source_file TEXT NOT NULL,
                device_vendor TEXT,
                device_type TEXT,
                chunk_count INTEGER,
                upload_date TEXT NOT NULL,
                file_hash TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS upload_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_id TEXT NOT NULL,
                action TEXT NOT NULL,
                status TEXT NOT NULL,
                message TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.commit()

    def upsert_document(self, doc: dict) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO documents
                    (doc_id, doc_type, title, source_file, device_vendor,
                     device_type, chunk_count, upload_date, file_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    doc["doc_id"],
                    doc["doc_type"],
                    doc["title"],
                    doc["source_file"],
                    doc.get("device_vendor"),
                    doc.get("device_type"),
                    doc.get("chunk_count", 0),
                    doc.get("upload_date", datetime.now().isoformat()),
                    doc["file_hash"],
                ),
            )
            conn.commit()

    def get_document_by_hash(self, file_hash: str) -> Optional[dict]:
        """Find a document by its file hash."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM documents WHERE file_hash = ?", (file_hash,)
            ).fetchone()
            return dict(row) if row else None

    def get_document_by_title(self, title: str) -> Optional[dict]:
        """Find a document by its title."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM documents WHERE title = ?", (title,)
            ).fetchone()
            return dict(row) if row else None

    def get_document(self, doc_id: str) -> Optional[dict]:
        """Find a document by its doc_id."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM documents WHERE doc_id = ?", (doc_id,)
            ).fetchone()
            return dict(row) if row else None

    def delete_document(self, doc_id: str) -> None:
        """Delete a document record by doc_id."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM documents WHERE doc_id = ?", (doc_id,))
            conn.commit()

    def list_documents(
        self,
        doc_type: Optional[str] = None,
        device_vendor: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict]:
        """Paginated document listing with optional filters."""
        conditions = []
        params: list = []

        if doc_type is not None:
            conditions.append("doc_type = ?")
            params.append(doc_type)
        if device_vendor is not None:
            conditions.append("device_vendor = ?")
            params.append(device_vendor)

        where = ""
        if conditions:
            where = "WHERE " + " AND ".join(conditions)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                f"SELECT * FROM documents {where} ORDER BY upload_date DESC LIMIT ? OFFSET ?",
                params + [limit, offset],
            ).fetchall()
            return [dict(row) for row in rows]

    def count_documents(self, doc_type: Optional[str] = None) -> int:
        """Count documents, optionally filtered by doc_type."""
        with sqlite3.connect(self.db_path) as conn:
            if doc_type is not None:
                row = conn.execute(
                    "SELECT COUNT(*) FROM documents WHERE doc_type = ?", (doc_type,)
                ).fetchone()
            else:
                row = conn.execute("SELECT COUNT(*) FROM documents").fetchone()
            return row[0] if row else 0

    def log_upload(
        self, doc_id: str, action: str, status: str, message: str = ""
    ) -> None:
        """Record an upload log entry."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO upload_logs (doc_id, action, status, message)
                VALUES (?, ?, ?, ?)
                """,
                (doc_id, action, status, message),
            )
            conn.commit()
