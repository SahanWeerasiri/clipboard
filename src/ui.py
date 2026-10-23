"""Attractive native GTK3 floating window for LightClip.

Features:
- Raycast / Win+V style floating popup with dark glassmorphic styling.
- Zero third-party dependencies (built-in GTK3 + CSS).
- Keyboard & mouse navigation (Arrow keys, Enter to copy, Esc to dismiss, Del to delete).
- Real-time relative timestamps and character/line count badges.
- Smooth scrolling and instant response.
"""

from __future__ import annotations

import html
from typing import Callable, List, Optional

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("Pango", "1.0")
from gi.repository import Gdk, GLib, Gtk, Pango

from src.config import DEFAULT_CONFIG, Config
from src.monitor import format_relative_time
from src.storage import ClipboardStorage, ClipItem

CSS_THEME = b"""
/* LightClip Modern Catppuccin-inspired Dark Theme */
window.lightclip-window {
    background-color: #181825;
    border-radius: 16px;
    border: 1px solid rgba(255, 255, 255, 0.1);
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
}

.header-container {
    background-color: #11111b;
    padding: 12px 16px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 16px 16px 0 0;
}

.title-label {
    font-size: 13px;
    font-weight: 700;
    color: #cdd6f4;
    letter-spacing: 0.5px;
}

.count-badge {
    background-color: rgba(203, 166, 247, 0.12);
    color: #cba6f7;
    font-size: 11px;
    font-weight: 600;
    border-radius: 12px;
    padding: 2px 8px;
    border: 1px solid rgba(203, 166, 247, 0.25);
}

.clear-btn {
    background-color: rgba(243, 139, 168, 0.12);
    color: #f38ba8;
    border: 1px solid rgba(243, 139, 168, 0.25);
    border-radius: 8px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 600;
    transition: all 120ms ease;
}

.clear-btn:hover {
    background-color: #f38ba8;
    color: #11111b;
    border-color: #f38ba8;
}

.close-btn {
    background-color: transparent;
    color: #6c7086;
    border: none;
    border-radius: 8px;
    padding: 2px 6px;
    font-size: 12px;
}

.close-btn:hover {
    background-color: rgba(255, 255, 255, 0.1);
    color: #cdd6f4;
}

/* Card list */
list.clip-list {
    background-color: transparent;
    border: none;
    padding: 6px 4px;
}

row.clip-row {
    background-color: #1e1e2e;
    border-radius: 10px;
    margin: 3px 8px;
    padding: 8px 12px;
    border: 1px solid rgba(255, 255, 255, 0.04);
    transition: background-color 100ms ease, border 100ms ease;
}

row.clip-row:hover {
    background-color: #313244;
    border-color: rgba(203, 166, 247, 0.3);
}

row.clip-row:selected {
    background-color: #313244;
    border-left: 3px solid #cba6f7;
    border-color: rgba(203, 166, 247, 0.5);
}

.clip-text {
    font-family: 'Inter', 'Ubuntu', 'DejaVu Sans', sans-serif;
    font-size: 12px;
    color: #cdd6f4;
}

.pill-info {
    font-size: 10px;
    color: #9399b2;
    background-color: rgba(255, 255, 255, 0.06);
    border-radius: 6px;
    padding: 1px 6px;
}

.pill-time {
    font-size: 10px;
    color: #6c7086;
}

.copy-hint {
    font-size: 11px;
    color: #cba6f7;
    font-weight: 700;
}

/* Empty State */
.empty-box {
    padding: 40px 20px;
}

.empty-title {
    font-size: 14px;
    font-weight: 700;
    color: #a6adc8;
}

.empty-subtitle {
    font-size: 12px;
    color: #6c7086;
}

/* Footer keyboard hints */
.footer-bar {
    background-color: #11111b;
    padding: 8px 14px;
    border-top: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 0 0 16px 16px;
}

.footer-hint {
    font-size: 10px;
    color: #6c7086;
}

/* Scrollbar */
scrollbar slider {
    background-color: rgba(255, 255, 255, 0.15);
    border-radius: 10px;
    min-width: 4px;
}

scrollbar slider:hover {
    background-color: rgba(203, 166, 247, 0.5);
}
"""


