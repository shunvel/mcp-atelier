# Building Reliable LLM + MCP Agents

**Practical guidance on resilience, operational excellence, and observability**

*For teams shipping AI agents that call tools, APIs, and external systems via MCP (Model Context Protocol) or similar patterns.*

---

## The core problem

Traditional APIs fail with HTTP status codes. **Agent systems fail in messier ways:**

- The LLM picks the wrong tool or bad arguments
- A tool returns success with an error buried in JSON
- One dependency is down and the whole chat session crashes
- You can't tell whether the failure was the model, the MCP server, or Stripe

**Production agents need the same discipline as production microservices** — just applied to a non-deterministic orchestration layer.

---

## Three pillars

| Pillar | Question it answers | What good looks like |
|--------|---------------------|----------------------|
| **Resilience** | What happens when something fails? | One bad tool call doesn't kill the session |
| **Operational excellence** | Can we run this safely at scale? | Predictable timeouts, retries, runbooks |
| **Observability** | Can we debug a bad answer in 5 minutes? | Traces from user message → LLM → tool → result |

---

## 1. Resilience — design for failure, not perfection

### Treat errors as data, not exceptions

**Anti-pattern:** Tool throws → agent crashes → user sees a stack trace.

**Pattern:** Tool returns a structured envelope → agent passes it to the LLM → user gets a helpful explanation.

```json
{
  "ok": false,
  "error_code": "DOCKER_UNAVAILABLE",
  "message": "Cannot connect to Docker daemon",
  "retryable": true,
  "hint": "Ensure Docker Desktop is running"
}
```

The agent loop **continues**. The model explains what went wrong and suggests next steps. This is the single highest-leverage pattern for agent UX.

### Classify before you handle

Not every error deserves a retry. Tag failures at the source:

| Class | Example | Retry? | User message |
|-------|---------|--------|--------------|
| Validation | Invalid input, unknown city | No | Specific + actionable hint |
| Dependency down | DB unreachable, API offline | Limited | "Service temporarily unavailable" |
| Transient | Timeout, 429 rate limit | Yes (backoff) | Generic; auto-retry behind the scenes |
| Auth / config | Missing API key | No | Setup instructions (ops alert) |
| Policy | Blocked SQL write | No | Clear policy explanation |
| Bug | Uncaught exception | No | Generic message + correlation ID |

**Rule:** Users never see stack traces. Operators always see full context in logs.

### Isolate failures by layer

Each layer owns its failures and passes structured results upward:

```
User interface     → safe messages, no raw exceptions
Agent orchestrator → one tool failure ≠ session death
MCP / tool client  → timeouts, protocol errors, isError flag
Tool server        → expected failures as JSON, not throws
Backend services   → real I/O; caught at tool boundary
```

### Partial success beats all-or-nothing

When preloading context (schemas, configs, previews), **don't abort the whole request** if one resource fails.

- Load what you can
- Record warnings for what failed
- Let the agent recover via tools or explain the gap

This mirrors how resilient batch systems handle partial pipeline failures.

### Timeouts everywhere

| Layer | Typical budget |
|-------|----------------|
| Single tool call | 10–60 seconds |
| LLM generation | 30–120 seconds |
| Full user request | 1–3 minutes (hard cap) |
| Agent tool rounds | 3–10 max |

**Without timeouts, one hung dependency blocks the user indefinitely.**

### Retries — surgical, not aggressive

| Signal | Action |
|--------|--------|
| 429 / rate limit | Exponential backoff + jitter |
| 5xx | 2–3 retries |
| 400 / validation | No retry |
| Timeout on read-only tool | One retry if `retryable: true` |

**Never blindly retry writes.** Use idempotency keys or make tools explicitly idempotent.

### Circuit breaker for tool dependencies

After N consecutive failures to the same tool or MCP server:

1. Stop calling it for a cooldown window
2. Tell the user tools are temporarily unavailable
3. Alert ops — something is structurally broken, not flaky

Prevents retry storms and wasted LLM tokens on doomed calls.

---

## 2. Operational excellence — run it like a service

### Stable error codes

Strings like `"Docker unavailable"` are fine for humans. **Codes like `DOCKER_UNAVAILABLE` are for machines.**

Use the same codes across:
- Tool responses
- Logs and metrics
- Runbooks ("when you see `MCP_TIMEOUT`, check …")
- LLM context (so the model can reason about failure type)

### Safe wrappers at the client boundary

Wrap every external call — `call_tool`, `read_resource`, `get_prompt`, LLM API — in a function that:

1. Applies a timeout
2. Catches protocol and transport errors
3. Checks protocol-level error flags (e.g. MCP `isError`)
4. Detects business errors in response payloads
5. **Never raises** into the agent loop
6. Emits a trace event either way

This is boring infrastructure. It's also what separates demos from production.

### Instruct the model on failure semantics

Add explicit system guidance:

> When a tool result contains `ok: false` or an `error_code`, explain the failure clearly, say whether retry might help, and suggest alternatives. Never pretend a failed call succeeded.

Models are good at empathetic error explanation **if you give them structured input.**

### Health checks and connection lifecycle

