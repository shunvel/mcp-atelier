"""Docker Desktop tools for MCP server."""

from __future__ import annotations

import json

import docker
from docker.errors import DockerException


def _get_client() -> docker.DockerClient:
    return docker.from_env()


def docker_list_containers(all_containers: bool = False) -> str:
    """List Docker containers on the local machine.

    Args:
        all_containers: If True, include stopped containers. Default False.
    """
    try:
        client = _get_client()
        containers = client.containers.list(all=all_containers)
        result = []
        for c in containers:
            result.append(
                {
                    "id": c.short_id,
                    "name": c.name,
                    "status": c.status,
                    "image": c.image.tags[0] if c.image.tags else c.image.short_id,
                    "ports": c.ports,
                }
            )
        return json.dumps({"count": len(result), "containers": result}, indent=2)
    except DockerException as exc:
        return json.dumps({"error": f"Docker unavailable: {exc}"})


def docker_container_logs(container_id: str, tail: int = 50) -> str:
    """Fetch the last N log lines from a Docker container.

    Args:
        container_id: Container ID or name.
        tail: Number of log lines to return (default 50, max 200).
    """
    tail = min(max(tail, 1), 200)
    try:
        client = _get_client()
        container = client.containers.get(container_id)
        logs = container.logs(tail=tail).decode("utf-8", errors="replace")
        return json.dumps(
            {"container": container.name, "tail": tail, "logs": logs},
            indent=2,
        )
    except DockerException as exc:
        return json.dumps({"error": f"Failed to fetch logs: {exc}"})


def docker_list_images() -> str:
    """List Docker images available locally."""
    try:
        client = _get_client()
        images = client.images.list()
        result = []
        for img in images:
            result.append(
                {
                    "id": img.short_id,
                    "tags": img.tags,
                    "size_mb": round(img.attrs.get("Size", 0) / (1024 * 1024), 2),
                }
            )
        return json.dumps({"count": len(result), "images": result}, indent=2)
    except DockerException as exc:
        return json.dumps({"error": f"Docker unavailable: {exc}"})
