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


def _open_token_dialog(
    parent,
    colors: dict,
    title: str,
    current_value: str,
    on_save: Callable[[str], None],
):
    """Small popup dialog to view/edit a single bot token."""
    dialog = ctk.CTkToplevel(parent)
    dialog.title(title)
    dialog.geometry("420x160")
    dialog.resizable(False, False)
    dialog.configure(fg_color=colors["bg"])
    dialog.transient(parent.winfo_toplevel())
    dialog.grab_set()

    ctk.CTkLabel(
        dialog,
        text=title,
        font=ctk.CTkFont(size=13, weight="bold"),
        text_color=colors["text"],
    ).pack(anchor="w", padx=20, pady=(20, 6))

    token_var = ctk.StringVar(value=current_value)
    entry = ctk.CTkEntry(
        dialog,
        textvariable=token_var,
        show="*",
        placeholder_text="Bot token",
        fg_color=colors["card"],
        border_color=colors["border"],
        text_color=colors["text"],
        width=380,
    )
    entry.pack(padx=20, pady=(0, 16))
    entry.focus_set()

    btn_row = ctk.CTkFrame(dialog, fg_color="transparent")
    btn_row.pack(padx=20, fill="x")

    def _save():
        on_save(token_var.get().strip())
        dialog.destroy()

    ctk.CTkButton(
        btn_row,
        text="Cancel",
        width=100,
        fg_color=colors["card"],
        hover_color=colors["border"],
        text_color=colors["text"],
        command=dialog.destroy,
    ).pack(side="right")
    ctk.CTkButton(
        btn_row,
        text="Save",
        width=100,
        fg_color=colors["accent"],
        hover_color=colors["accent2"],
        font=ctk.CTkFont(weight="bold"),
        command=_save,
    ).pack(side="right", padx=(0, 8))

    entry.bind("<Return>", lambda e: _save())
    dialog.bind("<Escape>", lambda e: dialog.destroy())


def make_status_row(
    parent,
    colors: dict,
    discord_token: str,
    fluxer_token: str,
    on_token_change: Callable[[str, str], None],
    on_reload: Callable[[], None],
) -> ctk.CTkFrame:

    row = ctk.CTkFrame(parent, fg_color="transparent")

    def _badge_style(has_token: bool) -> dict:
        return (
            {"text": "\u2713", "fg_color": colors["success"], "hover_color": "#2d8a50"}
            if has_token
            else {
                "text": "\u2715",
                "fg_color": colors["danger"],
                "hover_color": "#c63537",
            }
        )

    def _make_badge(
        label: str, has_token: bool, on_click: Callable[[], None]
    ) -> ctk.CTkButton:
        wrap = ctk.CTkFrame(row, fg_color="transparent")
        wrap.pack(side="left", padx=(0, 10))

        ctk.CTkLabel(
            wrap,
            text=label,
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=colors["muted"],
        ).pack(side="left", padx=(0, 6))

        style = _badge_style(has_token)
        badge = ctk.CTkButton(
            wrap,
            text=style["text"],
            width=26,
            height=26,
            corner_radius=13,
            fg_color=style["fg_color"],
            hover_color=style["hover_color"],
            font=ctk.CTkFont(size=13, weight="bold"),
            command=on_click,
        )
        badge.pack(side="left")
        return badge

    def _set_badge(badge: ctk.CTkButton, has_token: bool):
        style = _badge_style(has_token)
        badge.configure(
            text=style["text"],
            fg_color=style["fg_color"],
            hover_color=style["hover_color"],
        )

    state = {"discord": discord_token, "fluxer": fluxer_token}

    def _on_discord_click():
        _open_token_dialog(
            parent,
            colors,
            "Discord bot token",
            state["discord"],
            on_save=lambda v: (
                state.__setitem__("discord", v),
                _set_badge(discord_badge, bool(v)),
                on_token_change("discord", v),
            ),
        )

    def _on_fluxer_click():
        _open_token_dialog(
            parent,
            colors,
            "Fluxer bot token",
            state["fluxer"],
            on_save=lambda v: (
                state.__setitem__("fluxer", v),
                _set_badge(fluxer_badge, bool(v)),
                on_token_change("fluxer", v),
            ),
        )

    discord_badge = _make_badge("DISCORD", bool(discord_token), _on_discord_click)
    fluxer_badge = _make_badge("FLUXER", bool(fluxer_token), _on_fluxer_click)

    reload_btn = ctk.CTkButton(
        row,
        text="\u21bb Reload",
        width=90,
        height=26,
        fg_color=colors["card"],
        hover_color=colors["border"],
        text_color=colors["text"],
        font=ctk.CTkFont(size=11, weight="bold"),
        command=on_reload,
    )
    reload_btn.pack(side="left", padx=(4, 0))

    row.reload_btn = reload_btn
    return row
