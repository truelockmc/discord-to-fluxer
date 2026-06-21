"""
permissions.py - maps actions to the bot permission they require, and
builds a human-readable message when an action fails due to missing
permissions (HTTP 403).
"""

from __future__ import annotations

from net import status_code_of

_PERMISSION_INFO = {
    "load_discord_guilds": (
        "Discord",
        "access to this server",
        "list the servers the bot can see",
        False,
    ),
    "load_discord_channels": (
        "Discord",
        "View Channels",
        "read the channel list",
        False,
    ),
    "load_discord_emojis": (
        "Discord",
        "Manage Emojis and Stickers",
        "read the server's custom emojis",
        False,
    ),
    "load_emoji_list": (
        "Discord or Fluxer",
        "Manage Emojis and Stickers",
        "read the server's custom emojis",
        False,
    ),
    "load_discord_roles": (
        "Discord",
        "Manage Roles",
        "read the server's roles",
        True,
    ),
    "load_role_list": (
        "Discord or Fluxer",
        "Manage Roles",
        "read the server's roles",
        True,
    ),
    "load_discord_messages": (
        "Discord",
        "Read Message History",
        "read messages in this channel",
        False,
    ),
    "load_fluxer_guilds": (
        "Fluxer",
        "access to this server",
        "list the servers the bot can see",
        False,
    ),
    "load_fluxer_channels": (
        "Fluxer",
        "View Channels",
        "read the channel list",
        False,
    ),
    "load_fluxer_emojis": (
        "Fluxer",
        "Manage Emojis and Stickers",
        "read the server's custom emojis",
        False,
    ),
    "load_fluxer_roles": (
        "Fluxer",
        "Manage Roles",
        "read the server's roles",
        True,
    ),
    "create_fluxer_emoji": (
        "Fluxer",
        "Manage Emojis and Stickers",
        "create new custom emojis",
        False,
    ),
    "create_fluxer_role": (
        "Fluxer",
        "Manage Roles",
        "create new roles",
        True,
    ),
    "reorder_fluxer_roles": (
        "Fluxer",
        "Manage Roles",
        "reorder roles",
        True,
    ),
    "create_fluxer_webhook": (
        "Fluxer",
        "Manage Webhooks",
        "create webhooks used to post messages",
        False,
    ),
    "send_fluxer_webhook_message": (
        "Fluxer",
        "Manage Webhooks",
        "send messages through a webhook",
        False,
    ),
}


def permission_error_message(action: str, exc: Exception) -> str | None:
    """
    If `exc` represents a 403 Forbidden, return a human-readable message
    explaining why the bot was likely refused and what it was needed for.
    Returns None if `exc` isn't a permission error, so callers can fall
    back to their normal generic error handling.
    """
    if status_code_of(exc) != 403:
        return None

    info = _PERMISSION_INFO.get(action)
    if info is None:
        return "The bot doesn't have enough permissions for this action."

    platform, permission, purpose, hierarchy_sensitive = info

    if hierarchy_sensitive:
        return (
            f"The {platform} bot couldn't {purpose}. This usually means it's "
            f'missing the "{permission}" permission, but it can also happen '
            f"even with that permission if the bot's own role isn't placed "
            f"above the role(s) it's trying to manage. Try moving the bot's "
            f"role higher in the role list, or check its permissions, then "
            f"try again."
        )

    return (
        f'The {platform} bot is missing the "{permission}" permission, '
        f"needed to {purpose}. Please grant this permission to the bot "
        f"and try again."
    )
