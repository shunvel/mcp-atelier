"""Architecture diagrams as inline SVG (no JS/CDN — works reliably in Streamlit)."""

from __future__ import annotations

import html
from collections.abc import Callable

import streamlit.components.v1 as components

_ARROW_DEF = """
<defs>
  <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5"
    markerWidth="6" markerHeight="6" orient="auto-start-reverse">
    <path d="M 0 0 L 10 5 L 0 10 z" fill="#6b7280"/>
  </marker>
</defs>
"""


def _show(svg: str, height: int) -> None:
    """Embed SVG in a Streamlit HTML component."""
    safe = svg.strip()
    page = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"/></head>
<body style="margin:0;padding:8px;background:#fafafa;overflow:hidden;">
{safe}
</body></html>"""
    components.html(page, height=height, scrolling=False)


def _box(x: float, y: float, w: float, h: float, label: str, stroke: str = "#6366f1") -> str:
    t = html.escape(label)
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="#fff" '
        f'stroke="{stroke}" stroke-width="1.5"/>'
        f'<text x="{x + w / 2}" y="{y + h / 2 + 4}" text-anchor="middle" '
        f'font-family="system-ui,sans-serif" font-size="12" fill="#111827">{t}</text>'
    )


def _line(x1: float, y1: float, x2: float, y2: float, label: str = "") -> str:
    parts = [
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#6b7280" '
        f'stroke-width="1.5" marker-end="url(#arrow)"/>'
    ]
    if label:
        lx, ly = (x1 + x2) / 2, (y1 + y2) / 2 - 6
        parts.append(
            f'<text x="{lx}" y="{ly}" text-anchor="middle" font-size="10" '
            f'fill="#6b7280" font-family="system-ui,sans-serif">{html.escape(label)}</text>'
        )
    return "".join(parts)


def render_system_overview() -> None:
    nodes = [
        (40, 100, 70, 36, "User"),
        (140, 100, 100, 36, "Streamlit UI"),
        (280, 100, 100, 36, "GeminiAgent"),
        (420, 50, 90, 36, "Gemini LLM"),
        (420, 160, 90, 36, "MCP Client"),
        (560, 160, 120, 36, "FastMCP Server"),
        (720, 80, 80, 32, "Docker"),
        (720, 140, 90, 32, "Open-Meteo"),
        (720, 200, 70, 32, "SQLite"),
    ]
    boxes = "".join(_box(x, y, w, h, lbl) for x, y, w, h, lbl in nodes)
    arrows = (
        _line(110, 118, 140, 118)
        + _line(240, 118, 280, 118)
        + _line(380, 118, 420, 68, "function calls")
        + _line(380, 118, 420, 178)
        + _line(510, 178, 560, 178, "stdio JSON-RPC")
        + _line(680, 178, 720, 96)
        + _line(680, 178, 720, 156)
        + _line(680, 178, 720, 216)
    )
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="820" height="260" font-family="system-ui,sans-serif">
{_ARROW_DEF}{boxes}{arrows}</svg>"""
    _show(svg, 280)


def render_end_to_end_lifecycle() -> None:
    steps = [
        ("User", "Ask question in Streamlit"),
        ("GeminiAgent", "Send message + tool schemas to Gemini"),
        ("Gemini LLM", "Returns function_call e.g. get_weather"),
        ("MCP Client", "tools/call over stdio JSON-RPC"),
        ("MCP Server", "Runs Python tool handler"),
        ("Backend", "Docker / Weather API / SQLite"),
        ("Gemini LLM", "Receives result, writes final answer"),
        ("User", "Sees answer + Live Activity trace"),
    ]
    parts = [
        f'<text x="350" y="22" text-anchor="middle" font-size="14" font-weight="600" '
        f'fill="#111827">End-to-End Request Lifecycle</text>'
    ]
    y = 40
    for i, (actor, action) in enumerate(steps):
        parts.append(
            f'<rect x="20" y="{y}" width="130" height="34" rx="4" fill="#fff" '
            f'stroke="#0891b2" stroke-width="1.5"/>'
            f'<text x="85" y="{y + 21}" text-anchor="middle" font-size="11" fill="#111827">'
            f"{html.escape(actor)}</text>"
            f'<text x="170" y="{y + 21}" font-size="11" fill="#374151">'
            f"{html.escape(action)}</text>"
        )
        if i < len(steps) - 1:
            parts.append(
                f'<line x1="85" y1="{y + 34}" x2="85" y2="{y + 48}" stroke="#0891b2" stroke-width="1.5"/>'
                f'<polygon points="85,{y + 48} 80,{y + 42} 90,{y + 42}" fill="#0891b2"/>'
            )
        y += 52
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="700" height="{y + 10}">{"".join(parts)}</svg>'
    _show(svg, min(y + 30, 520))


