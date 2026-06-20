"""
ui/role_view.py - role porting screen.
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
from migration.roles import build_role_rows, port_roles
from net import status_code_of
from ui.widgets import make_guild_panel, make_status_row

SWATCH_SIZE = 22
DEFAULT_ROLE_COLOR_HEX = "#99aab5"  # Discord's "no color" grey


def _discord_color_to_hex(color: int) -> str:
    if not color:
        return DEFAULT_ROLE_COLOR_HEX
    return f"#{color:06x}"


class RoleView(ctk.CTkFrame):
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
        self._role_rows: list = []  # full row dicts from migration.roles
        self._role_vars: dict = {}  # role_id -> ctk.BooleanVar
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
            text="Roles",
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

        # Role list panel
        list_frame = ctk.CTkFrame(body, fg_color=COLORS["surface"], corner_radius=12)
        list_frame.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=(14, 0))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(1, weight=1)

        list_header = ctk.CTkFrame(list_frame, fg_color="transparent")
        list_header.grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 6))
        list_header.columnconfigure(1, weight=1)

        ctk.CTkLabel(
            list_header,
            text="ROLES",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLORS["muted"],
        ).grid(row=0, column=0, sticky="w")

        self.role_count_label = ctk.CTkLabel(
            list_header,
            text="",
            font=ctk.CTkFont(size=11),
            text_color=COLORS["muted"],
        )
        self.role_count_label.grid(row=0, column=1, sticky="w", padx=(10, 0))

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

        self.role_scroll = ctk.CTkScrollableFrame(
            list_frame,
            fg_color=COLORS["card"],
            corner_radius=8,
        )
        self.role_scroll.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 10))
        self.role_scroll.columnconfigure(0, weight=1)

        self.role_placeholder = ctk.CTkLabel(
            self.role_scroll,
            text="Select a Discord and a Fluxer server to load roles.",
            font=ctk.CTkFont(size=12),
            text_color=COLORS["muted"],
        )
        self.role_placeholder.grid(row=0, column=0, padx=10, pady=20, sticky="w")

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
            text="Port selected roles",
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
        d_names: list = []
        f_names: list = []

        self._log("Connecting to Discord...")
        try:
            self._discord_guilds = discord_guilds(self.cfg["discord_token"])
            d_names = [g["name"] for g in self._discord_guilds]
            self._log(f"  {len(self._discord_guilds)} Discord servers found")
            self.after(0, lambda: self.status_row.mark_valid("discord"))
        except Exception as exc:
            self._discord_guilds = []
            if status_code_of(exc) == 401:
                self._log("  Discord token is invalid (401 Unauthorized)")
                self.after(0, lambda: self.status_row.mark_invalid("discord"))
            else:
                self._log(f"  Error: {exc}")

        self._log("Connecting to Fluxer...")
        try:
            self._fluxer_guilds = fluxer_guilds(self.cfg["fluxer_token"])
            f_names = [g["name"] for g in self._fluxer_guilds]
            self._log(f"  {len(self._fluxer_guilds)} Fluxer servers found")
            self.after(0, lambda: self.status_row.mark_valid("fluxer"))
        except Exception as exc:
            self._fluxer_guilds = []
            if status_code_of(exc) == 401:
                self._log("  Fluxer token is invalid (401 Unauthorized)")
                self.after(0, lambda: self.status_row.mark_invalid("fluxer"))
            else:
                self._log(f"  Error: {exc}")

        self.after(0, lambda: self._update_guild_dropdowns(d_names, f_names))

    def _update_guild_dropdowns(self, d_names: list, f_names: list):
        self.discord_guild_cb.configure(values=d_names or ["(none)"], state="normal")
        self.discord_guild_cb.set(d_names[0] if d_names else "")
        self.fluxer_guild_cb.configure(values=f_names or ["(none)"], state="normal")
        self.fluxer_guild_cb.set(f_names[0] if f_names else "")
        self.status_row.reload_btn.configure(state="normal")
        self._maybe_load_roles()

    def _on_guild_select(self, side: str, guild_name: str):
        self._maybe_load_roles()

    # -----------------------------------------------------------------------
    # Role list
    # -----------------------------------------------------------------------

    def _maybe_load_roles(self):
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

        self._clear_role_list()
        self._show_loading_placeholder()

        def load():
            try:
                rows = build_role_rows(
                    self.cfg["discord_token"],
                    self.cfg["fluxer_token"],
                    discord_guild["id"],
                    fluxer_guild["id"],
                )
                self.after(0, lambda: self._populate_role_list(rows))
            except Exception as exc:
                err = str(exc)
                self._log(f"Role load error: {err}")
                self.after(0, self._clear_role_list)

        threading.Thread(target=load, daemon=True).start()

    def _clear_role_list(self):
        for widget in self.role_scroll.winfo_children():
            widget.destroy()
        self._role_vars = {}
        self.role_count_label.configure(text="")

    def _show_loading_placeholder(self):
        ctk.CTkLabel(
            self.role_scroll,
            text="Loading roles...",
            font=ctk.CTkFont(size=12),
            text_color=COLORS["muted"],
        ).grid(row=0, column=0, padx=10, pady=20, sticky="w")

    def _populate_role_list(self, rows: list):
        self._clear_role_list()
        self._role_rows = rows

        if not rows:
            ctk.CTkLabel(
                self.role_scroll,
                text="No roles found on this Discord server.",
                font=ctk.CTkFont(size=12),
                text_color=COLORS["muted"],
            ).grid(row=0, column=0, padx=10, pady=20, sticky="w")
            return

        existing_count = sum(1 for r in rows if r["already_exists"])
        self.role_count_label.configure(
            text=f"{len(rows)} total - {existing_count} already on Fluxer"
        )

        for i, row in enumerate(rows):
            self._add_role_row(row, i)

    def _add_role_row(self, row: dict, index: int):
        already = row["already_exists"]

        cell = ctk.CTkFrame(
            self.role_scroll,
            fg_color=COLORS["surface"] if not already else COLORS["bg"],
            corner_radius=8,
        )
        cell.grid(row=index, column=0, sticky="ew", padx=6, pady=4)
        cell.columnconfigure(2, weight=1)

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
            self._role_vars[row["id"]] = var

        swatch = ctk.CTkFrame(
            cell,
            width=SWATCH_SIZE,
            height=SWATCH_SIZE,
            corner_radius=5,
            fg_color=_discord_color_to_hex(row["color"]),
            border_width=1,
            border_color=COLORS["border"],
        )
        swatch.grid(row=0, column=1, padx=(0, 10), pady=10)
        swatch.grid_propagate(False)

        name_color = COLORS["muted"] if already else COLORS["text"]
        label_text = row["name"] if not already else f"{row['name']} (exists)"
        ctk.CTkLabel(
            cell,
            text=label_text,
            font=ctk.CTkFont(size=12),
            text_color=name_color,
            anchor="w",
        ).grid(row=0, column=2, sticky="ew", padx=(0, 10), pady=10)

    def _select_all(self):
        for var in self._role_vars.values():
            var.set(True)

    def _select_none(self):
        for var in self._role_vars.values():
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
            for row in self._role_rows
            if row["id"] in self._role_vars and self._role_vars[row["id"]].get()
        ]
        if not selected:
            messagebox.showerror("Error", "Please select at least one role to port.")
            return

        self._running = True
        self.start_btn.configure(state="disabled", text="Porting...")
        self.progress_bar.set(0)
        threading.Thread(
            target=self._port_thread, args=(fluxer_guild, selected), daemon=True
        ).start()

    def _port_thread(self, fluxer_guild: dict, selected: list):
        try:
            succeeded, failed = port_roles(
                fluxer_token=self.cfg["fluxer_token"],
                fluxer_guild_id=fluxer_guild["id"],
                roles=selected,
                log_fn=self._log,
                progress_fn=self._on_progress,
            )
            self.after(
                0,
                lambda: messagebox.showinfo(
                    "Done", f"{succeeded} role(s) ported, {failed} failed."
                ),
            )
            # Refresh the list so newly-ported roles grey out.
            self.after(0, self._maybe_load_roles)
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
                state="normal", text="Port selected roles"
            ),
        )
