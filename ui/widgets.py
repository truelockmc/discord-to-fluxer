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
    channel_label: str = "Channel",
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
        text=channel_label,
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


def make_guild_panel(
    parent,
    title: str,
    col: int,
    on_guild_select: Callable[[str], None],
    colors: dict,
) -> ctk.CTkComboBox:
    """
    Build a server-only selection panel (no channel dropdown) and return the
    guild CTkComboBox. Used by views that operate on a whole guild rather
    than a specific channel (e.g. the emoji porter).
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
    guild_cb.pack(fill="x", padx=16, pady=(0, 16))
    guild_cb.bind(
        "<<ComboboxSelected>>",
        lambda e, cb=guild_cb: on_guild_select(cb.get()),
    )

    return guild_cb


def make_token_row(
    parent,
    colors: dict,
    discord_token: str,
    fluxer_token: str,
    on_load: Callable[[], None],
) -> tuple[ctk.StringVar, ctk.StringVar, ctk.CTkButton]:
    """
    Build the shared "Discord token / Fluxer token / Load servers" row.
    Returns (discord_token_var, fluxer_token_var, load_button).
    """
    token_row = ctk.CTkFrame(parent, fg_color=colors["surface"], corner_radius=12)
    token_row.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 14))
    token_row.columnconfigure((1, 3), weight=1)

    def _label(text, col):
        ctk.CTkLabel(
            token_row,
            text=text,
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=colors["muted"],
        ).grid(row=0, column=col, padx=(16, 4), pady=14, sticky="w")

    _label("DISCORD BOT TOKEN", 0)
    discord_token_var = ctk.StringVar(value=discord_token)
    ctk.CTkEntry(
        token_row,
        textvariable=discord_token_var,
        show="*",
        placeholder_text="Bot token",
        fg_color=colors["card"],
        border_color=colors["border"],
        text_color=colors["text"],
    ).grid(row=0, column=1, padx=(0, 20), pady=14, sticky="ew")

    _label("FLUXER BOT TOKEN", 2)
    fluxer_token_var = ctk.StringVar(value=fluxer_token)
    ctk.CTkEntry(
        token_row,
        textvariable=fluxer_token_var,
        show="*",
        placeholder_text="Bot token",
        fg_color=colors["card"],
        border_color=colors["border"],
        text_color=colors["text"],
    ).grid(row=0, column=3, padx=(0, 16), pady=14, sticky="ew")

    load_btn = ctk.CTkButton(
        token_row,
        text="Load servers",
        width=130,
        fg_color=colors["accent"],
        hover_color=colors["accent2"],
        font=ctk.CTkFont(size=13, weight="bold"),
        command=on_load,
    )
    load_btn.grid(row=0, column=4, padx=(0, 16), pady=14)

    return discord_token_var, fluxer_token_var, load_btn
