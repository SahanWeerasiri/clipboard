"""Unit tests for LightClipApp lifecycle and IPC communication."""

import time
import pytest
from pathlib import Path
from unittest.mock import MagicMock
from src.config import Config
from src.app import LightClipApp, IpcServer, send_ipc_command, get_socket_path


def test_get_socket_path():
    """Verify socket path is returned as a Path object."""
    path = get_socket_path()
    assert isinstance(path, Path)
    assert path.name == "lightclip.sock"


def test_ipc_server_and_client(tmp_path: Path):
    """Test IPC server binds and receives command from send_ipc_command."""
    sock_file = tmp_path / "test_ipc.sock"
    received_commands = []

    def on_cmd(cmd: str):
        received_commands.append(cmd)

    server = IpcServer(sock_path=sock_file, on_command=on_cmd)
    server.start()
    time.sleep(0.05)

    assert sock_file.exists()

    # Send command
    success = send_ipc_command(sock_file, "toggle")
    assert success is True
    time.sleep(0.05)

    # Server should have received command
    assert "toggle" in received_commands

    server.stop()
    assert not sock_file.exists()


def test_ipc_client_handles_dead_socket(tmp_path: Path):
    """Test send_ipc_command gracefully returns False when no server listens."""
    non_existent = tmp_path / "dead.sock"
    assert send_ipc_command(non_existent, "ping") is False


def test_app_initialization(tmp_path: Path):
    """Test LightClipApp sets up storage and monitor with custom config."""
    cfg = Config(
        db_path=tmp_path / "app_test.db",
        max_cap=10,
    )
    app = LightClipApp(config=cfg)

    assert app.storage.max_cap == 10
    assert app.storage.db_path == tmp_path / "app_test.db"

    # Test clip handler adds to storage
    app._on_new_clip("Hello from test")
    assert app.storage.get_count() == 1


def test_app_ipc_command_handlers(tmp_path: Path):
    """Test _execute_ipc_command handles toggle, show, hide, clear."""
    cfg = Config(db_path=tmp_path / "app_cmd.db")
    app = LightClipApp(config=cfg)

    app.toggle_window = MagicMock()
    app.show_window = MagicMock()
    app.hide_window = MagicMock()

    app._execute_ipc_command("toggle")
    app.toggle_window.assert_called_once()

    app._execute_ipc_command("show")
    app.show_window.assert_called_once()

    app._execute_ipc_command("hide")
    app.hide_window.assert_called_once()

    app.storage.add_clip("Clip to clear")
    assert app.storage.get_count() == 1
    app._execute_ipc_command("clear")
    assert app.storage.get_count() == 0
