"""
api/fluxer.py - Fluxer API calls (guilds, channels, webhooks, emojis).
"""

from __future__ import annotations

import base64
import json
import time

import requests

from config import FLUXER_BASE
from net import SESSION, _get, _post, _raise_for_status_verbose


def _fluxer_headers(token: str) -> dict:
    return {"Authorization": f"Bot {token}", "Content-Type": "application/json"}


# ---------------------------------------------------------------------------
# Guilds & channels
# ---------------------------------------------------------------------------


def fluxer_guilds(token: str) -> list:
    return _get(f"{FLUXER_BASE}/users/@me/guilds", _fluxer_headers(token))


def fluxer_channels(token: str, guild_id: str) -> list:
    channels = _get(f"{FLUXER_BASE}/guilds/{guild_id}/channels", _fluxer_headers(token))
    return sorted(
        [c for c in channels if c.get("type") == 0],
        key=lambda c: c.get("position", 0),
    )


# ---------------------------------------------------------------------------
# Emojis
# ---------------------------------------------------------------------------


def fluxer_guild_emojis(token: str, guild_id: str) -> dict:
    """Return {emoji_name: emoji_id} for all custom emojis in a Fluxer guild."""
    try:
        data = _get(f"{FLUXER_BASE}/guilds/{guild_id}/emojis", _fluxer_headers(token))
        if isinstance(data, list):
            return {e["name"]: e["id"] for e in data if e.get("name") and e.get("id")}
    except Exception:
        pass
    return {}


def fluxer_guild_emojis_raw(token: str, guild_id: str) -> list:
    """Return the raw list of custom emoji objects for a Fluxer guild."""
    try:
        data = _get(f"{FLUXER_BASE}/guilds/{guild_id}/emojis", _fluxer_headers(token))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def fluxer_create_emoji(token: str, guild_id: str, name: str, image_url: str) -> dict:
    """
    Upload a new custom emoji to a Fluxer guild.

    `image_url` is downloaded (e.g. from the Discord CDN) and re-uploaded as a
    base64 data URI, same approach as webhook avatars.
    """
    r = SESSION.get(image_url, timeout=15)
    r.raise_for_status()
    mime = r.headers.get("Content-Type", "image/png").split(";")[0]
    b64 = base64.b64encode(r.content).decode()

    payload = {
        "name": name,
        "image": f"data:{mime};base64,{b64}",
    }
    return _post(
        f"{FLUXER_BASE}/guilds/{guild_id}/emojis", _fluxer_headers(token), payload
    )


# ---------------------------------------------------------------------------
# Roles
# ---------------------------------------------------------------------------


def fluxer_guild_roles_raw(token: str, guild_id: str) -> list:
    """Return the raw list of role objects for a Fluxer guild."""
    try:
        data = _get(f"{FLUXER_BASE}/guilds/{guild_id}/roles", _fluxer_headers(token))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def fluxer_create_role(
    token: str, guild_id: str, name: str, color: int, permissions: str
) -> dict:
    """
    Create a new role on a Fluxer guild with the given name, color, and
    permission bitfield. Discord (and Fluxer, mirroring it) always inserts
    newly created roles directly above @everyone; ordering across multiple
    created roles is fixed up afterwards via fluxer_reorder_roles.
    """
    payload = {
        "name": name,
        "color": color,
        "permissions": permissions,
        "hoist": False,
        "mentionable": False,
    }
    return _post(
        f"{FLUXER_BASE}/guilds/{guild_id}/roles", _fluxer_headers(token), payload
    )


def fluxer_reorder_roles(token: str, guild_id: str, role_id_to_position: dict) -> None:
    payload = [
        {"id": role_id, "position": position}
        for role_id, position in role_id_to_position.items()
    ]
    try:
        r = SESSION.patch(
            f"{FLUXER_BASE}/guilds/{guild_id}/roles",
            headers=_fluxer_headers(token),
            json=payload,
            timeout=25,
        )
        r.raise_for_status()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Webhooks
# ---------------------------------------------------------------------------


