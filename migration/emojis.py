"""
migration/emojis.py - emoji listing & porting logic (no UI dependencies).

Mirrors the approach of emoji-export.js, but instead of downloading emojis to
disk it uploads them straight to a Fluxer guild via the API.
"""

from __future__ import annotations

from typing import Callable

from api.discord import discord_guild_emojis
from api.fluxer import fluxer_create_emoji, fluxer_guild_emojis_raw
from net import status_code_of

LogFn = Callable[[str], None]
ProgressFn = Callable[[int, int], None]  # (current, total)


def build_emoji_rows(
    discord_token: str, fluxer_token: str, discord_guild_id: str, fluxer_guild_id: str
) -> list[dict]:
    """
    Fetch Discord guild emojis and cross-reference them against the existing
    Fluxer guild emojis.

    Returns a list of rows:
        {
            "id": discord emoji id,
            "name": emoji name,
            "animated": bool,
            "cdn_url": full Discord CDN url for the emoji image,
            "already_exists": bool,  # name already present on the Fluxer guild
        }
    """
    discord_emojis = discord_guild_emojis(discord_token, discord_guild_id)
    fluxer_emojis = fluxer_guild_emojis_raw(fluxer_token, fluxer_guild_id)
    existing_names = {e["name"] for e in fluxer_emojis if e.get("name")}

    rows = []
    for emoji in discord_emojis:
        name = emoji.get("name")
        emoji_id = emoji.get("id")
        if not name or not emoji_id:
            continue
        animated = bool(emoji.get("animated"))
        ext = "gif" if animated else "png"
        cdn_url = (
            f"https://cdn.discordapp.com/emojis/{emoji_id}.{ext}"
            f"?size=128&quality=lossless"
        )
        rows.append(
            {
                "id": emoji_id,
                "name": name,
                "animated": animated,
                "cdn_url": cdn_url,
                "already_exists": name in existing_names,
            }
        )

    rows.sort(key=lambda r: r["name"].lower())
    return rows


def port_emojis(
    fluxer_token: str,
    fluxer_guild_id: str,
    emojis: list[dict],
    log_fn: LogFn,
    progress_fn: ProgressFn,
) -> tuple[int, int]:
    """
    Upload the given emoji rows (as returned by build_emoji_rows, pre-filtered
    to the ones the user selected) to the Fluxer guild.

    Returns (succeeded, failed).
    """
    total = len(emojis)
    succeeded = 0
    failed = 0

    for i, emoji in enumerate(emojis):
        name = emoji["name"]
        try:
            fluxer_create_emoji(fluxer_token, fluxer_guild_id, name, emoji["cdn_url"])
            log_fn(f"  Ported: {name}")
            succeeded += 1
        except Exception as exc:
            if status_code_of(exc) == 403 and succeeded == 0:
                raise
            log_fn(f"  Failed: {name} -> {exc}")
            failed += 1

        progress_fn(i + 1, total)

    log_fn(f"\nDone. {succeeded} ported, {failed} failed.")
    return succeeded, failed
