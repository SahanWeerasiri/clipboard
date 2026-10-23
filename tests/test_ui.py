"""Unit tests for GTK3 UI components and interactions."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock
from src.config import Config
from src.storage import ClipboardStorage, ClipItem
from src.ui import ClipRow, ClipboardWindow, apply_theme


@pytest.fixture
def temp_storage(tmp_path: Path) -> ClipboardStorage:
    """Fixture providing a temporary storage instance."""
    db_file = tmp_path / "ui_test.db"
    return ClipboardStorage(db_path=db_file, max_cap=5)


def test_apply_theme():
    """Verify that custom CSS stylesheet loads cleanly without error."""
    apply_theme()


def test_clip_row_widget(temp_storage: ClipboardStorage):
    """Test creating a ClipRow widget with a ClipItem."""
    item = temp_storage.add_clip("Sample preview text\nSecond line")
    assert item is not None

    row = ClipRow(item)
    assert row.item == item
    assert row.get_style_context().has_class("clip-row")


def test_clipboard_window_empty_and_populated(temp_storage: ClipboardStorage):
    """Test window initialization, empty state, and population."""
    on_copy = MagicMock()
    config = Config(window_width=300, window_height=400, max_cap=5)
    win = ClipboardWindow(storage=temp_storage, on_copy=on_copy, config=config)

    # Initially empty
    assert temp_storage.get_count() == 0
    assert win.count_badge.get_text() == "0/5"

    # Add items
    temp_storage.add_clip("Clip Alpha")
    temp_storage.add_clip("Clip Beta")
    win.refresh_list()

    assert win.count_badge.get_text() == "2/5"
    assert len(win.list_box.get_children()) == 2

    # Test copy and dismiss
    win.copy_and_dismiss("Clip Beta")
    on_copy.assert_called_once_with("Clip Beta")


def test_clipboard_window_clear_action(temp_storage: ClipboardStorage):
    """Test clear button action wipes storage and updates list."""
    temp_storage.add_clip("Clip 1")
    temp_storage.add_clip("Clip 2")
    win = ClipboardWindow(storage=temp_storage)

    assert temp_storage.get_count() == 2
    win._on_clear_clicked(MagicMock())

    assert temp_storage.get_count() == 0
    assert win.count_badge.get_text() == "0/50"
    assert len(win.list_box.get_children()) == 0