def fluxer_channel_webhooks(token: str, channel_id: str) -> list:
    try:
        return _get(
            f"{FLUXER_BASE}/channels/{channel_id}/webhooks", _fluxer_headers(token)
        )
    except Exception:
        return []


def fluxer_create_webhook(
    token: str, channel_id: str, name: str, avatar_url: str | None = None
) -> dict:
    payload: dict = {"name": name[:80]}
    if avatar_url:
        try:
            r = SESSION.get(avatar_url, timeout=10)
            if r.status_code == 200:
                mime = r.headers.get("Content-Type", "image/png").split(";")[0]
                b64 = base64.b64encode(r.content).decode()
                payload["avatar"] = f"data:{mime};base64,{b64}"
        except Exception:
            pass
    return _post(
        f"{FLUXER_BASE}/channels/{channel_id}/webhooks", _fluxer_headers(token), payload
    )


def _webhook_base_payload(username: str | None, avatar_url: str | None) -> dict:
    payload = {}
    if username:
        payload["username"] = username[:80]
    if avatar_url:
        payload["avatar_url"] = avatar_url
    return payload


def fluxer_execute_webhook(
    wh_id: str,
    wh_token: str,
    content: str,
    username: str | None = None,
    avatar_url: str | None = None,
    file_urls: list | None = None,
    retries: int = 8,
) -> None:
    """
    Post a message via a Fluxer webhook.

    Attachments are re-downloaded from the Discord CDN and re-uploaded as
    multipart so they render properly in Fluxer rather than appearing as
    broken links.
    """
    from utils import _MIME_MAP, _download

    url = f"{FLUXER_BASE}/webhooks/{wh_id}/{wh_token}?wait=true"

    # Plain JSON (no attachments)
    if not file_urls:
        payload = _webhook_base_payload(username, avatar_url)
        payload["content"] = content[:2000] if content else "\u200b"

        for attempt in range(retries):
            try:
                r = SESSION.post(
                    url,
                    headers={"Content-Type": "application/json"},
                    json=payload,
                    timeout=25,
                )
                if r.status_code == 429:
                    time.sleep(float(r.json().get("retry_after", 2)) + 0.3)
                    continue
                if r.status_code in (200, 204):
                    return
                _raise_for_status_verbose(r)
            except RuntimeError:
                raise
            except (
                requests.exceptions.ConnectionError,
                requests.exceptions.ChunkedEncodingError,
            ) as exc:
                if attempt == retries - 1:
                    raise RuntimeError(f"Webhook connection failed: {exc}") from exc
                time.sleep(2 ** min(attempt, 5))
        return

    # Multipart (with attachments)
    is_first = True
    for file_url in file_urls:
        try:
            file_bytes, filename = _download(file_url)
        except Exception:
            if is_first:
                fallback = _webhook_base_payload(username, avatar_url)
                fallback["content"] = (content or file_url)[:2000]
                try:
                    SESSION.post(
                        url,
                        headers={"Content-Type": "application/json"},
                        json=fallback,
                        timeout=25,
                    )
                except Exception:
                    pass
            is_first = False
            continue

        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        mime = _MIME_MAP.get(ext, "application/octet-stream")

        part_payload = _webhook_base_payload(username, avatar_url)
        if is_first and content:
            part_payload["content"] = content[:2000]
        part_payload["attachments"] = [{"id": 0, "filename": filename}]

        for attempt in range(retries):
            try:
                r = SESSION.post(
                    url,
                    data={"payload_json": json.dumps(part_payload)},
                    files={"files[0]": (filename, file_bytes, mime)},
                    timeout=60,
                )
                if r.status_code == 429:
                    time.sleep(float(r.json().get("retry_after", 2)) + 0.3)
                    continue
                if r.status_code in (200, 204):
                    break
                _raise_for_status_verbose(r)
            except RuntimeError:
                raise
            except (
                requests.exceptions.ConnectionError,
                requests.exceptions.ChunkedEncodingError,
            ) as exc:
                if attempt == retries - 1:
                    raise RuntimeError(f"Webhook file upload failed: {exc}") from exc
                time.sleep(2 ** min(attempt, 5))

        is_first = False
        time.sleep(0.25)