For MCP servers (especially subprocess / stdio):

- Health check on connect
- Supervised process with auto-restart
- Reconnect with backoff on disconnect
- Fail fast on connect — don't let users chat against a dead server

### Security at the tool boundary

- Validate and sanitize all tool inputs server-side
- Tool allowlists per tenant / role
- Rate limits on expensive or sensitive tools
- Never return secrets in tool results or error messages
- Read-only by default for data tools (e.g. SELECT-only SQL)

### Runbooks per error code

| Code | First action |
|------|--------------|
| `MCP_TIMEOUT` | Check tool server load; increase timeout or fix slow dependency |
| `LLM_API_ERROR` | Check API key, quota, regional outage |
| `TOOL_BUSINESS_ERROR` | Usually user/input issue — check tool logs |
| `INTERNAL` | Page on-call — likely a bug |

---

## 3. Observability — if you can't trace it, you can't ship it

### One request ID, end to end

Generate a `request_id` at the UI or API gateway. Propagate it through:

- Agent loop
- Every LLM call
- Every MCP tool call
- Every log line and span

When a user says "it gave me a wrong answer," you need one ID to reconstruct the full story.

### The minimum viable trace

For each user message, you should be able to replay:

```
1. User input
2. Resources preloaded (success / failure per URI)
3. LLM request (model, round N)
4. LLM reasoning (if any text before tool calls)
5. Tool requested (name + arguments)
6. Tool result OR tool error (code, duration)
7. … repeat …
8. Final LLM answer
```

This is distributed tracing applied to agents. A live timeline in dev becomes OpenTelemetry spans in prod.

### Structured logs

```json
{
  "request_id": "req_8f3a",
  "event": "mcp.tool_error",
  "tool": "get_weather",
  "error_code": "MCP_TIMEOUT",
  "duration_ms": 30012,
  "retryable": true
}
```

### Metrics that matter

| Metric | Why |
|--------|-----|
| Error rate by tool | Which integration is flaky? |
| p95 latency by tool + LLM | Where is slowness? |
| Tool rounds per request | Runaway agent loops? |
| `INTERNAL` error spike | Deploy regression? |
| Token usage per request | Cost control |

### Alerts — signal, not noise

Alert on:
- Spike in `INTERNAL` or `MCP_PROTOCOL` (likely bug or outage)
- Circuit breaker open
- LLM error rate above baseline
- p95 request duration SLO breach

Don't alert on every `TOOL_BUSINESS_ERROR` — that's often user error.

### User-facing vs operator-facing

| Audience | Show |
|----------|------|
| End user | Plain language; optional "reference ID" for support |
| Support | Error code + request ID + timestamp |
| Engineer | Full trace, arguments, raw payloads (redacted) |

---

## Reference architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐     ┌──────────────┐
│   User UI   │────▶│    Agent     │────▶│ MCP Client  │────▶│ Tool Server  │
│  safe msgs  │     │  safe loop   │     │  timeouts   │     │  soft errors │
│  request_id │     │  max rounds  │     │  no raises  │     │  validation  │
└─────────────┘     └──────┬───────┘     └──────┬──────┘     └──────┬───────┘
                           │                    │                    │
                           ▼                    ▼                    ▼
                    ┌──────────────────────────────────────────────────────┐
                    │           Observability (logs · traces · metrics)     │
                    └──────────────────────────────────────────────────────┘
```

---

## Production readiness checklist

Use this before calling an agent "production-ready":

**Resilience**
- [ ] Tools return structured errors for expected failures
- [ ] Agent client wrappers never raise on tool/resource failures
- [ ] Timeouts on tool calls, LLM calls, and full request
- [ ] Max tool rounds capped
- [ ] Retry policy defined (with idempotency rules)
- [ ] Circuit breaker on repeated tool failures
- [ ] Partial success for context preload

**Operational excellence**
- [ ] Stable error codes documented with runbooks
- [ ] System prompt handles `ok: false` results
- [ ] MCP server health check + reconnect
- [ ] Input validation at tool server boundary
- [ ] Rate limits on sensitive tools
- [ ] No secrets in errors or tool output

**Observability**
- [ ] `request_id` propagated end to end
- [ ] Trace: user → LLM → tool → result per round
- [ ] Structured logs with `error_code`, `duration_ms`
- [ ] Metrics: error rate, latency, token usage
- [ ] Alerts on `INTERNAL` spikes and SLO breaches

---

## What we learned building a teaching lab

We built a small MCP + LLM lab to make these patterns concrete:

- **Soft errors** in tools (`{"error": "..."}`) let the agent keep going
- **`safe_call_tool`** converts hard MCP failures into structured results
- **Partial resource preload** avoids failing the whole request
- **Live Activity tracing** is a dev-friendly version of production distributed tracing

The lab code is intentionally simple. Production adds retries, circuit breakers, OpenTelemetry, and multi-tenant controls — but the **mental model is the same**.

Technical deep-dive (lab implementation): [ERROR_HANDLING.md](ERROR_HANDLING.md)

---

*Built as part of [mcp-atelier](../README.md) — open source, MIT licensed.*
