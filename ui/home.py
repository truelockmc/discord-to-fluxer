"""
ui/home.py - landing screen: choose what to port (messages or emojis).
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

        btn_row = ctk.CTkFrame(center, fg_color="transparent")
        btn_row.pack()

        self._make_card(
            btn_row,
            "\U0001f4ac",
            "Messages",
            "Copy channel messages\nfrom Discord to Fluxer",
            lambda: self.on_choose("messages"),
            0,
        )
        self._make_card(
            btn_row,
            "\U0001f60a",
            "Emojis",
            "Copy custom emojis\nfrom Discord to Fluxer",
            lambda: self.on_choose("emojis"),
            1,
        )

    def _make_card(self, parent, icon, title, subtitle, command, col):
        card = ctk.CTkFrame(
            parent,
            fg_color=COLORS["surface"],
            corner_radius=16,
            width=220,
            height=220,
            border_width=1,
            border_color=COLORS["border"],
        )
        card.grid(row=0, column=col, padx=14)
        card.grid_propagate(False)

        ctk.CTkLabel(card, text=icon, font=ctk.CTkFont(size=44)).pack(pady=(34, 8))
        ctk.CTkLabel(
            card,
            text=title,
            font=ctk.CTkFont(size=17, weight="bold"),
            text_color=COLORS["text"],
        ).pack()
        ctk.CTkLabel(
            card,
            text=subtitle,
            font=ctk.CTkFont(size=12),
            text_color=COLORS["muted"],
            justify="center",
        ).pack(pady=(6, 0))

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
        for widget in (card,):
            widget.bind("<Button-1>", lambda e: command())
