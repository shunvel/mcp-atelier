"""Streamlit UI for MCP Learning Lab — chat, workflows, live trace, diagrams."""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

try:
    import mcp  # noqa: F401
except ModuleNotFoundError:
    print(
        "\nERROR: Python package 'mcp' is not installed in this interpreter.\n"
        "Use the project virtualenv:\n"
        "  source .venv/bin/activate\n"
        "  streamlit run ui/app.py\n\n"
        "Or run directly:\n"
        "  .venv/bin/streamlit run ui/app.py\n"
        "  ./scripts/run_ui.sh\n",
        file=sys.stderr,
    )
    raise SystemExit(1)

import streamlit as st

# Ensure project root is on path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

from client.async_runner import AsyncRunner
from client.env import get_gemini_api_key, load_project_env
from client.gemini_agent import GeminiAgent
from client.mcp_client import MCPClientWrapper
from client.tracer import Tracer, TraceEvent
from ui.diagrams import DIAGRAM_RENDERERS

ENV_FILE = load_project_env()

st.set_page_config(
    page_title="MCP Learning Lab",
    page_icon="🔬",
    layout="wide",
)

# --- Session state ---

if "messages" not in st.session_state:
    st.session_state.messages = []
if "trace_events" not in st.session_state:
    st.session_state.trace_events = []
if "mcp_connected" not in st.session_state:
    st.session_state.mcp_connected = False
if "tools" not in st.session_state:
    st.session_state.tools = []
if "resources" not in st.session_state:
    st.session_state.resources = []
if "prompts" not in st.session_state:
    st.session_state.prompts = []
if "connect_error" not in st.session_state:
    st.session_state.connect_error = None


