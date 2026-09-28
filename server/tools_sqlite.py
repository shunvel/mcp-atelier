"""Read-only SQLite query tools."""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "demo.db"

# Block any non-SELECT statements
_WRITE_PATTERN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE|REPLACE|ATTACH|DETACH|PRAGMA)\b",
    re.IGNORECASE,
)


def _get_connection() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Database not found at {DB_PATH}. Run: python scripts/init_db.py"
        )
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def sqlite_list_tables() -> str:
    """List all tables in the demo SQLite database."""
    try:
        conn = _get_connection()
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()
        return json.dumps({"tables": tables, "count": len(tables)}, indent=2)
    except Exception as exc:
        return json.dumps({"error": str(exc)})


def sqlite_run_query(query: str) -> str:
    """Run a read-only SELECT query against the demo SQLite database.

    Only SELECT statements are allowed. Write operations are rejected.

    Args:
        query: SQL SELECT query to execute.
    """
    query = query.strip().rstrip(";")

    if not query.upper().startswith("SELECT"):
        return json.dumps({"error": "Only SELECT queries are allowed."})

    if _WRITE_PATTERN.search(query):
        return json.dumps({"error": "Query contains forbidden keywords."})

    try:
        conn = _get_connection()
        cursor = conn.execute(query)
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return json.dumps(
            {"columns": columns, "row_count": len(rows), "rows": rows},
            indent=2,
            default=str,
        )
    except Exception as exc:
        return json.dumps({"error": str(exc)})