def apply_theme() -> None:
    """Register custom CSS styles into the GTK display screen."""
    provider = Gtk.CssProvider()
    provider.load_from_data(CSS_THEME)
    screen = Gdk.Screen.get_default()
    if screen:
        Gtk.StyleContext.add_provider_for_screen(
            screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )


class ClipRow(Gtk.ListBoxRow):
    """A visually rich clipboard card item."""

    def __init__(self, item: ClipItem) -> None:
        super().__init__()
        self.item = item
        self.get_style_context().add_class("clip-row")

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)

        # Snippet preview label
        preview_text = item.content.strip()
        label = Gtk.Label()
        label.set_line_wrap(True)
        label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        label.set_ellipsize(Pango.EllipsizeMode.END)
        label.set_max_width_chars(45)
        label.set_lines(3)
        label.set_xalign(0.0)
        label.get_style_context().add_class("clip-text")

        # Clean preview text
        label.set_text(preview_text)
        box.pack_start(label, True, True, 0)

        # Bottom metadata row
        meta_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        # Type/size pill badge
        info_text = f"{item.line_count} lines" if item.line_count > 1 else f"{item.char_count} chars"
        info_label = Gtk.Label(label=info_text)
        info_label.get_style_context().add_class("pill-info")
        meta_box.pack_start(info_label, False, False, 0)

        # Relative time label
        time_label = Gtk.Label(label=format_relative_time(item.updated_at))
        time_label.get_style_context().add_class("pill-time")
        meta_box.pack_start(time_label, False, False, 0)

        # Right side copy icon/hint
        copy_hint = Gtk.Label(label="↵ Copy")
        copy_hint.get_style_context().add_class("copy-hint")
        meta_box.pack_end(copy_hint, False, False, 0)

        box.pack_start(meta_box, False, False, 0)
        self.add(box)


