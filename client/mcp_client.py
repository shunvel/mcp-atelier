"""MCP stdio client wrapper with tracing and safe error handling."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from contextlib import AsyncExitStack
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.shared.exceptions import McpError

from client.errors import ErrorCode, OperationResult, detect_business_error
from client.tracer import Tracer

DEFAULT_MCP_TIMEOUT_SECONDS = 30.0


class MCPClientWrapper:
    """Connects to the MCP server over stdio and exposes traced operations."""

    def __init__(self, tracer: Tracer, timeout_seconds: float = DEFAULT_MCP_TIMEOUT_SECONDS) -> None:
        self.tracer = tracer
        self.timeout_seconds = timeout_seconds
        self.session: ClientSession | None = None
        self._exit_stack = AsyncExitStack()
        self.tools: list[Any] = []
        self.resources: list[Any] = []
        self.prompts: list[Any] = []

    async def connect(self) -> None:
        """Start MCP server subprocess and initialize session."""
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        server_cmd = os.getenv("MCP_SERVER_CMD") or f"{sys.executable} -m server.main"
        parts = server_cmd.split()

        self.tracer.emit(
            "session.start",
            "→",
            f"Spawning MCP server: {server_cmd}",
            {"command": server_cmd, "cwd": project_root},
        )

        server_params = StdioServerParameters(
            command=parts[0],
            args=parts[1:],
            env={**os.environ, "PYTHONPATH": project_root},
        )

        stdio_transport = await self._exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        read_stream, write_stream = stdio_transport
        self.session = await self._exit_stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )

        init_result = await self.session.initialize()
        self.tracer.emit(
            "session.initialized",
            "←",
            "MCP handshake complete",
            {
                "server_name": init_result.serverInfo.name if init_result.serverInfo else "unknown",
                "server_version": init_result.serverInfo.version if init_result.serverInfo else "unknown",
                "capabilities": str(init_result.capabilities),
            },
        )

        await self._discover_capabilities()

    async def _discover_capabilities(self) -> None:
        assert self.session is not None

        tools_result = await self.session.list_tools()
        self.tools = tools_result.tools
        self.tracer.emit(
            "mcp.list_tools",
            "←",
            f"Discovered {len(self.tools)} tools",
            {"tools": [t.name for t in self.tools]},
        )

        resources_result = await self.session.list_resources()
        self.resources = resources_result.resources
        self.tracer.emit(
            "mcp.list_resources",
            "←",
            f"Discovered {len(self.resources)} resources",
            {"resources": [r.uri for r in self.resources]},
        )

        prompts_result = await self.session.list_prompts()
        self.prompts = prompts_result.prompts
        self.tracer.emit(
            "mcp.list_prompts",
            "←",
            f"Discovered {len(self.prompts)} prompts",
            {"prompts": [p.name for p in self.prompts]},
        )

    async def safe_call_tool(self, name: str, arguments: dict[str, Any]) -> OperationResult:
        """Call a tool; never raises — returns structured OperationResult."""
        assert self.session is not None

        self.tracer.emit(
            "mcp.call_tool",
            "→",
            f"Calling tool: {name}",
            {"tool": name, "arguments": arguments},
        )

        try:
            result = await asyncio.wait_for(
                self.session.call_tool(name, arguments),
                timeout=self.timeout_seconds,
            )
        except TimeoutError:
            return self._emit_tool_error(
                name,
                ErrorCode.MCP_TIMEOUT,
                f"Tool '{name}' timed out after {self.timeout_seconds}s",
                retryable=True,
            )
        except McpError as exc:
            return self._emit_tool_error(
                name,
                ErrorCode.MCP_PROTOCOL,
                str(exc),
                retryable=False,
            )
        except Exception as exc:
            return self._emit_tool_error(
                name,
                ErrorCode.TOOL_UNAVAILABLE,
                str(exc),
                retryable=False,
            )

        if getattr(result, "isError", False):
            result_text = self._extract_tool_text(result)
            return self._emit_tool_error(
                name,
                ErrorCode.TOOL_BUSINESS_ERROR,
                result_text or "Tool returned isError=true",
                retryable=False,
                result_preview=result_text,
            )

        result_text = self._extract_tool_text(result)
        business_error = detect_business_error(result_text)
        if business_error:
            self.tracer.emit(
                "mcp.tool_error",
                "←",
                f"Tool business error: {name}",
                {
                    "tool": name,
                    "error_code": business_error.error_code,
                    "message": business_error.message,
                    "result": result_text[:2000],
                },
            )
            return business_error

        self.tracer.emit(
            "mcp.tool_result",
            "←",
            f"Tool result: {name}",
            {"tool": name, "result": result_text[:2000]},
        )
        return OperationResult.success(result_text)

    async def safe_read_resource(self, uri: str) -> OperationResult:
        """Read a resource; never raises — returns structured OperationResult."""
        assert self.session is not None

        self.tracer.emit(
            "mcp.read_resource",
            "→",
            f"Reading resource: {uri}",
            {"uri": uri},
        )

        try:
            result = await asyncio.wait_for(
                self.session.read_resource(uri),
                timeout=self.timeout_seconds,
            )
        except TimeoutError:
            return self._emit_resource_error(
                uri,
                ErrorCode.MCP_TIMEOUT,
                f"Resource read timed out after {self.timeout_seconds}s",
                retryable=True,
            )
        except McpError as exc:
            return self._emit_resource_error(
                uri,
                ErrorCode.MCP_PROTOCOL,
                str(exc),
                retryable=False,
            )
        except Exception as exc:
            return self._emit_resource_error(
                uri,
                ErrorCode.RESOURCE_UNAVAILABLE,
                str(exc),
                retryable=False,
            )

        text_parts = []
        for content in result.contents:
            if hasattr(content, "text"):
                text_parts.append(content.text)
        result_text = "\n".join(text_parts)

        business_error = detect_business_error(result_text)
        if business_error:
            self.tracer.emit(
                "mcp.resource_error",
                "←",
                f"Resource business error: {uri}",
                {
                    "uri": uri,
                    "error_code": business_error.error_code,
                    "message": business_error.message,
                },
            )
            return business_error

        self.tracer.emit(
            "mcp.resource_result",
            "←",
            f"Resource content: {uri}",
            {"uri": uri, "content": result_text[:2000]},
        )
        return OperationResult.success(result_text)

    async def safe_get_prompt(
        self, name: str, arguments: dict[str, str] | None = None
    ) -> OperationResult:
        """Fetch a prompt template; never raises — returns structured OperationResult."""
        assert self.session is not None

        self.tracer.emit(
            "mcp.get_prompt",
            "→",
            f"Fetching prompt: {name}",
            {"prompt": name, "arguments": arguments or {}},
        )

        try:
            result = await asyncio.wait_for(
                self.session.get_prompt(name, arguments or {}),
                timeout=self.timeout_seconds,
            )
        except TimeoutError:
            return self._emit_prompt_error(
                name,
                ErrorCode.MCP_TIMEOUT,
                f"Prompt fetch timed out after {self.timeout_seconds}s",
                retryable=True,
            )
        except McpError as exc:
            return self._emit_prompt_error(
                name,
                ErrorCode.MCP_PROTOCOL,
                str(exc),
                retryable=False,
            )
        except Exception as exc:
            return self._emit_prompt_error(
                name,
                ErrorCode.PROMPT_UNAVAILABLE,
                str(exc),
                retryable=False,
            )

        messages_text = []
        for msg in result.messages:
            if hasattr(msg.content, "text"):
                messages_text.append(f"[{msg.role}]: {msg.content.text}")
            else:
                messages_text.append(f"[{msg.role}]: {msg.content}")
        prompt_text = "\n".join(messages_text)

        self.tracer.emit(
            "mcp.prompt_result",
            "←",
            f"Prompt loaded: {name}",
            {"prompt": name, "messages": prompt_text[:2000]},
        )
        return OperationResult.success(prompt_text)

    def _extract_tool_text(self, result: Any) -> str:
        text_parts = []
        for content in result.content:
            if hasattr(content, "text"):
                text_parts.append(content.text)
        if text_parts:
            return "\n".join(text_parts)
        return json.dumps(
            [c.model_dump() if hasattr(c, "model_dump") else str(c) for c in result.content]
        )

    def _emit_tool_error(
        self,
        name: str,
        code: ErrorCode,
        message: str,
        retryable: bool,
        result_preview: str | None = None,
    ) -> OperationResult:
        self.tracer.emit(
            "mcp.tool_error",
            "←",
            f"Tool error: {name}",
            {
                "tool": name,
                "error_code": code,
                "message": message,
                "retryable": retryable,
                "result": (result_preview or "")[:2000],
            },
        )
        return OperationResult.failure(code, message, retryable=retryable)

    def _emit_resource_error(
        self,
        uri: str,
        code: ErrorCode,
        message: str,
        retryable: bool,
    ) -> OperationResult:
        self.tracer.emit(
            "mcp.resource_error",
            "←",
            f"Resource error: {uri}",
            {"uri": uri, "error_code": code, "message": message, "retryable": retryable},
        )
        return OperationResult.failure(code, message, retryable=retryable)

    def _emit_prompt_error(
        self,
        name: str,
        code: ErrorCode,
        message: str,
        retryable: bool,
    ) -> OperationResult:
        self.tracer.emit(
            "mcp.prompt_error",
            "←",
            f"Prompt error: {name}",
            {"prompt": name, "error_code": code, "message": message, "retryable": retryable},
        )
        return OperationResult.failure(code, message, retryable=retryable)

    def get_gemini_function_declarations(self) -> list[dict[str, Any]]:
        """Convert MCP tool schemas to Gemini function declarations."""
        declarations = []
        for tool in self.tools:
            schema = tool.inputSchema if hasattr(tool, "inputSchema") else {}
            declarations.append(
                {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": schema,
                }
            )
        return declarations

    async def close(self) -> None:
        await self._exit_stack.aclose()
