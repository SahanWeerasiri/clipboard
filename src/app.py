"""Application entrypoint for LightClip clipboard manager.

Handles:
- Single-instance lifecycle and instant window toggle via Unix domain socket.
- Wiring between storage, clipboard monitor, and GTK3 floating window.
- Command-line arguments (--daemon, --toggle, --clear, --list, --help).
"""

from __future__ import annotations

import argparse
import os
import signal
import socket
import sys
import threading
from pathlib import Path
from typing import Optional

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib, Gtk

from src.config import DEFAULT_CONFIG, Config
from src.monitor import ClipboardMonitor
from src.storage import ClipboardStorage
from src.ui import ClipboardWindow, apply_theme


def get_socket_path() -> Path:
    """Return platform-appropriate runtime socket path."""
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
    if runtime_dir and os.path.isdir(runtime_dir):
        return Path(runtime_dir) / "lightclip.sock"
    return Path.home() / ".local" / "share" / "lightclip" / "lightclip.sock"


def send_ipc_command(sock_path: Path, command: str) -> bool:
    """Send command to running LightClip instance. Returns True if succeeded."""
    if not sock_path.exists():
        return False

    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        client.settimeout(1.0)
        client.connect(str(sock_path))
        client.sendall(f"{command.strip()}\n".encode("utf-8"))
        client.close()
        return True
    except (socket.error, OSError):
        # Socket file exists but no process is listening
        try:
            sock_path.unlink(missing_ok=True)
        except OSError:
            pass
        return False


class IpcServer:
    """Lightweight Unix domain socket server for instant window toggling."""

    def __init__(self, sock_path: Path, on_command: callable) -> None:
        self.sock_path = sock_path
        self.on_command = on_command
        self._server_sock: Optional[socket.socket] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Bind socket and start listening in background thread."""
        self.sock_path.parent.mkdir(parents=True, exist_ok=True)
        self.sock_path.unlink(missing_ok=True)

        self._server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._server_sock.bind(str(self.sock_path))
        self._server_sock.listen(5)
        self._running = True

        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()

    def _listen_loop(self) -> None:
        """Loop accepting incoming IPC commands."""
        while self._running and self._server_sock:
            try:
                conn, _ = self._server_sock.accept()
                with conn:
                    data = conn.recv(1024).decode("utf-8").strip()
                    if data:
                        self.on_command(data)
            except (OSError, socket.error):
                break

    def stop(self) -> None:
        """Stop socket server and clean up socket file."""
        self._running = False
        if self._server_sock:
            try:
                self._server_sock.close()
            except OSError:
                pass
            self._server_sock = None
        self.sock_path.unlink(missing_ok=True)


class LightClipApp:
    """Main application coordinator managing storage, monitor, UI, and IPC."""

    def __init__(self, config: Config = DEFAULT_CONFIG) -> None:
        self.config = config
        self.storage = ClipboardStorage(
            db_path=config.db_path,
            max_cap=config.max_cap,
            max_text_length=config.max_text_length,
        )
        self.monitor = ClipboardMonitor(
            on_clip=self._on_new_clip,
            poll_interval_ms=config.poll_interval_ms,
        )
        self.window: Optional[ClipboardWindow] = None
        self.ipc_server: Optional[IpcServer] = None
        self.sock_path = get_socket_path()

    def _on_new_clip(self, text: str) -> None:
        """Callback invoked when system clipboard receives new text."""
        self.storage.add_clip(text)
        if self.window and self.window.is_visible():
            GLib.idle_add(self.window.refresh_list)

    def _handle_ipc_command(self, cmd: str) -> None:
        """Dispatch IPC command safely to the GTK main thread."""
        GLib.idle_add(self._execute_ipc_command, cmd)

    def _execute_ipc_command(self, cmd: str) -> bool:
        """Execute command on the GTK main thread."""
        if cmd == "toggle":
            self.toggle_window()
        elif cmd == "show":
            self.show_window()
        elif cmd == "hide":
            self.hide_window()
        elif cmd == "clear":
            self.storage.clear_all()
            if self.window:
                self.window.refresh_list()
        return False

    def toggle_window(self) -> None:
        """Toggle floating window visibility."""
        if not self.window:
            return

        if self.window.is_visible():
            self.window.hide()
        else:
            self.show_window()

    def show_window(self) -> None:
        """Display and bring floating window to front."""
        if not self.window:
            return

        self.window.refresh_list()
        self.window.show_all()
        self.window.present()

    def hide_window(self) -> None:
        """Hide window."""
        if self.window:
            self.window.hide()

    def run(self, start_hidden: bool = False) -> None:
        """Start the GTK main loop."""
        apply_theme()
        self.window = ClipboardWindow(
            storage=self.storage,
            on_copy=self.monitor.copy_to_clipboard,
            config=self.config,
        )

        # Start background monitor
        self.monitor.start()

        # Start IPC server for instant Super+V shortcuts
        self.ipc_server = IpcServer(self.sock_path, self._handle_ipc_command)
        self.ipc_server.start()

        # Show initial window unless requested to start in background daemon mode
        if not start_hidden:
            self.show_window()

        # Graceful shutdown on signals
        def _signal_handler(sig, frame):
            GLib.idle_add(self.shutdown)

        signal.signal(signal.SIGINT, _signal_handler)
        signal.signal(signal.SIGTERM, _signal_handler)

        Gtk.main()

    def shutdown(self) -> None:
        """Cleanly stop background services and exit GTK loop."""
        if self.monitor:
            self.monitor.stop()
        if self.ipc_server:
            self.ipc_server.stop()
        Gtk.main_quit()


def main() -> None:
    """CLI parser and application entrypoint."""
    parser = argparse.ArgumentParser(
        description="LightClip - Ultra-lightweight & attractive native Linux clipboard manager"
    )
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Run in background daemon mode (window hidden until shortcut is pressed)",
    )
    parser.add_argument(
        "--toggle",
        action="store_true",
        help="Toggle floating clipboard window (ideal for Super+V shortcut)",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear all stored clipboard history",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Print clipboard history to terminal",
    )

    args = parser.parse_args()
    sock_path = get_socket_path()

    # Handle CLI subcommands
    if args.clear:
        if send_ipc_command(sock_path, "clear"):
            print("Cleared history via active LightClip instance.")
        else:
            storage = ClipboardStorage()
            count = storage.clear_all()
            print(f"Cleared {count} clips from clipboard storage.")
        return

    if args.list:
        storage = ClipboardStorage()
        clips = storage.get_clips()
        if not clips:
            print("Clipboard is empty.")
            return
        print(f"--- LightClip History ({len(clips)} items) ---")
        for i, clip in enumerate(clips, 1):
            snippet = clip.content.replace("\n", "\\n")
            if len(snippet) > 60:
                snippet = snippet[:57] + "..."
            print(f"[{i:2d}] {snippet}")
        return

    # If --toggle requested or default invocation:
    # Try sending toggle to already running instance first
    if send_ipc_command(sock_path, "toggle"):
        # Instance was running and toggled!
        return

    # No existing instance running, start LightClip
    app = LightClipApp()
    app.run(start_hidden=args.daemon)


if __name__ == "__main__":
    main()
