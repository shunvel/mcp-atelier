"""MCP resources — application-controlled context data."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import docker
from docker.errors import DockerException

from server.tools_weather import CITY_COORDS

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "demo.db"


def get_docker_system_info() -> str:
    """Docker system information resource."""
    try:
        client = docker.from_env()
        info = client.info()
        version = client.version()
        return json.dumps(
            {
                "docker_version": version.get("Version", "unknown"),
                "api_version": version.get("ApiVersion", "unknown"),
                "os": info.get("OperatingSystem", "unknown"),
                "architecture": info.get("Architecture", "unknown"),
                "cpus": info.get("NCPU", 0),
                "memory_gb": round(info.get("MemTotal", 0) / (1024**3), 2),
                "containers_running": info.get("ContainersRunning", 0),
                "containers_total": info.get("Containers", 0),
                "images": info.get("Images", 0),
            },
            indent=2,
        )
    except DockerException as exc:
        return json.dumps({"error": f"Docker unavailable: {exc}"})


def get_weather_cities() -> str:
    """Curated city list with coordinates for weather lookups."""
    cities = [
        {"city": name.title(), "latitude": lat, "longitude": lon}
        for name, (lat, lon) in sorted(CITY_COORDS.items())
    ]
    return json.dumps({"cities": cities, "count": len(cities)}, indent=2)


def get_sqlite_schema() -> str:
    """Full CREATE TABLE schema dump of the demo database."""
    if not DB_PATH.exists():
        return json.dumps({"error": f"Database not found at {DB_PATH}"})

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    schemas = {row[0].split("(")[0].replace("CREATE TABLE ", "").strip(): row[0] for row in cursor.fetchall() if row[0]}
    conn.close()
    return json.dumps({"schema": schemas}, indent=2)


def get_sqlite_preview(table: str) -> str:
    """Preview first 5 rows of a SQLite table."""
    if not DB_PATH.exists():
        return json.dumps({"error": f"Database not found at {DB_PATH}"})

    allowed = {"customers", "products", "orders"}
    if table not in allowed:
        return json.dumps({"error": f"Unknown table '{table}'. Allowed: {sorted(allowed)}"})

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(f"SELECT * FROM {table} LIMIT 5")
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return json.dumps({"table": table, "preview_rows": rows}, indent=2, default=str)
