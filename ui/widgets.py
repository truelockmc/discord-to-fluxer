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
        command=on_guild_select,
    )
    guild_cb.pack(fill="x", padx=16, pady=(0, 8))

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
        command=on_guild_select,
    )
    guild_cb.pack(fill="x", padx=16, pady=(0, 16))

    return guild_cb


def _bind_entry_shortcuts(entry: ctk.CTkEntry):

    # Explicitly wire Select All / Copy / Cut / Paste on a CTkEntry.

    def select_all(_event=None):
        entry.select_range(0, "end")
        entry.icursor("end")
        return "break"

    def copy(_event=None):
        try:
            value = entry.get()[entry.index("sel.first") : entry.index("sel.last")]
        except Exception:
            value = entry.get()
        entry.clipboard_clear()
        entry.clipboard_append(value)
        return "break"

    def cut(_event=None):
        copy(_event)
        try:
            entry.delete("sel.first", "sel.last")
        except Exception:
            entry.delete(0, "end")
        return "break"

    def paste(_event=None):
        try:
            clip = entry.clipboard_get()
        except Exception:
            return "break"
        try:
            entry.delete("sel.first", "sel.last")
        except Exception:
            pass
        entry.insert("insert", clip)
        return "break"

    for modifier in ("Control", "Command"):
        entry.bind(f"<{modifier}-a>", select_all)
        entry.bind(f"<{modifier}-A>", select_all)
        entry.bind(f"<{modifier}-c>", copy)
        entry.bind(f"<{modifier}-C>", copy)
        entry.bind(f"<{modifier}-x>", cut)
        entry.bind(f"<{modifier}-X>", cut)
        entry.bind(f"<{modifier}-v>", paste)
        entry.bind(f"<{modifier}-V>", paste)


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

    ctk.CTkLabel(
        dialog,
        text=title,
        font=ctk.CTkFont(size=13, weight="bold"),
        text_color=colors["text"],
    ).pack(anchor="w", padx=20, pady=(20, 6))

    entry_row = ctk.CTkFrame(dialog, fg_color="transparent")
    entry_row.pack(padx=20, pady=(0, 16), fill="x")

    token_var = ctk.StringVar(value=current_value)
    entry = ctk.CTkEntry(
        entry_row,
        textvariable=token_var,
        show="*",
        placeholder_text="Bot token",
        fg_color=colors["card"],
        border_color=colors["border"],
        text_color=colors["text"],
    )
    entry.pack(side="left", fill="x", expand=True)
    _bind_entry_shortcuts(entry)

    visible = {"on": False}

    def _toggle_visibility():
        visible["on"] = not visible["on"]
        entry.configure(show="" if visible["on"] else "*")
        toggle_btn.configure(text="\U0001f648" if visible["on"] else "\U0001f441")

    toggle_btn = ctk.CTkButton(
        entry_row,
        text="\U0001f441",
        width=32,
        height=28,
        fg_color=colors["card"],
        hover_color=colors["border"],
        text_color=colors["text"],
        command=_toggle_visibility,
    )
    toggle_btn.pack(side="left", padx=(6, 0))

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

    # The window must actually be drawn/mapped on screen before grab_set()
    # Force a draw, then focus + grab.
    dialog.update_idletasks()
    dialog.deiconify()
    dialog.lift()
    entry.focus_set()
    dialog.after(50, dialog.grab_set)


def make_status_row(
    parent,
    colors: dict,
    discord_token: str,
    fluxer_token: str,
    on_token_change: Callable[[str, str], None],
    on_reload: Callable[[], None],
) -> ctk.CTkFrame:

    row = ctk.CTkFrame(parent, fg_color="transparent")

    # Badge states:
    #   "empty"      -> no token set                       (red, X)
    #   "unverified" -> token set, not checked against API  (green, check)
    #   "invalid"    -> token set, last API call returned 401 (orange, !)
    def _badge_style(state: str) -> dict:
        if state == "empty":
            return {
                "text": "\u2715",
                "fg_color": colors["danger"],
                "hover_color": "#c63537",
            }
        if state == "invalid":
            return {
                "text": "!",
                "fg_color": colors["warn"],
                "hover_color": "#d68f13",
            }
        return {
            "text": "\u2713",
            "fg_color": colors["success"],
            "hover_color": "#2d8a50",
        }

    def _state_for(has_token: bool) -> str:
        return "unverified" if has_token else "empty"

    def _make_badge(
        label: str, initial_state: str, on_click: Callable[[], None]
    ) -> ctk.CTkButton:
        wrap = ctk.CTkFrame(row, fg_color="transparent")
        wrap.pack(side="left", padx=(0, 10))

        ctk.CTkLabel(
            wrap,
            text=label,
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=colors["muted"],
        ).pack(side="left", padx=(0, 6))

        style = _badge_style(initial_state)
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

    def _set_badge(badge: ctk.CTkButton, state: str):
        style = _badge_style(state)
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
                _set_badge(discord_badge, _state_for(bool(v))),
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
                _set_badge(fluxer_badge, _state_for(bool(v))),
                on_token_change("fluxer", v),
            ),
        )

    discord_badge = _make_badge(
        "DISCORD", _state_for(bool(discord_token)), _on_discord_click
    )
    fluxer_badge = _make_badge(
        "FLUXER", _state_for(bool(fluxer_token)), _on_fluxer_click
    )

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

    def mark_valid(which: str):
        badge = discord_badge if which == "discord" else fluxer_badge
        _set_badge(badge, _state_for(bool(state[which])))

    def mark_invalid(which: str):
        badge = discord_badge if which == "discord" else fluxer_badge
        _set_badge(badge, "invalid")

    row.reload_btn = reload_btn
    row.mark_valid = mark_valid
    row.mark_invalid = mark_invalid
    return row
