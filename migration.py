"""
migration.py - channel migration logic (no UI dependencies).

Runs in a background thread; communicates progress via callbacks.
"""

from __future__ import annotations

import time
from typing import Callable

from api.discord import discord_messages_all
from api.fluxer import (
    fluxer_channel_webhooks,
    fluxer_create_webhook,
    fluxer_execute_webhook,
    fluxer_guild_emojis,
)
from utils import remap_emojis

LogFn = Callable[[str], None]
ProgressFn = Callable[[int, int], None]  # (current, total)


def migrate_channel(
    discord_token: str,
    fluxer_token: str,
    src_channel: dict,
    dst_channel: dict,
    fluxer_guilds: list,
    fluxer_guild_name: str,
    log_fn: LogFn,
    progress_fn: ProgressFn,
) -> int:
    """
    Copy all messages from a Discord channel to a Fluxer channel.

    Returns the number of messages migrated.
    Raises on unrecoverable errors.
    """
    # 1. Fetch all messages
    log_fn(f"\nFetching messages from #{src_channel['name']}...")
    messages = discord_messages_all(discord_token, src_channel["id"], log_fn)
    total = len(messages)
    log_fn(f"  {total} messages found")

    if total == 0:
        log_fn("No messages to migrate.")
        return 0

    # 2. Load Fluxer emoji map for ID remapping
    fluxer_guild_id = next(
        (g["id"] for g in fluxer_guilds if g["name"] == fluxer_guild_name),
        None,
    )
    emoji_map: dict = {}
    if fluxer_guild_id:
        log_fn("Loading Fluxer emoji list for remapping...")
        emoji_map = fluxer_guild_emojis(fluxer_token, fluxer_guild_id)
        log_fn(f"  {len(emoji_map)} Fluxer emojis found")

    # 3. Load existing webhooks (avoid recreating them on re-runs)
    log_fn(f"\nLoading existing webhooks in #{dst_channel['name']}...")
    existing_webhooks = fluxer_channel_webhooks(fluxer_token, dst_channel["id"])
    webhook_map: dict = {}
    for hook in existing_webhooks:
        name = hook.get("name", "")
        if "[uid:" in name:
            uid = name.split("[uid:")[1].rstrip("]")
            webhook_map[uid] = hook
    log_fn(f"  {len(webhook_map)} existing webhooks found")

    # 4. Send messages
    for i, msg in enumerate(messages):
        author = msg.get("author", {})
        user_id = author.get("id", "unknown")
        username = author.get("global_name") or author.get("username", "Unknown")
        content = remap_emojis(msg.get("content", ""), emoji_map)
        file_urls = [att["url"] for att in msg.get("attachments", []) if att.get("url")]

        # Build avatar URL
        avatar_hash = author.get("avatar")
        avatar_url = None
        if avatar_hash:
            ext = "gif" if avatar_hash.startswith("a_") else "png"
            avatar_url = (
                f"https://cdn.discordapp.com/avatars/{user_id}/{avatar_hash}"
                f".{ext}?size=128"
            )

        # Get or create a per-user webhook
        if user_id not in webhook_map:
            log_fn(f"Creating webhook for {username}...")
            hook = fluxer_create_webhook(
                fluxer_token,
                dst_channel["id"],
                f"{username} [uid:{user_id}]",
                avatar_url,
            )
            webhook_map[user_id] = hook
            time.sleep(0.3)

        hook = webhook_map[user_id]
        wh_id = hook.get("id")
        wh_tk = hook.get("token")

        if not wh_id or not wh_tk:
            log_fn(f"Missing webhook token for {username} -> skipping")
            continue

        fluxer_execute_webhook(
            wh_id,
            wh_tk,
            content,
            username=username,
            avatar_url=avatar_url,
            file_urls=file_urls or None,
        )

        progress_fn(i + 1, total)

        if (i + 1) % 10 == 1:
            log_fn(f"  {i + 1}/{total} messages sent...")

        time.sleep(0.25)

    log_fn(f"\nDone. {total} messages migrated successfully.")
    return total
