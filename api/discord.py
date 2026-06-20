"""
api/discord.py - Discord API calls.
"""

from __future__ import annotations

import time

from config import DISCORD_BASE
from net import _get


def _discord_headers(token: str) -> dict:
    return {"Authorization": f"Bot {token}", "Content-Type": "application/json"}


def discord_guilds(token: str) -> list:
    return _get(f"{DISCORD_BASE}/users/@me/guilds", _discord_headers(token))


def discord_channels(token: str, guild_id: str) -> list:
    channels = _get(
        f"{DISCORD_BASE}/guilds/{guild_id}/channels", _discord_headers(token)
    )
    return sorted(
        [c for c in channels if c.get("type") == 0],
        key=lambda c: c.get("position", 0),
    )


def discord_guild_emojis(token: str, guild_id: str) -> list:
    """Return the list of custom emoji objects for a Discord guild."""
    guild = _get(
        f"{DISCORD_BASE}/guilds/{guild_id}?with_counts=false",
        _discord_headers(token),
    )
    return guild.get("emojis", [])


def discord_messages_all(token: str, channel_id: str, log_fn=None) -> list:
    """Fetch every message in a channel in chronological order."""
    messages, before = [], None
    while True:
        url = f"{DISCORD_BASE}/channels/{channel_id}/messages?limit=100"
        if before:
            url += f"&before={before}"
        batch = _get(url, _discord_headers(token))
        if not batch:
            break
        messages.extend(batch)
        before = batch[-1]["id"]
        if log_fn:
            log_fn(f"  Fetching... {len(messages)} messages loaded")
        if len(batch) < 100:
            break
        time.sleep(0.4)
    messages.reverse()
    return messages
