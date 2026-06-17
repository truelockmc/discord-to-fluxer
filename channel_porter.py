"""
Discord → Fluxer migration tool

Configuration is loaded from a .env file (or environment variables).
Create a .env file next to this script with:

    DISCORD_TOKEN=your_discord_bot_token
    FLUXER_TOKEN=your_fluxer_bot_token

Tokens entered in the UI are saved back to .env on "Load servers".
"""

from __future__ import annotations

import base64
import json
import os
import queue
import re
import threading
import time
from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk
import requests
import requests.adapters

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ENV_FILE = Path(".env")
DISCORD_BASE = "https://discord.com/api/v10"
FLUXER_BASE = "https://api.fluxer.app/v1"
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff")

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

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
    """Persist tokens back to .env, keeping any other variables intact."""
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


# ---------------------------------------------------------------------------
# HTTP session with automatic retries
# ---------------------------------------------------------------------------


def _make_session() -> requests.Session:
    session = requests.Session()
    retry = requests.adapters.Retry(
        total=8,
        backoff_factor=1.5,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
        raise_on_status=False,
    )
    adapter = requests.adapters.HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


SESSION = _make_session()

# ---------------------------------------------------------------------------
# Low-level HTTP helpers
# ---------------------------------------------------------------------------


def _get(url: str, headers: dict, retries: int = 8) -> dict:
    for attempt in range(retries):
        try:
            r = SESSION.get(url, headers=headers, timeout=25)
            if r.status_code == 429:
                time.sleep(float(r.json().get("retry_after", 2)) + 0.3)
                continue
            r.raise_for_status()
            return r.json()
        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.ChunkedEncodingError,
        ) as exc:
            if attempt == retries - 1:
                raise RuntimeError(f"Connection failed: {exc}") from exc
            time.sleep(2 ** min(attempt, 5))
    raise RuntimeError(f"GET failed after {retries} retries: {url}")


def _post(
    url: str, headers: dict, payload: dict | None = None, retries: int = 8
) -> dict:
    for attempt in range(retries):
        try:
            r = SESSION.post(url, headers=headers, json=payload, timeout=25)
            if r.status_code == 429:
                time.sleep(float(r.json().get("retry_after", 2)) + 0.3)
                continue
            if r.status_code in (200, 201, 204):
                try:
                    return r.json()
                except Exception:
                    return {}
            r.raise_for_status()
        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.ChunkedEncodingError,
        ) as exc:
            if attempt == retries - 1:
                raise RuntimeError(f"Connection failed: {exc}") from exc
            time.sleep(2 ** min(attempt, 5))
    raise RuntimeError(f"POST failed after {retries} retries: {url}")


def _discord_headers(token: str) -> dict:
    return {"Authorization": f"Bot {token}", "Content-Type": "application/json"}


def _fluxer_headers(token: str) -> dict:
    return {"Authorization": f"Bot {token}", "Content-Type": "application/json"}


# ---------------------------------------------------------------------------
# Discord API
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Fluxer API
# ---------------------------------------------------------------------------


def fluxer_guilds(token: str) -> list:
    return _get(f"{FLUXER_BASE}/users/@me/guilds", _fluxer_headers(token))


def fluxer_channels(token: str, guild_id: str) -> list:
    channels = _get(f"{FLUXER_BASE}/guilds/{guild_id}/channels", _fluxer_headers(token))
    return sorted(
        [c for c in channels if c.get("type") == 0],
        key=lambda c: c.get("position", 0),
    )


def fluxer_channel_webhooks(token: str, channel_id: str) -> list:
    try:
        return _get(
            f"{FLUXER_BASE}/channels/{channel_id}/webhooks", _fluxer_headers(token)
        )
    except Exception:
        return []


def fluxer_guild_emojis(token: str, guild_id: str) -> dict:
    """Return {emoji_name: emoji_id} for all custom emojis in a Fluxer guild."""
    try:
        data = _get(f"{FLUXER_BASE}/guilds/{guild_id}/emojis", _fluxer_headers(token))
        if isinstance(data, list):
            return {e["name"]: e["id"] for e in data if e.get("name") and e.get("id")}
    except Exception:
        pass
    return {}


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


