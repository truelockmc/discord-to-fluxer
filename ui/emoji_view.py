"""
ui/emoji_view.py - emoji porting screen.

Lets the user pick a Discord guild (source) and a Fluxer guild
(destination), shows every Discord custom emoji in a checkbox grid, greys
out + disables ones that already exist on the Fluxer guild (by name), and
lets the user select / deselect all and port the chosen ones.
"""

from __future__ import annotations

import queue
import threading
from tkinter import messagebox
from typing import Callable

import customtkinter as ctk

from api.discord import discord_guilds
from api.fluxer import fluxer_guilds
from config import COLORS
from migration.emojis import build_emoji_rows, port_emojis
from ui.widgets import make_guild_panel, make_status_row


class EmojiView(ctk.CTkFrame):
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
        self._emoji_rows: list = []  # full row dicts from migration.emojis
        self._emoji_vars: dict = {}  # emoji_id -> ctk.BooleanVar
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

        title_row = ctk.CTkFrame(self, fg_color="transparent")
        title_row.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(
            title_row,
            text="Emojis",
            font=ctk.CTkFont(family="Segoe UI", size=17, weight="bold"),
            text_color=COLORS["text"],
        ).pack(side="left")

        self.status_row = make_status_row(
            title_row,
            COLORS,
            self.cfg.get("discord_token", ""),
            self.cfg.get("fluxer_token", ""),
            on_token_change=self._on_token_change,
            on_reload=self._on_load_servers,
        )
        self.status_row.pack(side="left", padx=(16, 0))

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True)
        body.columnconfigure((0, 1), weight=1, uniform="col")
        body.rowconfigure(1, weight=0)
        body.rowconfigure(2, weight=1)

        self.discord_guild_cb = make_guild_panel(
            body,
            "Discord  -  Source",
            0,
            on_guild_select=lambda name: self._on_guild_select("discord", name),
            colors=COLORS,
        )
        self.fluxer_guild_cb = make_guild_panel(
            body,
            "Fluxer  -  Destination",
            1,
            on_guild_select=lambda name: self._on_guild_select("fluxer", name),
            colors=COLORS,
        )

        # Emoji list panel
        list_frame = ctk.CTkFrame(body, fg_color=COLORS["surface"], corner_radius=12)
        list_frame.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=(14, 0))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(1, weight=1)

        list_header = ctk.CTkFrame(list_frame, fg_color="transparent")
        list_header.grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 6))
        list_header.columnconfigure(1, weight=1)

        ctk.CTkLabel(
            list_header,
            text="EMOJIS",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLORS["muted"],
        ).grid(row=0, column=0, sticky="w")

        self.emoji_count_label = ctk.CTkLabel(
            list_header,
            text="",
            font=ctk.CTkFont(size=11),
            text_color=COLORS["muted"],
        )
        self.emoji_count_label.grid(row=0, column=1, sticky="w", padx=(10, 0))

        select_btns = ctk.CTkFrame(list_header, fg_color="transparent")
        select_btns.grid(row=0, column=2, sticky="e")
        ctk.CTkButton(
            select_btns,
            text="Select all",
            width=90,
            height=26,
            fg_color=COLORS["card"],
            hover_color=COLORS["border"],
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._select_all,
        ).pack(side="left", padx=(0, 6))
        ctk.CTkButton(
            select_btns,
            text="Select none",
            width=90,
            height=26,
            fg_color=COLORS["card"],
            hover_color=COLORS["border"],
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._select_none,
        ).pack(side="left")

        self.emoji_scroll = ctk.CTkScrollableFrame(
            list_frame,
            fg_color=COLORS["card"],
            corner_radius=8,
        )
        self.emoji_scroll.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 10))
        self._set_grid_columns(4)

        self.emoji_placeholder = ctk.CTkLabel(
            self.emoji_scroll,
            text="Select a Discord and a Fluxer server to load emojis.",
            font=ctk.CTkFont(size=12),
            text_color=COLORS["muted"],
        )
        self.emoji_placeholder.grid(row=0, column=0, padx=10, pady=20, sticky="w")

        # Log box
        log_frame = ctk.CTkFrame(body, fg_color=COLORS["surface"], corner_radius=12)
        log_frame.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(14, 0))
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
            height=110,
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
        btn_row.grid(row=4, column=0, columnspan=2, pady=(12, 0))

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
            text="Port selected emojis",
            width=200,
            height=42,
            fg_color=COLORS["success"],
            hover_color="#2d8a50",
            font=ctk.CTkFont(size=15, weight="bold"),
            command=self._on_start,
        )
        self.start_btn.pack(side="left")

    def _set_grid_columns(self, n: int):
        for i in range(n):
            self.emoji_scroll.columnconfigure(i, weight=1, uniform="emoji_col")

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

    def _on_token_change(self, which: str, value: str):
        self.cfg[f"{which}_token"] = value
        self.save_cfg(self.cfg)

    def _on_load_servers(self):
        self._load_servers()

    def _load_servers(self):
        if not self.cfg["discord_token"] or not self.cfg["fluxer_token"]:
            messagebox.showerror("Error", "Please enter both bot tokens.")
            return
        self.status_row.reload_btn.configure(state="disabled")
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
            self.after(0, lambda: self.status_row.reload_btn.configure(state="normal"))

    def _update_guild_dropdowns(self, d_names: list, f_names: list):
        self.discord_guild_cb.configure(values=d_names or ["(none)"], state="normal")
        self.discord_guild_cb.set(d_names[0] if d_names else "")
        self.fluxer_guild_cb.configure(values=f_names or ["(none)"], state="normal")
        self.fluxer_guild_cb.set(f_names[0] if f_names else "")
        self.status_row.reload_btn.configure(state="normal")
        self._maybe_load_emojis()

    def _on_guild_select(self, side: str, guild_name: str):
        self._maybe_load_emojis()

    # -----------------------------------------------------------------------
    # Emoji list
    # -----------------------------------------------------------------------

    def _maybe_load_emojis(self):
        discord_name = self.discord_guild_cb.get()
        fluxer_name = self.fluxer_guild_cb.get()
        discord_guild = next(
            (g for g in self._discord_guilds if g["name"] == discord_name), None
        )
        fluxer_guild = next(
            (g for g in self._fluxer_guilds if g["name"] == fluxer_name), None
        )
        if not discord_guild or not fluxer_guild:
            return

        self._clear_emoji_grid()
        self._show_loading_placeholder()

        def load():
            try:
                rows = build_emoji_rows(
                    self.cfg["discord_token"],
                    self.cfg["fluxer_token"],
                    discord_guild["id"],
                    fluxer_guild["id"],
                )
                self.after(0, lambda: self._populate_emoji_grid(rows))
            except Exception as exc:
                err = str(exc)
                self._log(f"Emoji load error: {err}")
                self.after(0, self._clear_emoji_grid)

        threading.Thread(target=load, daemon=True).start()

    def _clear_emoji_grid(self):
        for widget in self.emoji_scroll.winfo_children():
            widget.destroy()
        self._emoji_vars = {}
        self.emoji_count_label.configure(text="")

    def _show_loading_placeholder(self):
        ctk.CTkLabel(
            self.emoji_scroll,
            text="Loading emojis...",
            font=ctk.CTkFont(size=12),
            text_color=COLORS["muted"],
        ).grid(row=0, column=0, padx=10, pady=20, sticky="w")

    def _populate_emoji_grid(self, rows: list):
        self._clear_emoji_grid()
        self._emoji_rows = rows

        if not rows:
            ctk.CTkLabel(
                self.emoji_scroll,
                text="No custom emojis found on this Discord server.",
                font=ctk.CTkFont(size=12),
                text_color=COLORS["muted"],
            ).grid(row=0, column=0, padx=10, pady=20, sticky="w")
            return

        existing_count = sum(1 for r in rows if r["already_exists"])
        self.emoji_count_label.configure(
            text=f"{len(rows)} total - {existing_count} already on Fluxer"
        )

        cols = 4
        self._set_grid_columns(cols)

        for i, row in enumerate(rows):
            r, c = divmod(i, cols)
            self._add_emoji_cell(row, r, c)

    def _add_emoji_cell(self, row: dict, r: int, c: int):
        already = row["already_exists"]

        cell = ctk.CTkFrame(
            self.emoji_scroll,
            fg_color=COLORS["surface"] if not already else COLORS["bg"],
            corner_radius=8,
        )
        cell.grid(row=r, column=c, sticky="ew", padx=6, pady=6)
        cell.columnconfigure(1, weight=1)

        var = ctk.BooleanVar(value=not already)
        checkbox = ctk.CTkCheckBox(
            cell,
            text="",
            variable=var,
            width=20,
            checkbox_width=20,
            checkbox_height=20,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent2"],
            border_color=COLORS["border"],
            state="disabled" if already else "normal",
        )
        checkbox.grid(row=0, column=0, padx=(10, 4), pady=10)
        if not already:
            self._emoji_vars[row["id"]] = var

        name_color = COLORS["muted"] if already else COLORS["text"]
        label_text = row["name"] if not already else f"{row['name']} (exists)"
        ctk.CTkLabel(
            cell,
            text=label_text,
            font=ctk.CTkFont(size=12),
            text_color=name_color,
            anchor="w",
        ).grid(row=0, column=1, sticky="ew", padx=(0, 10), pady=10)

    def _select_all(self):
        for var in self._emoji_vars.values():
            var.set(True)

    def _select_none(self):
        for var in self._emoji_vars.values():
            var.set(False)

    # -----------------------------------------------------------------------
    # Porting
    # -----------------------------------------------------------------------

    def _on_start(self):
        if self._running:
            return

        fluxer_name = self.fluxer_guild_cb.get()
        fluxer_guild = next(
            (g for g in self._fluxer_guilds if g["name"] == fluxer_name), None
        )
        if not fluxer_guild:
            messagebox.showerror("Error", "Please select a destination Fluxer server.")
            return

        selected = [
            row
            for row in self._emoji_rows
            if row["id"] in self._emoji_vars and self._emoji_vars[row["id"]].get()
        ]
        if not selected:
            messagebox.showerror("Error", "Please select at least one emoji to port.")
            return

        self._running = True
        self.start_btn.configure(state="disabled", text="Porting...")
        self.progress_bar.set(0)
        threading.Thread(
            target=self._port_thread, args=(fluxer_guild, selected), daemon=True
        ).start()

    def _port_thread(self, fluxer_guild: dict, selected: list):
        try:
            succeeded, failed = port_emojis(
                fluxer_token=self.cfg["fluxer_token"],
                fluxer_guild_id=fluxer_guild["id"],
                emojis=selected,
                log_fn=self._log,
                progress_fn=self._on_progress,
            )
            self.after(
                0,
                lambda: messagebox.showinfo(
                    "Done", f"{succeeded} emoji(s) ported, {failed} failed."
                ),
            )
            # Refresh the grid so newly-ported emojis grey out.
            self.after(0, self._maybe_load_emojis)
        except Exception as exc:
            err = str(exc)
            self._log(f"\nError: {err}")
            self.after(0, lambda m=err: messagebox.showerror("Error", m))
        finally:
            self._finish()

    def _on_progress(self, current: int, total: int):
        progress = current / total if total else 0
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
            0,
            lambda: self.start_btn.configure(
                state="normal", text="Port selected emojis"
            ),
        )