class ClipboardWindow(Gtk.Window):
    """Main floating clipboard manager window."""

    def __init__(
        self,
        storage: ClipboardStorage,
        on_copy: Optional[Callable[[str], None]] = None,
        config: Config = DEFAULT_CONFIG,
    ) -> None:
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.storage = storage
        self.on_copy = on_copy
        self.config = config

        self._setup_window_properties()
        self._build_ui()
        self.refresh_list()

    def _setup_window_properties(self) -> None:
        """Configure window decorations, size, and window manager hints."""
        self.set_title("LightClip")
        self.set_decorated(False)
        self.set_default_size(self.config.window_width, self.config.window_height)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_skip_taskbar_hint(True)
        self.set_keep_above(True)
        self.get_style_context().add_class("lightclip-window")

        # Enable transparency if compositor supports RGBA
        screen = self.get_screen()
        if screen:
            visual = screen.get_rgba_visual()
            if visual and screen.is_composited():
                self.set_visual(visual)
        self.set_app_paintable(True)

        # Connect window events
        self.connect("key-press-event", self._on_key_press)
        self.connect("focus-out-event", self._on_focus_out)

    def _build_ui(self) -> None:
        """Construct the window layout and widgets."""
        root_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add(root_box)

        # --- Header ---
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        header.get_style_context().add_class("header-container")

        # Draggable header
        header.connect("button-press-event", self._on_header_drag)

        title_label = Gtk.Label(label="📋 LightClip")
        title_label.get_style_context().add_class("title-label")
        header.pack_start(title_label, False, False, 0)

        self.count_badge = Gtk.Label(label="0 clips")
        self.count_badge.get_style_context().add_class("count-badge")
        header.pack_start(self.count_badge, False, False, 0)

        # Close button
        close_btn = Gtk.Button(label="✕")
        close_btn.get_style_context().add_class("close-btn")
        close_btn.connect("clicked", lambda b: self.hide())
        header.pack_end(close_btn, False, False, 0)

        # Clear button
        clear_btn = Gtk.Button(label="Clear")
        clear_btn.get_style_context().add_class("clear-btn")
        clear_btn.connect("clicked", self._on_clear_clicked)
        header.pack_end(clear_btn, False, False, 0)

        root_box.pack_start(header, False, False, 0)

        # --- Scrolled List Container ---
        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.list_box = Gtk.ListBox()
        self.list_box.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.list_box.get_style_context().add_class("clip-list")
        self.list_box.connect("row-activated", self._on_row_activated)

        self.scrolled.add(self.list_box)
        root_box.pack_start(self.scrolled, True, True, 0)

        # --- Empty State Container ---
        self.empty_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.empty_box.get_style_context().add_class("empty-box")
        self.empty_box.set_valign(Gtk.Align.CENTER)
        self.empty_box.set_halign(Gtk.Align.CENTER)

        empty_icon = Gtk.Label(label="📋")
        empty_icon.get_style_context().add_class("empty-title")
        self.empty_box.pack_start(empty_icon, False, False, 0)

        empty_title = Gtk.Label(label="Clipboard is empty")
        empty_title.get_style_context().add_class("empty-title")
        self.empty_box.pack_start(empty_title, False, False, 0)

        empty_sub = Gtk.Label(label="Copy text anywhere to see it here")
        empty_sub.get_style_context().add_class("empty-subtitle")
        self.empty_box.pack_start(empty_sub, False, False, 0)

        root_box.pack_start(self.empty_box, True, True, 0)

        # --- Footer ---
        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        footer.get_style_context().add_class("footer-bar")
        hint_label = Gtk.Label(label="↑↓ Navigate   •   ↵ Copy   •   Del Delete   •   Esc Close")
        hint_label.get_style_context().add_class("footer-hint")
        hint_label.set_xalign(0.5)
        footer.pack_start(hint_label, True, True, 0)
        root_box.pack_end(footer, False, False, 0)

    def refresh_list(self) -> None:
        """Reload clips from storage into the UI."""
        # Clear existing rows
        for child in self.list_box.get_children():
            self.list_box.remove(child)

        clips = self.storage.get_clips()
        count = len(clips)

        # Update counter badge
        self.count_badge.set_text(f"{count}/{self.config.max_cap}")

        if count == 0:
            self.scrolled.hide()
            self.empty_box.show_all()
            return

        self.empty_box.hide()
        self.scrolled.show_all()

        for clip in clips:
            row = ClipRow(clip)
            self.list_box.add(row)

        self.list_box.show_all()
        # Select first item by default for rapid keyboard copy
        first_row = self.list_box.get_row_at_index(0)
        if first_row:
            self.list_box.select_row(first_row)

    def copy_and_dismiss(self, content: str) -> None:
        """Copy selected text to system clipboard and hide the popup."""
        if self.on_copy:
            self.on_copy(content)
        self.hide()

    def _on_row_activated(self, list_box: Gtk.ListBox, row: Optional[ClipRow]) -> None:
        """Triggered when row is clicked or activated with Enter."""
        if row and hasattr(row, "item"):
            self.copy_and_dismiss(row.item.content)

    def _on_key_press(self, widget: Gtk.Widget, event: Gdk.EventKey) -> bool:
        """Handle keyboard navigation and shortcuts."""
        keyval = event.keyval

        if keyval == Gdk.KEY_Escape:
            self.hide()
            return True

        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            selected = self.list_box.get_selected_row()
            if selected and hasattr(selected, "item"):
                self.copy_and_dismiss(selected.item.content)
                return True

        if keyval in (Gdk.KEY_Delete, Gdk.KEY_BackSpace):
            selected = self.list_box.get_selected_row()
            if selected and hasattr(selected, "item"):
                self.storage.delete_clip(selected.item.id)
                self.refresh_list()
                return True

        return False

    def _on_clear_clicked(self, button: Gtk.Button) -> None:
        """Wipe all clips and refresh."""
        self.storage.clear_all()
        self.refresh_list()

    def _on_header_drag(self, widget: Gtk.Widget, event: Gdk.EventButton) -> bool:
        """Allow user to drag and move the window by clicking the header."""
        if event.button == 1:
            self.begin_move_drag(
                event.button, int(event.x_root), int(event.y_root), event.time
            )
            return True
        return False

    def _on_focus_out(self, widget: Gtk.Widget, event: Gdk.EventFocus) -> bool:
        """Auto-hide when clicking outside the window (Raycast/Win+V behavior)."""
        self.hide()
        return False