def render_tools_resources_prompts() -> None:
    groups = [
        ("Tools — LLM decides", "#d97706", 20, ["LLM reads user question", "Picks tool from schema", "mcp.call_tool(name, args)"]),
        ("Resources — App preloads", "#0891b2", 270, ["UI/agent reads URI", "e.g. sqlite://schema", "Injected into LLM context"]),
        ("Prompts — User picks", "#7c3aed", 520, ["Workflow button clicked", "prompts/get template", "LLM follows instructions"]),
    ]
    parts = []
    for title, color, x, items in groups:
        parts.append(
            f'<rect x="{x}" y="20" width="230" height="180" rx="8" fill="#f9fafb" '
            f'stroke="{color}" stroke-width="2"/>'
            f'<text x="{x + 115}" y="44" text-anchor="middle" font-size="13" '
            f'font-weight="600" fill="{color}">{html.escape(title)}</text>'
        )
        for j, item in enumerate(items):
            parts.append(
                f'<text x="{x + 14}" y="{70 + j * 22}" font-size="11" fill="#374151">'
                f"• {html.escape(item)}</text>"
            )
    parts.append(
        '<text x="390" y="230" text-anchor="middle" font-size="11" fill="#6b7280">'
        "All three feed context into the LLM</text>"
    )
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="780" height="250">{"".join(parts)}</svg>'
    _show(svg, 270)


def render_jsonrpc_sequence() -> None:
    messages = [
        ("Client → Server", "initialize", True),
        ("Server → Client", "InitializeResult", False),
        ("Client → Server", "notifications/initialized", True),
        ("Client → Server", "tools/list", True),
        ("Server → Client", "ListToolsResult", False),
        ("Client → Server", "resources/list", True),
        ("Server → Client", "ListResourcesResult", False),
        ("Client → Server", "prompts/list", True),
        ("Server → Client", "ListPromptsResult", False),
        ("Client → Server", "tools/call", True),
        ("Server → Client", "CallToolResult", False),
    ]
    parts = [
        '<text x="310" y="22" text-anchor="middle" font-size="14" font-weight="600">'
        "JSON-RPC over stdio</text>"
    ]
    y = 36
    for direction, method, is_req in messages:
        fill = "#eff6ff" if is_req else "#f0fdf4"
        stroke = "#3b82f6" if is_req else "#22c55e"
        parts.append(
            f'<rect x="20" y="{y}" width="120" height="28" rx="4" fill="{fill}" stroke="{stroke}"/>'
            f'<text x="80" y="{y + 18}" text-anchor="middle" font-size="10">{html.escape(direction)}</text>'
            f'<text x="155" y="{y + 18}" font-size="12" font-family="monospace">{html.escape(method)}</text>'
        )
        y += 36
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="620" height="{y + 10}">{"".join(parts)}</svg>'
    _show(svg, min(y + 20, 480))


def render_gemini_bridge() -> None:
    nodes = [
        (30, 70, 90, 34, "tools/list"),
        (160, 70, 100, 34, "inputSchema"),
        (300, 70, 130, 34, "FunctionDecl"),
        (470, 70, 130, 34, "Gemini tools"),
        (100, 170, 130, 34, "generate_content"),
        (270, 170, 110, 34, "function_call"),
        (420, 170, 110, 34, "mcp.call_tool"),
        (560, 170, 130, 34, "function_response"),
    ]
    boxes = "".join(_box(x, y, w, h, lbl) for x, y, w, h, lbl in nodes)
    arrows = (
        _line(120, 87, 160, 87)
        + _line(260, 87, 300, 87)
        + _line(430, 87, 470, 87)
        + _line(535, 104, 165, 170)
        + _line(230, 187, 270, 187)
        + _line(380, 187, 420, 187)
        + _line(530, 187, 560, 187)
        + _line(625, 170, 165, 110)
    )
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="720" height="240" font-family="system-ui,sans-serif">
{_ARROW_DEF}{boxes}{arrows}</svg>"""
    _show(svg, 260)


DIAGRAM_RENDERERS: list[tuple[str, str, Callable[[], None]]] = [
    ("System Overview", "High-level components and stdio transport.", render_system_overview),
    ("End-to-End Request Lifecycle", "What happens from user question to final answer.", render_end_to_end_lifecycle),
    ("Tools vs Resources vs Prompts", "Who initiates each MCP primitive.", render_tools_resources_prompts),
    ("JSON-RPC over stdio", "Wire protocol messages between client and server.", render_jsonrpc_sequence),
    ("Gemini Function-Calling Bridge", "How MCP tool schemas become Gemini function calls.", render_gemini_bridge),
]
