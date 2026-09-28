"""Gemini agent loop with MCP tool bridge and safe error handling."""

from __future__ import annotations

import os

from google import genai
from google.genai import types

from client.env import get_gemini_api_key
from typing import Any

from client.errors import ErrorCode
from client.mcp_client import MCPClientWrapper
from client.tracer import Tracer

MAX_TOOL_ROUNDS = 5

ERROR_HANDLING_INSTRUCTION = (
    "When a tool or resource result contains ok=false or an error_code field, "
    "explain the failure clearly to the user, mention whether retry might help "
    "(retryable=true), and suggest alternatives. Never pretend a failed tool call succeeded."
)


class GeminiAgent:
    """Orchestrates Gemini LLM calls with MCP tool execution."""

    def __init__(self, mcp_client: MCPClientWrapper, tracer: Tracer) -> None:
        self.mcp = mcp_client
        self.tracer = tracer
        api_key = get_gemini_api_key()
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY not set. Create a .env file in the project root "
                "(copy from .env.example) and add your key from Google AI Studio."
            )
        self.client = genai.Client(api_key=api_key)
        self.model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    async def run(
        self,
        user_message: str,
        preload_resources: list[str] | None = None,
    ) -> str:
        """Run the agent loop: LLM reasons → calls tools → returns final answer."""
        context_parts: list[str] = []
        resource_failures: list[str] = []

        if preload_resources:
            for uri in preload_resources:
                result = await self.mcp.safe_read_resource(uri)
                if result.ok:
                    context_parts.append(f"--- Resource: {uri} ---\n{result.data}")
                else:
                    resource_failures.append(
                        f"--- Resource unavailable: {uri} ---\n{result.to_llm_text()}"
                    )

        system_instruction = (
            "You are a helpful assistant with access to MCP tools for Docker, "
            "weather, and SQLite database queries. Use tools when needed to answer "
            "questions accurately. When you have enough information, provide a "
            "clear final answer.\n\n"
            + ERROR_HANDLING_INSTRUCTION
        )

        if context_parts:
            system_instruction += "\n\nPreloaded context:\n" + "\n\n".join(context_parts)
        if resource_failures:
            system_instruction += "\n\nResource preload warnings:\n" + "\n\n".join(
                resource_failures
            )

        tools = self._build_gemini_tools()
        contents: list[types.Content] = [
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=user_message)],
            )
        ]

        for round_num in range(MAX_TOOL_ROUNDS):
            self.tracer.emit(
                "llm.request",
                "→",
                f"Sending to Gemini (round {round_num + 1})",
                {"model": self.model, "message_preview": user_message[:200]},
            )

            response, llm_error = self._safe_generate_content(
                contents, system_instruction, tools
            )
            if llm_error:
                return llm_error
            if response is None:
                return "The language model request failed."
            if not response.candidates:
                self.tracer.emit(
                    "llm.error",
                    "←",
                    "Gemini returned no candidates",
                    {"error_code": ErrorCode.LLM_EMPTY_RESPONSE},
                )
                return "No response from Gemini."

            candidate = response.candidates[0]
            parts = candidate.content.parts if candidate.content else []

            function_calls = [
                p for p in parts if hasattr(p, "function_call") and p.function_call
            ]
            text_parts = [p.text for p in parts if hasattr(p, "text") and p.text]

            if function_calls:
                reasoning = text_parts[0] if text_parts else "Model decided to call tools."
                self.tracer.emit(
                    "llm.reasoning",
                    "•",
                    reasoning,
                    {"round": round_num + 1, "tool_calls_planned": len(function_calls)},
                )

                contents.append(candidate.content)

                for fc_part in function_calls:
                    fc = fc_part.function_call
                    tool_name = fc.name
                    tool_args = dict(fc.args) if fc.args else {}

                    self.tracer.emit(
                        "llm.tool_request",
                        "•",
                        f"LLM requests tool: {tool_name}",
                        {"tool": tool_name, "arguments": tool_args},
                    )

                    tool_result = await self.mcp.safe_call_tool(tool_name, tool_args)

                    contents.append(
                        types.Content(
                            role="user",
                            parts=[
                                types.Part.from_function_response(
                                    name=tool_name,
                                    response={"result": tool_result.to_llm_text()},
                                )
                            ],
                        )
                    )
            else:
                final_text = "\n".join(text_parts) if text_parts else "No text response."
                self.tracer.emit(
                    "llm.final",
                    "←",
                    "Gemini produced final answer",
                    {"response_preview": final_text[:500]},
                )
                return final_text

        return "Reached maximum tool call rounds. Try a simpler question."

    async def run_prompt_workflow(
        self,
        prompt_name: str,
        prompt_args: dict[str, str] | None = None,
        preload_resources: list[str] | None = None,
    ) -> str:
        """Execute a user-controlled MCP prompt workflow."""
        self.tracer.emit(
            "workflow.start",
            "•",
            f"Starting prompt workflow: {prompt_name}",
            {"prompt": prompt_name, "args": prompt_args or {}},
        )

        prompt_result = await self.mcp.safe_get_prompt(prompt_name, prompt_args)
        if not prompt_result.ok:
            return (
                f"Could not load workflow prompt '{prompt_name}': "
                f"{prompt_result.message} (code: {prompt_result.error_code})"
            )

        return await self.run(prompt_result.data, preload_resources=preload_resources)

    def _safe_generate_content(
        self,
        contents: list[types.Content],
        system_instruction: str,
        tools: list[types.Tool] | None,
    ) -> tuple[Any | None, str | None]:
        """Call Gemini API; return (response, error_message). Never raises."""
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    tools=tools if tools else None,
                ),
            )
            return response, None
        except Exception as exc:
            self.tracer.emit(
                "llm.error",
                "←",
                "Gemini API call failed",
                {"error_code": ErrorCode.LLM_API_ERROR, "message": str(exc)},
            )
            return None, f"The language model is temporarily unavailable: {exc}"

    def _build_gemini_tools(self) -> list[types.Tool] | None:
        declarations = self.mcp.get_gemini_function_declarations()
        if not declarations:
            return None

        function_declarations = []
        for decl in declarations:
            function_declarations.append(
                types.FunctionDeclaration(
                    name=decl["name"],
                    description=decl["description"],
                    parameters=decl["parameters"],
                )
            )

        return [types.Tool(function_declarations=function_declarations)]
