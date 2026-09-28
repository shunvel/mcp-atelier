"""MCP prompts — user-controlled interaction templates."""

from mcp.server.fastmcp.prompts import base


def docker_health_check() -> list[base.Message]:
    """Generate a Docker health check workflow prompt."""
    return [
        base.Message(
            role="user",
            content=base.TextContent(
                type="text",
                text=(
                    "Perform a Docker health check on my local machine:\n"
                    "1. Read the docker://system-info resource for system overview.\n"
                    "2. List all running containers using docker_list_containers.\n"
                    "3. For any container that is not 'running', note its status.\n"
                    "4. Summarize the overall Docker health in plain language."
                ),
            ),
        )
    ]


def weather_trip_advice(city: str = "Bangalore") -> list[base.Message]:
    """Generate a weather and trip advice workflow prompt."""
    return [
        base.Message(
            role="user",
            content=base.TextContent(
                type="text",
                text=(
                    f"I'm planning a trip to {city}. Please:\n"
                    f"1. Read the weather://cities resource to confirm coordinates.\n"
                    f"2. Use get_weather for '{city}' to get current conditions.\n"
                    f"3. Based on temperature, humidity, and wind, suggest what to pack "
                    f"and whether it's a good day for outdoor activities."
                ),
            ),
        )
    ]


def sql_data_explorer(question: str = "What are the top products by total revenue?") -> list[base.Message]:
    """Generate a SQL data exploration workflow prompt."""
    return [
        base.Message(
            role="user",
            content=base.TextContent(
                type="text",
                text=(
                    f"Explore the demo SQLite database and answer: {question}\n\n"
                    "Steps:\n"
                    "1. Read the sqlite://schema resource to understand table structure.\n"
                    "2. Use sqlite_list_tables to confirm available tables.\n"
                    "3. Optionally read sqlite://preview/{table} resources for sample data.\n"
                    "4. Write and run a SELECT query with sqlite_run_query.\n"
                    "5. Present the answer clearly with the query you used."
                ),
            ),
        )
    ]
