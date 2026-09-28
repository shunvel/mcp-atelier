"""MCP Learning Lab server — exposes tools, resources, and prompts."""

from mcp.server.fastmcp import FastMCP

from server import prompts as prompt_templates
from server import resources
from server import tools_docker, tools_sqlite, tools_weather

mcp = FastMCP("MCP Learning Lab")


# --- Tools (model-controlled) ---

@mcp.tool()
def docker_list_containers(all_containers: bool = False) -> str:
    """List Docker containers on the local machine."""
    return tools_docker.docker_list_containers(all_containers)


@mcp.tool()
def docker_container_logs(container_id: str, tail: int = 50) -> str:
    """Fetch the last N log lines from a Docker container."""
    return tools_docker.docker_container_logs(container_id, tail)


@mcp.tool()
def docker_list_images() -> str:
    """List Docker images available locally."""
    return tools_docker.docker_list_images()


@mcp.tool()
def get_weather(city: str) -> str:
    """Get current weather for a city using Open-Meteo API."""
    return tools_weather.get_weather(city)


@mcp.tool()
def sqlite_list_tables() -> str:
    """List all tables in the demo SQLite database."""
    return tools_sqlite.sqlite_list_tables()


@mcp.tool()
def sqlite_run_query(query: str) -> str:
    """Run a read-only SELECT query against the demo SQLite database."""
    return tools_sqlite.sqlite_run_query(query)


# --- Resources (application-controlled) ---

@mcp.resource("docker://system-info")
def docker_system_info() -> str:
    """Docker Desktop system information (version, CPUs, memory, container counts)."""
    return resources.get_docker_system_info()


@mcp.resource("weather://cities")
def weather_cities() -> str:
    """Curated list of cities with latitude/longitude for weather lookups."""
    return resources.get_weather_cities()


@mcp.resource("sqlite://schema")
def sqlite_schema() -> str:
    """CREATE TABLE schema dump of the demo SQLite database."""
    return resources.get_sqlite_schema()


@mcp.resource("sqlite://preview/{table}")
def sqlite_preview(table: str) -> str:
    """Preview first 5 rows of a demo database table (customers, products, orders)."""
    return resources.get_sqlite_preview(table)


# --- Prompts (user-controlled) ---

@mcp.prompt()
def docker_health_check() -> list:
    """Workflow: inspect Docker containers and summarize system health."""
    return prompt_templates.docker_health_check()


@mcp.prompt()
def weather_trip_advice(city: str = "Bangalore") -> list:
    """Workflow: get weather for a city and suggest packing/trip advice."""
    return prompt_templates.weather_trip_advice(city)


@mcp.prompt()
def sql_data_explorer(question: str = "What are the top products by total revenue?") -> list:
    """Workflow: explore SQLite schema and answer a data question."""
    return prompt_templates.sql_data_explorer(question)


if __name__ == "__main__":
    mcp.run()
