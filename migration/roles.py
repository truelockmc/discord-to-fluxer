"""
migration/roles.py - role listing & porting logic (no UI dependencies).

Copies role name, color, permissions, and relative position from a Discord
guild to a Fluxer guild.
"""

from __future__ import annotations

from typing import Callable

from api.discord import discord_guild_roles
from api.fluxer import fluxer_create_role, fluxer_guild_roles_raw, fluxer_reorder_roles
from net import status_code_of

LogFn = Callable[[str], None]
ProgressFn = Callable[[int, int], None]  # (current, total)


def build_role_rows(
    discord_token: str, fluxer_token: str, discord_guild_id: str, fluxer_guild_id: str
) -> list[dict]:
    """
    Returns a list of rows, ordered the same way Discord shows them
    (highest role first):
        {
            "id": discord role id,
            "name": role name,
            "color": integer color (0 = no color / default),
            "permissions": permission bitfield as a string,
            "position": original Discord position (for ordering after copy),
            "already_exists": bool,
        }
    """
    discord_roles = discord_guild_roles(discord_token, discord_guild_id)
    fluxer_roles = fluxer_guild_roles_raw(fluxer_token, fluxer_guild_id)
    existing = {
        (r.get("name"), r.get("color", 0)) for r in fluxer_roles if r.get("name")
    }

    rows = []
    for role in discord_roles:
        name = role.get("name")
        role_id = role.get("id")
        if not name or not role_id:
            continue
        color = role.get("color", 0) or 0
        rows.append(
            {
                "id": role_id,
                "name": name,
                "color": color,
                "permissions": role.get("permissions", "0"),
                "position": role.get("position", 0),
                "already_exists": (name, color) in existing,
            }
        )

    return rows


def port_roles(
    fluxer_token: str,
    fluxer_guild_id: str,
    roles: list[dict],
    log_fn: LogFn,
    progress_fn: ProgressFn,
) -> tuple[int, int]:
    """
    Create the given role rows (as returned by build_role_rows, pre-filtered
    to the ones the user selected) on the Fluxer guild, then fix up their
    relative order to match the original Discord positions.

    Returns (succeeded, failed).
    """
    total = len(roles)
    succeeded = 0
    failed = 0
    created_ids_in_order: list[str] = []  # highest Discord position first

    # Create highest-position roles first, so if reordering isn't supported the list is not completely wrong
    ordered = sorted(roles, key=lambda r: r["position"], reverse=True)

    for i, role in enumerate(ordered):
        name = role["name"]
        try:
            created = fluxer_create_role(
                fluxer_token,
                fluxer_guild_id,
                name,
                role["color"],
                role["permissions"],
            )
            new_id = created.get("id")
            if new_id:
                created_ids_in_order.append(new_id)
            log_fn(f"  Ported: {name}")
            succeeded += 1
        except Exception as exc:
            if status_code_of(exc) == 403 and succeeded == 0:
                raise
            log_fn(f"  Failed: {name} -> {exc}")
            failed += 1

        progress_fn(i + 1, total)

    if len(created_ids_in_order) > 1:
        # Highest position gets the largest position number, matching how
        # Discord/Fluxer rank roles (higher number = higher in the list).
        top = len(created_ids_in_order)
        positions = {
            role_id: top - idx for idx, role_id in enumerate(created_ids_in_order)
        }
        fluxer_reorder_roles(fluxer_token, fluxer_guild_id, positions)

    log_fn(f"\nDone. {succeeded} ported, {failed} failed.")
    return succeeded, failed
