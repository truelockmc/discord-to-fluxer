"""
ui/widgets.py - reusable UI components.
"""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk


def make_panel(
    parent,
    title: str,
    col: int,
    on_guild_select: Callable[[str], None],
    colors: dict,
) -> tuple[ctk.CTkComboBox, ctk.CTkComboBox]:
    """
    Build a server/channel selection panel and return (guild_cb, channel_cb).
    """
    frame = ctk.CTkFrame(parent, fg_color=colors["surface"], corner_radius=12)
    frame.grid(
        row=1,
        column=col,
        sticky="nsew",
        padx=(0, 8) if col == 0 else (8, 0),
    )

    ctk.CTkLabel(
        frame,
        text=title,
        font=ctk.CTkFont(size=13, weight="bold"),
        text_color=colors["text"],
    ).pack(anchor="w", padx=16, pady=(14, 4))

    ctk.CTkLabel(
        frame,
        text="Server",
        font=ctk.CTkFont(size=11, weight="bold"),
        text_color=colors["muted"],
    ).pack(anchor="w", padx=16, pady=(4, 2))

    guild_cb = ctk.CTkComboBox(
        frame,
        values=["- not loaded -"],
        fg_color=colors["card"],
        border_color=colors["border"],
        button_color=colors["accent"],
        button_hover_color=colors["accent2"],
        dropdown_fg_color=colors["card"],
        text_color=colors["text"],
        dropdown_text_color=colors["text"],
        font=ctk.CTkFont(size=13),
        state="disabled",
    )
    guild_cb.pack(fill="x", padx=16, pady=(0, 8))
    guild_cb.bind(
        "<<ComboboxSelected>>",
        lambda e, cb=guild_cb: on_guild_select(cb.get()),
    )

    ctk.CTkLabel(
        frame,
        text="Channel",
        font=ctk.CTkFont(size=11, weight="bold"),
        text_color=colors["muted"],
    ).pack(anchor="w", padx=16, pady=(0, 2))

    channel_cb = ctk.CTkComboBox(
        frame,
        values=["- select a server first -"],
        fg_color=colors["card"],
        border_color=colors["border"],
        button_color=colors["accent"],
        button_hover_color=colors["accent2"],
        dropdown_fg_color=colors["card"],
        text_color=colors["text"],
        dropdown_text_color=colors["text"],
        font=ctk.CTkFont(size=13),
        state="disabled",
    )
    channel_cb.pack(fill="x", padx=16, pady=(0, 16))

    return guild_cb, channel_cb
