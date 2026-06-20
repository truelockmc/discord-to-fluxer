"""
ui/home.py - landing screen: choose what to port (messages, emojis, ...).
"""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from config import COLORS


class HomeView(ctk.CTkFrame):
    def __init__(self, parent, on_choose: Callable[[str], None]):
        super().__init__(parent, fg_color="transparent")
        self.on_choose = on_choose

        center = ctk.CTkFrame(self, fg_color="transparent")
        center.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(
            center,
            text="What do you want to port?",
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
            text_color=COLORS["text"],
        ).pack(pady=(0, 28))

        grid = ctk.CTkFrame(center, fg_color="transparent")
        grid.pack()

        self._make_card(
            grid,
            "\U0001f4ac",
            "Messages",
            "Copy channel messages\nfrom Discord to Fluxer",
            lambda: self.on_choose("messages"),
            row=0,
            col=0,
        )
        self._make_card(
            grid,
            "\U0001f60a",
            "Emojis",
            "Copy custom emojis\nfrom Discord to Fluxer",
            lambda: self.on_choose("emojis"),
            row=0,
            col=1,
        )
        self._make_card(
            grid,
            "\U0001f3f7\ufe0f",
            "Roles",
            "Copy role names, colors\nand permissions",
            lambda: self.on_choose("roles"),
            row=1,
            col=0,
        )
        self._make_card(
            grid,
            "\U0001f5c2\ufe0f",
            "Channel Structure",
            "Recreate categories and\nchannels with their layout",
            lambda: self.on_choose("channel_structure"),
            row=1,
            col=1,
            enabled=False,
        )

    def _make_card(
        self, parent, icon, title, subtitle, command, row, col, enabled=True
    ):
        card = ctk.CTkFrame(
            parent,
            fg_color=COLORS["surface"],
            corner_radius=16,
            width=220,
            height=220,
            border_width=1,
            border_color=COLORS["border"],
        )
        card.grid(row=row, column=col, padx=14, pady=14)
        card.grid_propagate(False)

        icon_color = COLORS["text"] if enabled else COLORS["muted"]
        title_color = COLORS["text"] if enabled else COLORS["muted"]

        ctk.CTkLabel(
            card, text=icon, font=ctk.CTkFont(size=44), text_color=icon_color
        ).pack(pady=(34, 8))
        ctk.CTkLabel(
            card,
            text=title,
            font=ctk.CTkFont(size=17, weight="bold"),
            text_color=title_color,
        ).pack()
        ctk.CTkLabel(
            card,
            text=subtitle,
            font=ctk.CTkFont(size=12),
            text_color=COLORS["muted"],
            justify="center",
        ).pack(pady=(6, 0))

        if enabled:
            btn = ctk.CTkButton(
                card,
                text="Select",
                width=120,
                fg_color=COLORS["accent"],
                hover_color=COLORS["accent2"],
                font=ctk.CTkFont(size=13, weight="bold"),
                command=command,
            )
            btn.pack(pady=(16, 0))

            # Make the whole card clickable, not just the button.
            card.bind("<Button-1>", lambda e: command())
        else:
            ctk.CTkButton(
                card,
                text="Coming soon",
                width=120,
                fg_color=COLORS["card"],
                hover_color=COLORS["card"],
                text_color=COLORS["muted"],
                font=ctk.CTkFont(size=13, weight="bold"),
                state="disabled",
            ).pack(pady=(16, 0))
