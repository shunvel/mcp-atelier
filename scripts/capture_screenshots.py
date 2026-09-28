#!/usr/bin/env python3
"""Capture README screenshots from a running Streamlit instance.

Usage:
    # Terminal 1: streamlit run ui/app.py
    # Terminal 2:
    python scripts/capture_screenshots.py

Requires: pip install playwright && playwright install chromium
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "docs" / "images"
BASE_URL = "http://localhost:8501"


async def capture() -> None:
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("Install playwright: pip install playwright && playwright install chromium")
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1440, "height": 900})
        page.set_default_timeout(120_000)

        print(f"Opening {BASE_URL}...")
        await page.goto(BASE_URL, wait_until="networkidle")
        await page.wait_for_timeout(1500)

        # --- 1. Landing / sidebar ---
        print("Capturing overview...")
        await page.screenshot(path=OUTPUT_DIR / "01-overview.png", full_page=False)

        # --- Connect MCP ---
        connect_btn = page.get_by_role("button", name="Connect to MCP Server")
        if await connect_btn.count() == 0:
            connect_btn = page.get_by_role("button", name="Reconnect to MCP Server")
        await connect_btn.click()
        await page.wait_for_selector("text=Server connected", timeout=30_000)
        await page.wait_for_timeout(1000)
        await page.screenshot(path=OUTPUT_DIR / "02-connected.png", full_page=False)

        # --- Chat: ask a quick SQL question (no network-heavy deps) ---
        print("Running chat demo...")
        chat_input = page.get_by_placeholder("Ask about Docker, weather, or SQL data...")
        await chat_input.fill("List all tables in the demo database")
        await chat_input.press("Enter")
        await page.wait_for_selector("text=LLM reasoning", timeout=90_000)
        await page.wait_for_timeout(3000)
        await page.screenshot(path=OUTPUT_DIR / "03-chat.png", full_page=True)

        # --- Live Activity ---
        print("Capturing live activity trace...")
        await page.get_by_role("tab", name="Live Activity").click()
        await page.wait_for_timeout(1500)
        await page.screenshot(path=OUTPUT_DIR / "04-live-activity.png", full_page=True)

        # --- Inspector ---
        print("Capturing inspector...")
        await page.get_by_role("tab", name="Inspector").click()
        await page.wait_for_timeout(1000)
        await page.screenshot(path=OUTPUT_DIR / "05-inspector.png", full_page=True)

        # --- Diagrams ---
        print("Capturing diagrams...")
        await page.get_by_role("tab", name="Diagrams").click()
        await page.wait_for_timeout(1500)
        await page.screenshot(path=OUTPUT_DIR / "06-diagrams.png", full_page=True)

        # --- Workflows ---
        print("Capturing workflows...")
        await page.get_by_role("tab", name="Workflows").click()
        await page.wait_for_timeout(1000)
        await page.screenshot(path=OUTPUT_DIR / "07-workflows.png", full_page=False)

        await browser.close()

    print(f"\nScreenshots saved to {OUTPUT_DIR}/")
    for f in sorted(OUTPUT_DIR.glob("*.png")):
        print(f"  - {f.name}")


if __name__ == "__main__":
    asyncio.run(capture())
