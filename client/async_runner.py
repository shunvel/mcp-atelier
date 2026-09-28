"""Persistent asyncio loop for Streamlit (avoids MCP client teardown errors)."""

from __future__ import annotations

import asyncio
import threading
from typing import Coroutine, TypeVar

T = TypeVar("T")


class AsyncRunner:
    """Run coroutines on a background event loop (singleton)."""

    _instance: AsyncRunner | None = None

    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._loop.run_forever,
            name="mcp-async-runner",
            daemon=True,
        )
        self._thread.start()

    @classmethod
    def get(cls) -> AsyncRunner:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def run(self, coro: Coroutine[None, None, T]) -> T:
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result()
