# Error Handling — Lab Implementation Reference

Technical reference for how **this repository** implements error handling.

**For production guidance** (resilience, operational excellence, observability, LinkedIn-ready checklist): see **[OPERATIONAL_EXCELLENCE.md](OPERATIONAL_EXCELLENCE.md)**.

---

## Code map

| File | Role |
|------|------|
| [`client/errors.py`](../client/errors.py) | `ErrorCode`, `OperationResult`, `detect_business_error()` |
| [`client/mcp_client.py`](../client/mcp_client.py) | `safe_call_tool`, `safe_read_resource`, `safe_get_prompt` |
| [`client/gemini_agent.py`](../client/gemini_agent.py) | Agent loop, partial preload, `_safe_generate_content` |
| [`server/tools_*.py`](../server/) | Soft errors as JSON from tools |

---

## Error models

| Type | Behavior | Agent loop |
|------|----------|------------|
| **Soft error** | JSON `{"error": "..."}` or `OperationResult` with `ok: false` | Continues; LLM sees `function_response` |
| **Hard error** (avoided) | Uncaught exception | Would stop session — prevented by `safe_*` wrappers |

---

## Error codes (`client/errors.py`)

| Code | Meaning |
|------|---------|
| `TOOL_UNAVAILABLE` | Tool call failed (connection, crash) |
| `RESOURCE_UNAVAILABLE` | Resource read failed |
| `PROMPT_UNAVAILABLE` | Prompt fetch failed |
| `MCP_PROTOCOL` | MCP SDK / JSON-RPC error |
| `MCP_TIMEOUT` | Exceeded 30s default timeout |
| `TOOL_BUSINESS_ERROR` | Tool returned `{"error": ...}` or `isError: true` |
| `LLM_API_ERROR` | Gemini API failure |
| `LLM_EMPTY_RESPONSE` | No candidates returned |
| `INTERNAL` | Unexpected failure |

---

## Layer responsibilities

```
UI (Streamlit)       → safe messages; red trace for *_error events
Agent (GeminiAgent)  → safe loop; partial resource preload
MCP Client           → timeouts, no raises, trace events
MCP Server (tools)   → structured JSON for expected failures
Backends             → Docker, Open-Meteo, SQLite
```

---

## Trace events (Live Activity)

| Event | Meaning |
|-------|---------|
| `mcp.tool_result` / `mcp.tool_error` | Tool call outcome |
| `mcp.resource_result` / `mcp.resource_error` | Resource read outcome |
| `mcp.prompt_result` / `mcp.prompt_error` | Prompt fetch outcome |
| `llm.error` | Gemini API failure |

`*_error` events render **red** in the UI.

---

## Test scenarios

| Scenario | Expected |
|----------|----------|
| Docker Desktop stopped | `TOOL_BUSINESS_ERROR` → LLM explains |
| Weather for unknown city | `TOOL_BUSINESS_ERROR` → lists available cities |
| `DELETE FROM orders` | `TOOL_BUSINESS_ERROR` → read-only message |
| Invalid `GEMINI_API_KEY` | `llm.error` → safe chat message |

---

## See also

- **[OPERATIONAL_EXCELLENCE.md](OPERATIONAL_EXCELLENCE.md)** — production patterns, checklist, LinkedIn post drafts
- **[ARCHITECTURE.md](ARCHITECTURE.md)** — system design and diagrams
