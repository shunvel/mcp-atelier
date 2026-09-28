"""Event tracer for live MCP call visibility."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class TraceEvent:
    """A single traced step in the LLM ↔ MCP flow."""

    event_type: str
    direction: str  # "→" outbound, "←" inbound, "•" internal
    summary: str
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "direction": self.direction,
            "summary": self.summary,
            "payload": self.payload,
            "timestamp": self.timestamp,
        }


class Tracer:
    """Collects trace events and notifies listeners for live UI updates."""

    def __init__(self) -> None:
        self.events: list[TraceEvent] = []
        self._listeners: list[Callable[[TraceEvent], None]] = []

    def on_event(self, callback: Callable[[TraceEvent], None]) -> None:
        self._listeners.append(callback)

    def emit(
        self,
        event_type: str,
        direction: str,
        summary: str,
        payload: dict[str, Any] | None = None,
    ) -> TraceEvent:
        event = TraceEvent(
            event_type=event_type,
            direction=direction,
            summary=summary,
            payload=payload or {},
        )
        self.events.append(event)
        for listener in self._listeners:
            listener(event)
        return event

    def clear(self) -> None:
        self.events.clear()

    def to_json(self) -> str:
        return json.dumps([e.to_dict() for e in self.events], indent=2, default=str)
