"""Structured error envelopes for MCP and LLM operations."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import Any


class ErrorCode(str, Enum):
    """Stable error codes for logging, metrics, and LLM context."""

    TOOL_UNAVAILABLE = "TOOL_UNAVAILABLE"
    RESOURCE_UNAVAILABLE = "RESOURCE_UNAVAILABLE"
    PROMPT_UNAVAILABLE = "PROMPT_UNAVAILABLE"
    MCP_PROTOCOL = "MCP_PROTOCOL"
    MCP_TIMEOUT = "MCP_TIMEOUT"
    TOOL_BUSINESS_ERROR = "TOOL_BUSINESS_ERROR"
    LLM_API_ERROR = "LLM_API_ERROR"
    LLM_EMPTY_RESPONSE = "LLM_EMPTY_RESPONSE"
    INTERNAL = "INTERNAL"


@dataclass
class OperationResult:
    """Result of a safe MCP or LLM operation."""

    ok: bool
    data: str = ""
    error_code: ErrorCode | None = None
    message: str | None = None
    retryable: bool = False
    details: dict[str, Any] | None = None

    def to_llm_text(self) -> str:
        """Serialize for Gemini function_response or context injection."""
        if self.ok:
            return self.data
        payload: dict[str, Any] = {
            "ok": False,
            "error_code": self.error_code,
            "message": self.message or "Operation failed",
            "retryable": self.retryable,
        }
        if self.details:
            payload["details"] = self.details
        return json.dumps(payload, indent=2)

    @staticmethod
    def success(data: str) -> OperationResult:
        return OperationResult(ok=True, data=data)

    @staticmethod
    def failure(
        code: ErrorCode,
        message: str,
        retryable: bool = False,
        details: dict[str, Any] | None = None,
    ) -> OperationResult:
        return OperationResult(
            ok=False,
            error_code=code,
            message=message,
            retryable=retryable,
            details=details,
        )


def detect_business_error(result_text: str) -> OperationResult | None:
    """Detect soft errors returned as JSON from MCP tool handlers."""
    try:
        parsed = json.loads(result_text)
    except json.JSONDecodeError:
        return None

    if not isinstance(parsed, dict):
        return None

    if "error" in parsed:
        return OperationResult.failure(
            ErrorCode.TOOL_BUSINESS_ERROR,
            str(parsed["error"]),
            retryable=False,
            details={k: v for k, v in parsed.items() if k != "error"},
        )
    if parsed.get("ok") is False:
        return OperationResult.failure(
            ErrorCode.TOOL_BUSINESS_ERROR,
            str(parsed.get("message", "Tool reported failure")),
            retryable=bool(parsed.get("retryable", False)),
            details=parsed,
        )
    return None
