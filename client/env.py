"""Load project environment variables from .env (with .env.example fallback)."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_project_env() -> Path | None:
    """Load env vars from .env, falling back to .env.example if needed."""
    env_path = PROJECT_ROOT / ".env"
    example_path = PROJECT_ROOT / ".env.example"

    if env_path.exists():
        load_dotenv(env_path, override=True)
        return env_path

    if example_path.exists():
        load_dotenv(example_path, override=True)
        return example_path

    load_dotenv()
    return None


def get_gemini_api_key() -> str:
    """Return trimmed GEMINI_API_KEY or empty string."""
    return os.getenv("GEMINI_API_KEY", "").strip()
