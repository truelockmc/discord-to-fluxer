"""
ui/app.py - main application window.

Acts as a thin shell that swaps between the home screen and the
feature-specific views (messages / emojis). Each view manages its own
state and background threads; the shell only holds the shared cfg dict
(tokens) and handles navigation.
"""

from __future__ import annotations

import customtkinter as ctk

from config import COLORS, load_env, save_env
from ui.emoji_view import EmojiView
from ui.home import HomeView
from ui.messages_view import MessagesView
from ui.role_view import RoleView

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Discord -> Fluxer Migrator")
        self.geometry("960x720")
        self.minsize(860, 640)
        self.configure(fg_color=COLORS["bg"])

        self.cfg = load_env()
        self._current_view = None

        self._header = ctk.CTkFrame(
            self, fg_color=COLORS["surface"], corner_radius=0, height=56
        )
        self._header.pack(fill="x")
        self._header.pack_propagate(False)
        ctk.CTkLabel(
            self._header,
            text="  Discord -> Fluxer Migrator",
            font=ctk.CTkFont(family="Segoe UI", size=17, weight="bold"),
            text_color=COLORS["text"],
        ).pack(side="left", padx=20)

        self._body = ctk.CTkFrame(self, fg_color="transparent")
        self._body.pack(fill="both", expand=True, padx=20, pady=16)

        self._show_home()

    # -----------------------------------------------------------------------
    # Navigation
    # -----------------------------------------------------------------------

    def _save_cfg(self, cfg: dict):
        self.cfg = cfg
        save_env(cfg)

    def _swap_view(self, view: ctk.CTkFrame):
        if self._current_view is not None:
            self._current_view.destroy()
        self._current_view = view
        view.pack(fill="both", expand=True)

    def _show_home(self):
        self._swap_view(HomeView(self._body, on_choose=self._on_choose))

    def _on_choose(self, choice: str):
        if choice == "messages":
            self._swap_view(
                MessagesView(
                    self._body,
                    cfg=self.cfg,
                    save_cfg=self._save_cfg,
                    on_back=self._show_home,
                )
            )
        elif choice == "emojis":
            self._swap_view(
                EmojiView(
                    self._body,
                    cfg=self.cfg,
                    save_cfg=self._save_cfg,
                    on_back=self._show_home,
                )
            )
        elif choice == "roles":
            self._swap_view(
                RoleView(
                    self._body,
                    cfg=self.cfg,
                    save_cfg=self._save_cfg,
                    on_back=self._show_home,
                )
            )