def _format_timestamp(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%H:%M:%S.%f")[:-3]


def _event_color(event_type: str) -> str:
    if "error" in event_type:
        return "#dc2626"
    colors = {
        "session": "#6366f1",
        "mcp": "#0891b2",
        "llm": "#d97706",
        "workflow": "#7c3aed",
    }
    for prefix, color in colors.items():
        if event_type.startswith(prefix):
            return color
    return "#6b7280"


def render_trace_timeline(events: list[TraceEvent]) -> None:
    """Render the live activity timeline."""
    if not events:
        st.info("No activity yet. Send a message or run a workflow to see the MCP trace.")
        return

    for event in events:
        color = _event_color(event.event_type)
        with st.container():
            cols = st.columns([0.5, 0.5, 4, 1])
            with cols[0]:
                st.markdown(f"`{_format_timestamp(event.timestamp)}`")
            with cols[1]:
                st.markdown(f"**{event.direction}**")
            with cols[2]:
                st.markdown(
                    f"<span style='color:{color}; font-weight:600'>{event.event_type}</span> "
                    f"— {event.summary}",
                    unsafe_allow_html=True,
                )
            with cols[3]:
                if event.payload:
                    with st.popover("JSON"):
                        st.json(event.payload)


async def _connect_mcp(
    existing_client: MCPClientWrapper | None = None,
) -> dict:
    """Connect to MCP server. Must not touch Streamlit session state (runs off main thread)."""
    if existing_client is not None:
        await existing_client.close()

    tracer = Tracer()
    mcp_client = MCPClientWrapper(tracer)
    await mcp_client.connect()
    agent = GeminiAgent(mcp_client, tracer)

    return {
        "mcp_client": mcp_client,
        "agent": agent,
        "tracer": tracer,
        "tools": [t.name for t in mcp_client.tools],
        "resources": [str(r.uri) for r in mcp_client.resources],
        "prompts": [p.name for p in mcp_client.prompts],
        "trace_events": list(tracer.events),
    }


async def _run_agent(
    agent: GeminiAgent,
    tracer: Tracer,
    message: str,
    resources: list[str] | None = None,
) -> dict:
    tracer.clear()
    response = await agent.run(message, preload_resources=resources)
    return {"response": response, "trace_events": list(tracer.events)}


async def _run_workflow(
    agent: GeminiAgent,
    tracer: Tracer,
    prompt_name: str,
    prompt_args: dict | None = None,
    resources: list[str] | None = None,
) -> dict:
    tracer.clear()
    response = await agent.run_prompt_workflow(prompt_name, prompt_args, preload_resources=resources)
    return {"response": response, "trace_events": list(tracer.events)}


def _apply_connection(result: dict) -> None:
    """Persist connection on the Streamlit main thread only."""
    st.session_state.mcp_client = result["mcp_client"]
    st.session_state.agent = result["agent"]
    st.session_state.tracer = result["tracer"]
    st.session_state.tools = result["tools"]
    st.session_state.resources = result["resources"]
    st.session_state.prompts = result["prompts"]
    st.session_state.trace_events = result["trace_events"]
    st.session_state.mcp_connected = True
    st.session_state.connect_error = None


# --- Sidebar ---

with st.sidebar:
    st.title("MCP Learning Lab")
    st.caption("LLM → MCP Client → Server → Tools/Resources/Prompts")

    api_key = get_gemini_api_key()
    if not api_key:
        st.error("Set GEMINI_API_KEY in .env")
        st.code("cp .env.example .env\n# then edit .env and paste your key", language="bash")
        if ENV_FILE:
            st.caption(f"Checked: {ENV_FILE.name} (not found or key empty)")
        else:
            st.caption("No .env or .env.example found in project root")
    else:
        source = ENV_FILE.name if ENV_FILE else "environment"
        st.success(f"Gemini API key loaded ({source})")

    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    st.text(f"Model: {model}")

    st.divider()
    st.subheader("Connection")

    if st.session_state.connect_error:
        st.error(f"Connection failed: {st.session_state.connect_error}")

    connect_label = "Reconnect to MCP Server" if st.session_state.mcp_connected else "Connect to MCP Server"
    if st.button(connect_label, type="primary", use_container_width=True):
        with st.spinner("Starting MCP server..."):
            try:
                existing = st.session_state.get("mcp_client")
                result = AsyncRunner.get().run(_connect_mcp(existing))
                _apply_connection(result)
                st.rerun()
            except Exception as exc:
                st.session_state.mcp_connected = False
                st.session_state.connect_error = str(exc)
                st.rerun()

    if st.session_state.mcp_connected:
        st.success("Server connected")
        st.text(f"Tools: {len(st.session_state.tools)}")
        st.text(f"Resources: {len(st.session_state.resources)}")
        st.text(f"Prompts: {len(st.session_state.prompts)}")

# --- Main tabs ---

tab_chat, tab_workflows, tab_activity, tab_inspector, tab_diagrams = st.tabs(
    ["Chat", "Workflows", "Live Activity", "Inspector", "Diagrams"]
)

# --- Chat tab ---

with tab_chat:
    st.header("Chat with MCP Tools")
    st.caption("Ask questions — watch the Live Activity tab to see each MCP call.")

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("Ask about Docker, weather, or SQL data..."):
        if not st.session_state.get("agent"):
            st.warning("Connect to MCP Server first (sidebar).")
        else:
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                with st.spinner("LLM reasoning + MCP calls..."):
                    try:
                        result = AsyncRunner.get().run(
                            _run_agent(
                                st.session_state.agent,
                                st.session_state.tracer,
                                prompt,
                            )
                        )
                        st.session_state.trace_events = result["trace_events"]
                        st.markdown(result["response"])
                        st.session_state.messages.append(
                            {"role": "assistant", "content": result["response"]}
                        )
                    except Exception as exc:
                        st.error(f"Error: {exc}")

# --- Workflows tab ---

with tab_workflows:
    st.header("Prompt Workflows")
    st.caption(
        "User-controlled MCP prompts — each workflow demonstrates tools + resources + prompts."
    )

    if not st.session_state.get("agent"):
        st.warning("Connect to MCP Server first (sidebar).")
    else:
        col1, col2, col3 = st.columns(3)

        with col1:
            st.subheader("Docker Health Check")
            st.text("Uses: docker://system-info resource + docker tools")
            if st.button("Run Docker Check", key="wf_docker", use_container_width=True):
                with st.spinner("Running docker_health_check workflow..."):
                    run = AsyncRunner.get().run(
                        _run_workflow(
                            st.session_state.agent,
                            st.session_state.tracer,
                            "docker_health_check",
                            resources=["docker://system-info"],
                        )
                    )
                    st.session_state.trace_events = run["trace_events"]
                    result = run["response"]
                    st.session_state.messages.append(
                        {"role": "assistant", "content": f"**Docker Health Check**\n\n{result}"}
                    )
                    st.success("Done — check Live Activity tab")
                    st.markdown(result)

        with col2:
            st.subheader("Weather Trip Advice")
            city = st.text_input("City", value="Bangalore", key="wf_city")
            st.text("Uses: weather://cities resource + get_weather tool")
            if st.button("Run Weather Advice", key="wf_weather", use_container_width=True):
                with st.spinner("Running weather_trip_advice workflow..."):
                    run = AsyncRunner.get().run(
                        _run_workflow(
                            st.session_state.agent,
                            st.session_state.tracer,
                            "weather_trip_advice",
                            {"city": city},
                            resources=["weather://cities"],
                        )
                    )
                    st.session_state.trace_events = run["trace_events"]
                    result = run["response"]
                    st.session_state.messages.append(
                        {"role": "assistant", "content": f"**Weather for {city}**\n\n{result}"}
                    )
                    st.success("Done — check Live Activity tab")
                    st.markdown(result)

        with col3:
            st.subheader("SQL Data Explorer")
            question = st.text_input(
                "Question",
                value="What are the top products by total revenue?",
                key="wf_sql",
            )
            st.text("Uses: sqlite://schema resource + sqlite tools")
            if st.button("Run SQL Explorer", key="wf_sql_btn", use_container_width=True):
                with st.spinner("Running sql_data_explorer workflow..."):
                    run = AsyncRunner.get().run(
                        _run_workflow(
                            st.session_state.agent,
                            st.session_state.tracer,
                            "sql_data_explorer",
                            {"question": question},
                            resources=["sqlite://schema"],
                        )
                    )
                    st.session_state.trace_events = run["trace_events"]
                    result = run["response"]
                    st.session_state.messages.append(
                        {"role": "assistant", "content": f"**SQL: {question}**\n\n{result}"}
                    )
                    st.success("Done — check Live Activity tab")
                    st.markdown(result)

# --- Live Activity tab ---

with tab_activity:
    st.header("Live Activity Trace")
    st.caption("Step-by-step view of LLM → MCP Client → Server → Tools → back to LLM")

    events = st.session_state.trace_events
    render_trace_timeline(events)

    if events:
        st.divider()
        with st.expander("Export full trace as JSON"):
            st.code(
                json.dumps([e.to_dict() for e in events], indent=2, default=str),
                language="json",
            )

# --- Inspector tab ---

with tab_inspector:
    st.header("MCP Server Inspector")
    st.caption("Raw capabilities discovered from the connected MCP server.")

    if not st.session_state.mcp_connected:
        st.warning("Connect to MCP Server first (sidebar).")
    else:
        st.subheader("Tools (model-controlled)")
        for name in st.session_state.tools:
            st.code(name, language=None)

        st.subheader("Resources (app-controlled)")
        for uri in st.session_state.resources:
            st.code(uri, language=None)

        st.subheader("Prompts (user-controlled)")
        for name in st.session_state.prompts:
            st.code(name, language=None)

# --- Diagrams tab ---

with tab_diagrams:
    st.header("Architecture Diagrams")
    st.caption(
        "Architecture diagrams rendered as inline SVG (no external JS). "
        "See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full write-up."
    )

    for i, (title, description, render_fn) in enumerate(DIAGRAM_RENDERERS):
        st.subheader(title)
        st.markdown(description)
        render_fn()
        if i < len(DIAGRAM_RENDERERS) - 1:
            st.divider()
