"""
config.py - shared constants, colours, and .env helpers.

Pure config module: deliberately has no UI (customtkinter/tkinter) imports.
"""

from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ENV_FILE = Path(".env")
DISCORD_BASE = "https://discord.com/api/v10"
FLUXER_BASE = "https://api.fluxer.app/v1"
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff")

COLORS = {
    "bg": "#0f1117",
    "surface": "#1a1d27",
    "card": "#21253a",
    "border": "#2e3250",
    "accent": "#5865f2",
    "accent2": "#7c5df7",
    "success": "#3ba55d",
    "warn": "#faa61a",
    "danger": "#ed4245",
    "text": "#e3e5ea",
    "muted": "#72767d",
}

# ---------------------------------------------------------------------------
# .env helpers
# ---------------------------------------------------------------------------


def load_env() -> dict:
    """Read .env into a dict, falling back to os.environ."""
    env: dict = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip()
    return {
        "discord_token": env.get("DISCORD_TOKEN")
        or os.environ.get("DISCORD_TOKEN", ""),
        "fluxer_token": env.get("FLUXER_TOKEN") or os.environ.get("FLUXER_TOKEN", ""),
    }


def save_env(cfg: dict) -> None:
    """Persist tokens back to .env."""
    existing: dict = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            existing[key.strip()] = value.strip()

    existing["DISCORD_TOKEN"] = cfg.get("discord_token", "")
    existing["FLUXER_TOKEN"] = cfg.get("fluxer_token", "")

    lines = [f"{k}={v}" for k, v in existing.items()]
    ENV_FILE.write_text("\n".join(lines) + "\n")
