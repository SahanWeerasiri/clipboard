"""Clipboard monitor and helper functions for LightClip.

Listens to system clipboard changes using GTK3 events with a robust polling fallback.
"""

from __future__ import annotations

import logging
import time
from typing import Callable, Optional

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib, Gtk

from src.config import DEFAULT_CONFIG

logger = logging.getLogger("lightclip.monitor")


def format_relative_time(timestamp: float, now: Optional[float] = None) -> str:
    """Format a unix timestamp into human-readable relative time (e.g. 'Just now', '2m ago')."""
    current = now if now is not None else time.time()
    diff = max(0, int(current - timestamp))

    if diff < 60:
        return "Just now"
    if diff < 3600:
        mins = diff // 60
        return f"{mins}m ago"
    if diff < 86400:
        hours = diff // 3600
        return f"{hours}h ago"
    days = diff // 86400
    return f"{days}d ago"


class ClipboardMonitor:
    """Monitors system clipboard for new text content."""

    def __init__(
        self,
        on_clip: Optional[Callable[[str], None]] = None,
        poll_interval_ms: int = DEFAULT_CONFIG.poll_interval_ms,
    ) -> None:
        self.on_clip = on_clip
        self.poll_interval_ms = poll_interval_ms
        self._last_seen_text: Optional[str] = None
        self._clipboard: Optional[Gtk.Clipboard] = None
        self._poll_source_id: Optional[int] = None
        self._owner_change_handler_id: Optional[int] = None
        self._is_running = False

    def process_text(self, text: Optional[str]) -> bool:
        """Process candidate clipboard text with in-memory deduplication.
        
        Returns True if new text was processed and callback triggered, False otherwise.
        """
        if not text or not text.strip():
            return False

        if text == self._last_seen_text:
            return False

        self._last_seen_text = text

        if self.on_clip:
            try:
                self.on_clip(text)
            except Exception as e:
                logger.error("Error in on_clip callback: %s", e)
        return True

    def start(self) -> None:
        """Start listening to clipboard events and polling fallback."""
        if self._is_running:
            return

        self._clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)

        # Connect owner-change signal
        try:
            self._owner_change_handler_id = self._clipboard.connect(
                "owner-change", self._on_owner_change
            )
        except Exception as e:
            logger.warning("Could not connect owner-change signal: %s", e)

        # Polling fallback for non-cooperative Wayland/X11 clients
        self._poll_source_id = GLib.timeout_add(
            self.poll_interval_ms, self._poll_clipboard
        )
        self._is_running = True
        self._check_current_text()

    def stop(self) -> None:
        """Stop listening to clipboard events."""
        if not self._is_running:
            return

        if self._clipboard and self._owner_change_handler_id:
            try:
                self._clipboard.disconnect(self._owner_change_handler_id)
            except Exception:
                pass
            self._owner_change_handler_id = None

        if self._poll_source_id:
            GLib.source_remove(self._poll_source_id)
            self._poll_source_id = None

        self._is_running = False

    def copy_to_clipboard(self, text: str) -> None:
        """Set system clipboard text without triggering a duplicate notification."""
        if not self._clipboard:
            self._clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)

        self._last_seen_text = text
        self._clipboard.set_text(text, -1)
        self._clipboard.store()

    def _on_owner_change(self, clipboard: Gtk.Clipboard, event: Gdk.EventOwnerChange) -> None:
        """Handle GTK clipboard owner-change event."""
        self._check_current_text()

    def _poll_clipboard(self) -> bool:
        """Periodic check for clipboard changes."""
        if not self._is_running:
            return False
        self._check_current_text()
        return True

    def _check_current_text(self) -> None:
        """Read current clipboard text asynchronously and dispatch to process_text."""
        if not self._clipboard:
            return

        def _text_received_cb(clip: Gtk.Clipboard, text: Optional[str], data: None) -> None:
            if text:
                self.process_text(text)

        self._clipboard.request_text(_text_received_cb, None)
