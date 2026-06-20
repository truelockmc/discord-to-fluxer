"""
utils.py - emoji remapping and file download helpers.
"""

from __future__ import annotations

import re

from net import SESSION

# ---------------------------------------------------------------------------
# Emoji remapping
# ---------------------------------------------------------------------------

_EMOJI_RE = re.compile(r"<(a?):([a-zA-Z0-9_]+):(\d+)>")


def remap_emojis(content: str, fluxer_emoji_map: dict) -> str:
    """Replace Discord custom emoji IDs with the matching Fluxer emoji IDs."""

    def replacer(match):
        animated, name, _old_id = match.group(1), match.group(2), match.group(3)
        new_id = fluxer_emoji_map.get(name)
        return f"<{animated}:{name}:{new_id}>" if new_id else match.group(0)

    return _EMOJI_RE.sub(replacer, content)


# ---------------------------------------------------------------------------
# File download helper
# ---------------------------------------------------------------------------

_MIME_MAP = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "webp": "image/webp",
    "mp4": "video/mp4",
    "mov": "video/quicktime",
    "mp3": "audio/mpeg",
    "ogg": "audio/ogg",
    "pdf": "application/pdf",
}


def _download(url: str) -> tuple[bytes, str]:
    """Download a file and return (content_bytes, filename)."""
    r = SESSION.get(url, timeout=30)
    r.raise_for_status()
    cd = r.headers.get("Content-Disposition", "")
    if "filename=" in cd:
        filename = cd.split("filename=")[-1].strip().strip('"')
    else:
        filename = url.split("?")[0].split("/")[-1] or "file"
    return r.content, filename


def download_image_bytes(url: str, timeout: int = 15) -> bytes:
    """Download raw image bytes from a URL (used for small UI thumbnails)."""
    r = SESSION.get(url, timeout=timeout)
    r.raise_for_status()
    return r.content