def _raise_for_status_verbose(r: requests.Response) -> None:
    if r.status_code >= 400:
        try:
            body = r.json()
        except Exception:
            body = r.text[:300]
        raise RuntimeError(f"HTTP {r.status_code}: {body}")


def _webhook_base_payload(username: str | None, avatar_url: str | None) -> dict:
    payload = {}
    if username:
        payload["username"] = username[:80]
    if avatar_url:
        payload["avatar_url"] = avatar_url
    return payload


# ---------------------------------------------------------------------------
# Webhook execution
# ---------------------------------------------------------------------------


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
    url = f"{FLUXER_BASE}/webhooks/{wh_id}/{wh_token}?wait=true"

    # Plain JSON
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

    # Multipart
    is_first = True
    for file_url in file_urls:
        try:
            file_bytes, filename = _download(file_url)
        except Exception:
            # If download fails, send the raw link in the first message
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


# ===========================================================================
#  UI
# ===========================================================================


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Discord -> Fluxer Migrator")
        self.geometry("920x700")
        self.minsize(820, 620)
        self.configure(fg_color=COLORS["bg"])

        self.cfg = load_env()
        self.log_queue: queue.Queue = queue.Queue()

        self._discord_guilds: list = []
        self._fluxer_guilds: list = []
        self._discord_channels: list = []
        self._fluxer_channels: list = []
        self._running = False

        self._build_ui()
        self._poll_log()

        if self.cfg["discord_token"] and self.cfg["fluxer_token"]:
            self.after(300, self._load_servers)

    # -----------------------------------------------------------------------
    # UI construction
    # -----------------------------------------------------------------------

    def _build_ui(self):
        # Header bar
        header = ctk.CTkFrame(
            self, fg_color=COLORS["surface"], corner_radius=0, height=56
        )
        header.pack(fill="x")
        header.pack_propagate(False)
        ctk.CTkLabel(
            header,
            text="  Discord -> Fluxer Migrator",
            font=ctk.CTkFont(family="Segoe UI", size=17, weight="bold"),
            text_color=COLORS["text"],
        ).pack(side="left", padx=20)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=16)
        body.columnconfigure((0, 1), weight=1, uniform="col")
        body.rowconfigure(1, weight=1)

        # Token row
        token_row = ctk.CTkFrame(body, fg_color=COLORS["surface"], corner_radius=12)
        token_row.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 14))
        token_row.columnconfigure((1, 3), weight=1)

        def _label(parent, text, col):
            ctk.CTkLabel(
                parent,
                text=text,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=COLORS["muted"],
            ).grid(row=0, column=col, padx=(16, 4), pady=14, sticky="w")

        _label(token_row, "DISCORD BOT TOKEN", 0)
        self.discord_token_var = ctk.StringVar(value=self.cfg.get("discord_token", ""))
        ctk.CTkEntry(
            token_row,
            textvariable=self.discord_token_var,
            show="*",
            placeholder_text="Bot token",
            fg_color=COLORS["card"],
            border_color=COLORS["border"],
            text_color=COLORS["text"],
        ).grid(row=0, column=1, padx=(0, 20), pady=14, sticky="ew")

        _label(token_row, "FLUXER BOT TOKEN", 2)
        self.fluxer_token_var = ctk.StringVar(value=self.cfg.get("fluxer_token", ""))
        ctk.CTkEntry(
            token_row,
            textvariable=self.fluxer_token_var,
            show="*",
            placeholder_text="Bot token",
            fg_color=COLORS["card"],
            border_color=COLORS["border"],
            text_color=COLORS["text"],
        ).grid(row=0, column=3, padx=(0, 16), pady=14, sticky="ew")

        self.load_btn = ctk.CTkButton(
            token_row,
            text="Load servers",
            width=130,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent2"],
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._on_load_servers,
        )
        self.load_btn.grid(row=0, column=4, padx=(0, 16), pady=14)

        # Server/channel selection panels
        self._make_panel(body, "Discord  -  Source", 0)
        self._make_panel(body, "Fluxer  -  Destination", 1)

        # Log box
        log_frame = ctk.CTkFrame(body, fg_color=COLORS["surface"], corner_radius=12)
        log_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(14, 0))
        log_frame.columnconfigure(0, weight=1)

        log_header = ctk.CTkFrame(log_frame, fg_color="transparent")
        log_header.grid(row=0, column=0, sticky="ew", padx=16, pady=(10, 0))
        ctk.CTkLabel(
            log_header,
            text="LOG",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLORS["muted"],
        ).pack(side="left")
        self.progress_label = ctk.CTkLabel(
            log_header,
            text="",
            font=ctk.CTkFont(size=11),
            text_color=COLORS["warn"],
        )
        self.progress_label.pack(side="right")

        self.log_box = ctk.CTkTextbox(
            log_frame,
            height=155,
            fg_color=COLORS["card"],
            text_color=COLORS["text"],
            font=ctk.CTkFont(family="Consolas", size=12),
            border_width=0,
            corner_radius=8,
        )
        self.log_box.grid(row=1, column=0, sticky="ew", padx=12, pady=(4, 10))
        self.log_box.configure(state="disabled")

        # Start row
        btn_row = ctk.CTkFrame(body, fg_color="transparent")
        btn_row.grid(row=3, column=0, columnspan=2, pady=(12, 0))

        self.progress_bar = ctk.CTkProgressBar(
            btn_row,
            width=360,
            height=6,
            fg_color=COLORS["card"],
            progress_color=COLORS["accent"],
        )
        self.progress_bar.pack(side="left", padx=(0, 16))
        self.progress_bar.set(0)

        self.start_btn = ctk.CTkButton(
            btn_row,
            text="Start migration",
            width=200,
            height=42,
            fg_color=COLORS["success"],
            hover_color="#2d8a50",
            font=ctk.CTkFont(size=15, weight="bold"),
            command=self._on_start,
        )
        self.start_btn.pack(side="left")

    def _make_panel(self, parent, title: str, col: int):
        frame = ctk.CTkFrame(parent, fg_color=COLORS["surface"], corner_radius=12)
        frame.grid(
            row=1,
            column=col,
            sticky="nsew",
            padx=(0, 8) if col == 0 else (8, 0),
        )
        side = "discord" if col == 0 else "fluxer"

        ctk.CTkLabel(
            frame,
            text=title,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=COLORS["text"],
        ).pack(anchor="w", padx=16, pady=(14, 4))

        ctk.CTkLabel(
            frame,
            text="Server",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLORS["muted"],
        ).pack(anchor="w", padx=16, pady=(4, 2))

        guild_cb = ctk.CTkComboBox(
            frame,
            values=["- not loaded -"],
            fg_color=COLORS["card"],
            border_color=COLORS["border"],
            button_color=COLORS["accent"],
            button_hover_color=COLORS["accent2"],
            dropdown_fg_color=COLORS["card"],
            text_color=COLORS["text"],
            dropdown_text_color=COLORS["text"],
            font=ctk.CTkFont(size=13),
            state="disabled",
        )
        guild_cb.pack(fill="x", padx=16, pady=(0, 8))
        guild_cb.bind(
            "<<ComboboxSelected>>",
            lambda e, cb=guild_cb, s=side: self._on_guild_select(s, cb.get()),
        )

        ctk.CTkLabel(
            frame,
            text="Channel",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLORS["muted"],
        ).pack(anchor="w", padx=16, pady=(0, 2))

        channel_cb = ctk.CTkComboBox(
            frame,
            values=["- select a server first -"],
            fg_color=COLORS["card"],
            border_color=COLORS["border"],
            button_color=COLORS["accent"],
            button_hover_color=COLORS["accent2"],
            dropdown_fg_color=COLORS["card"],
            text_color=COLORS["text"],
            dropdown_text_color=COLORS["text"],
            font=ctk.CTkFont(size=13),
            state="disabled",
        )
        channel_cb.pack(fill="x", padx=16, pady=(0, 16))

        if col == 0:
            self.discord_guild_cb = guild_cb
            self.discord_channel_cb = channel_cb
        else:
            self.fluxer_guild_cb = guild_cb
            self.fluxer_channel_cb = channel_cb

    # -----------------------------------------------------------------------
    # Log
    # -----------------------------------------------------------------------

    def _log(self, msg: str):
        self.log_queue.put(msg)

    def _poll_log(self):
        while not self.log_queue.empty():
            msg = self.log_queue.get_nowait()
            self.log_box.configure(state="normal")
            self.log_box.insert("end", msg + "\n")
            self.log_box.see("end")
            self.log_box.configure(state="disabled")
        self.after(100, self._poll_log)

    # -----------------------------------------------------------------------
    # Load servers
    # -----------------------------------------------------------------------

    def _on_load_servers(self):
        self.cfg["discord_token"] = self.discord_token_var.get().strip()
        self.cfg["fluxer_token"] = self.fluxer_token_var.get().strip()
        save_env(self.cfg)
        self._load_servers()

    def _load_servers(self):
        if not self.cfg["discord_token"] or not self.cfg["fluxer_token"]:
            messagebox.showerror("Error", "Please enter both bot tokens.")
            return
        self.load_btn.configure(text="Loading...", state="disabled")
        threading.Thread(target=self._load_servers_thread, daemon=True).start()

    def _load_servers_thread(self):
        try:
            self._log("Connecting to Discord...")
            self._discord_guilds = discord_guilds(self.cfg["discord_token"])
            self._log(f"  {len(self._discord_guilds)} Discord servers found")

            self._log("Connecting to Fluxer...")
            self._fluxer_guilds = fluxer_guilds(self.cfg["fluxer_token"])
            self._log(f"  {len(self._fluxer_guilds)} Fluxer servers found")

            d_names = [g["name"] for g in self._discord_guilds]
            f_names = [g["name"] for g in self._fluxer_guilds]
            self.after(0, lambda: self._update_guild_dropdowns(d_names, f_names))
        except Exception as exc:
            err = str(exc)
            self._log(f"Error: {err}")
            self.after(
                0, lambda: self.load_btn.configure(text="Load servers", state="normal")
            )

    def _update_guild_dropdowns(self, d_names: list, f_names: list):
        self.discord_guild_cb.configure(values=d_names or ["(none)"], state="normal")
        self.discord_guild_cb.set(d_names[0] if d_names else "")
        self.fluxer_guild_cb.configure(values=f_names or ["(none)"], state="normal")
        self.fluxer_guild_cb.set(f_names[0] if f_names else "")
        self.load_btn.configure(text="Reload", state="normal")

        if d_names:
            self._on_guild_select("discord", d_names[0])
        if f_names:
            self._on_guild_select("fluxer", f_names[0])

    def _on_guild_select(self, side: str, guild_name: str):
        guilds_list = self._discord_guilds if side == "discord" else self._fluxer_guilds
        token = (
            self.cfg["discord_token"] if side == "discord" else self.cfg["fluxer_token"]
        )
        fetch_fn = discord_channels if side == "discord" else fluxer_channels
        cb = self.discord_channel_cb if side == "discord" else self.fluxer_channel_cb

        guild = next((g for g in guilds_list if g["name"] == guild_name), None)
        if not guild:
            return

        cb.configure(values=["Loading..."], state="disabled")

        def load():
            try:
                channels = fetch_fn(token, guild["id"])
                names = [f"# {c['name']}" for c in channels]
                if side == "discord":
                    self._discord_channels = channels
                else:
                    self._fluxer_channels = channels
                self.after(
                    0, lambda: cb.configure(values=names or ["(none)"], state="normal")
                )
                self.after(0, lambda: cb.set(names[0] if names else ""))
            except Exception as exc:
                err = str(exc)
                self._log(f"Channel load error ({side}): {err}")

        threading.Thread(target=load, daemon=True).start()

    # -----------------------------------------------------------------------
    # Migration
    # -----------------------------------------------------------------------

    def _get_channel(self, side: str) -> dict | None:
        if side == "discord":
            name = self.discord_channel_cb.get().lstrip("# ")
            return next((c for c in self._discord_channels if c["name"] == name), None)
        else:
            name = self.fluxer_channel_cb.get().lstrip("# ")
            return next((c for c in self._fluxer_channels if c["name"] == name), None)

    def _on_start(self):
        if self._running:
            return
        src = self._get_channel("discord")
        dst = self._get_channel("fluxer")
        if not src or not dst:
            messagebox.showerror(
                "Error", "Please select both a source and destination channel."
            )
            return
        self._running = True
        self.start_btn.configure(state="disabled", text="Migrating...")
        self.progress_bar.set(0)
        threading.Thread(
            target=self._migrate_thread, args=(src, dst), daemon=True
        ).start()

    def _migrate_thread(self, src_ch: dict, dst_ch: dict):
        dtok = self.cfg["discord_token"]
        ftok = self.cfg["fluxer_token"]
        try:
            # 1. Fetch all messages
            self._log(f"\nFetching messages from #{src_ch['name']}...")
            messages = discord_messages_all(dtok, src_ch["id"], self._log)
            total = len(messages)
            self._log(f"  {total} messages found")

            if total == 0:
                self._log("No messages to migrate.")
                return

            # 2. Load Fluxer emoji map for ID remapping
            fluxer_guild_id = next(
                (
                    g["id"]
                    for g in self._fluxer_guilds
                    if g["name"] == self.fluxer_guild_cb.get()
                ),
                None,
            )
            emoji_map: dict = {}
            if fluxer_guild_id:
                self._log("Loading Fluxer emoji list for remapping...")
                emoji_map = fluxer_guild_emojis(ftok, fluxer_guild_id)
                self._log(f"  {len(emoji_map)} Fluxer emojis found")

            # 3. Load existing webhooks
            self._log(f"\nLoading existing webhooks in #{dst_ch['name']}...")
            existing_webhooks = fluxer_channel_webhooks(ftok, dst_ch["id"])
            webhook_map: dict = {}
            for hook in existing_webhooks:
                name = hook.get("name", "")
                if "[uid:" in name:
                    uid = name.split("[uid:")[1].rstrip("]")
                    webhook_map[uid] = hook
            self._log(f"  {len(webhook_map)} existing webhooks found")

            # 4. Send messages
            for i, msg in enumerate(messages):
                author = msg.get("author", {})
                user_id = author.get("id", "unknown")
                username = author.get("global_name") or author.get(
                    "username", "Unknown"
                )
                content = remap_emojis(msg.get("content", ""), emoji_map)
                file_urls = [
                    att["url"] for att in msg.get("attachments", []) if att.get("url")
                ]

                # Build avatar URL
                avatar_hash = author.get("avatar")
                avatar_url = None
                if avatar_hash:
                    ext = "gif" if avatar_hash.startswith("a_") else "png"
                    avatar_url = f"https://cdn.discordapp.com/avatars/{user_id}/{avatar_hash}.{ext}?size=128"

                # Get or create a per-user webhook
                if user_id not in webhook_map:
                    self._log(f"Creating webhook for {username}...")
                    hook = fluxer_create_webhook(
                        ftok, dst_ch["id"], f"{username} [uid:{user_id}]", avatar_url
                    )
                    webhook_map[user_id] = hook
                    time.sleep(0.3)

                hook = webhook_map[user_id]
                wh_id = hook.get("id")
                wh_tk = hook.get("token")

                if not wh_id or not wh_tk:
                    self._log(f"Missing webhook token for {username} -> skipping")
                    continue

                fluxer_execute_webhook(
                    wh_id,
                    wh_tk,
                    content,
                    username=username,
                    avatar_url=avatar_url,
                    file_urls=file_urls or None,
                )

                progress = (i + 1) / total
                snap = i + 1
                self.after(
                    0,
                    lambda p=progress, n=snap: (
                        self.progress_bar.set(p),
                        self.progress_label.configure(text=f"{n}/{total}"),
                    ),
                )

                if snap % 10 == 1:
                    self._log(f"  {snap}/{total} messages sent...")

                time.sleep(0.25)

            self._log(f"\nDone. {total} messages migrated successfully.")
            self.after(
                0,
                lambda: messagebox.showinfo(
                    "Done", f"{total} messages migrated successfully."
                ),
            )

        except Exception as exc:
            err = str(exc)
            self._log(f"\nError: {err}")
            self.after(0, lambda m=err: messagebox.showerror("Error", m))
        finally:
            self._finish()

    def _finish(self):
        self._running = False
        self.after(
            0, lambda: self.start_btn.configure(state="normal", text="Start migration")
        )


if __name__ == "__main__":
    app = App()
    app.mainloop()
