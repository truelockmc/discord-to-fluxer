"""
ui/messages_view.py - channel message migration screen.
"""

from __future__ import annotations

import queue
import threading
from tkinter import messagebox
from typing import Callable

import customtkinter as ctk

from api.discord import discord_channels, discord_guilds
from api.fluxer import fluxer_channels, fluxer_guilds
from config import COLORS
from migration.messages import migrate_channel
from ui.widgets import make_panel, make_token_row


class MessagesView(ctk.CTkFrame):
    def __init__(
        self,
        parent,
        cfg: dict,
        save_cfg: Callable[[dict], None],
        on_back: Callable[[], None],
    ):
        super().__init__(parent, fg_color="transparent")
        self.cfg = cfg
        self.save_cfg = save_cfg
        self.on_back = on_back

        self.log_queue: queue.Queue = queue.Queue()
        self._discord_guilds: list = []
        self._fluxer_guilds: list = []
        self._discord_channels: list = []
        self._fluxer_channels: list = []
        self._running = False
        self._poll_after_id = None

        self._build_ui()
        self._poll_log()

        if self.cfg["discord_token"] and self.cfg["fluxer_token"]:
            self.after(300, self._load_servers)

    def destroy(self):
        if self._poll_after_id is not None:
            try:
                self.after_cancel(self._poll_after_id)
            except Exception:
                pass
        super().destroy()

    # -----------------------------------------------------------------------
    # UI construction
    # -----------------------------------------------------------------------

    def _build_ui(self):
        back_btn = ctk.CTkButton(
            self,
            text="\u2190 Back",
            width=80,
            fg_color="transparent",
            hover_color=COLORS["card"],
            text_color=COLORS["muted"],
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self.on_back,
        )
        back_btn.pack(anchor="w", pady=(0, 8))

        ctk.CTkLabel(
            self,
            text="Messages",
            font=ctk.CTkFont(family="Segoe UI", size=17, weight="bold"),
            text_color=COLORS["text"],
        ).pack(anchor="w", pady=(0, 12))

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True)
        body.columnconfigure((0, 1), weight=1, uniform="col")
        body.rowconfigure(1, weight=1)

        self.discord_token_var, self.fluxer_token_var, self.load_btn = make_token_row(
            body,
            COLORS,
            self.cfg.get("discord_token", ""),
            self.cfg.get("fluxer_token", ""),
            self._on_load_servers,
        )

        discord_cbs = make_panel(
            body,
            "Discord  -  Source",
            0,
            on_guild_select=lambda name: self._on_guild_select("discord", name),
            colors=COLORS,
        )
        self.discord_guild_cb, self.discord_channel_cb = discord_cbs

        fluxer_cbs = make_panel(
            body,
            "Fluxer  -  Destination",
            1,
            on_guild_select=lambda name: self._on_guild_select("fluxer", name),
            colors=COLORS,
        )
        self.fluxer_guild_cb, self.fluxer_channel_cb = fluxer_cbs

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
        self._poll_after_id = self.after(100, self._poll_log)

    # -----------------------------------------------------------------------
    # Load servers
    # -----------------------------------------------------------------------

    def _on_load_servers(self):
        self.cfg["discord_token"] = self.discord_token_var.get().strip()
        self.cfg["fluxer_token"] = self.fluxer_token_var.get().strip()
        self.save_cfg(self.cfg)
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
        try:
            total = migrate_channel(
                discord_token=self.cfg["discord_token"],
                fluxer_token=self.cfg["fluxer_token"],
                src_channel=src_ch,
                dst_channel=dst_ch,
                fluxer_guilds=self._fluxer_guilds,
                fluxer_guild_name=self.fluxer_guild_cb.get(),
                log_fn=self._log,
                progress_fn=self._on_progress,
            )
            if total > 0:
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

    def _on_progress(self, current: int, total: int):
        progress = current / total
        self.after(
            0,
            lambda p=progress, n=current: (
                self.progress_bar.set(p),
                self.progress_label.configure(text=f"{n}/{total}"),
            ),
        )

    def _finish(self):
        self._running = False
        self.after(
            0, lambda: self.start_btn.configure(state="normal", text="Start migration")
        )
