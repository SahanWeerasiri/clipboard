"""Unit tests for Clipboard Storage engine.

Tests TDD requirements:
- Persistence in SQLite
- Duplicate detection and bumping to top
- Max capacity enforcement (auto-pruning oldest entries)
- Keyboard/mouse copy retrieval
- Clearing history
"""

import time
import pytest
from pathlib import Path
from src.storage import ClipboardStorage, ClipItem


@pytest.fixture
def temp_db(tmp_path: Path) -> Path:
    """Fixture providing a temporary SQLite database path."""
    return tmp_path / "test_clipboard.db"


@pytest.fixture
def storage(temp_db: Path) -> ClipboardStorage:
    """Fixture providing an initialized ClipboardStorage instance with max_cap=5."""
    return ClipboardStorage(db_path=temp_db, max_cap=5, max_text_length=1000)


def test_storage_initialization(storage: ClipboardStorage, temp_db: Path):
    """Test that the database file and schema are created properly."""
    assert temp_db.exists()
    assert storage.get_count() == 0
    assert storage.get_clips() == []


def test_add_clip_basic(storage: ClipboardStorage):
    """Test inserting a new text snippet into storage."""
    text = "Hello, Linux Clipboard!"
    item = storage.add_clip(text)

    assert item is not None
    assert item.content == text
    assert item.char_count == len(text)
    assert item.line_count == 1
    assert item.created_at > 0
    assert item.updated_at >= item.created_at
    assert storage.get_count() == 1

    clips = storage.get_clips()
    assert len(clips) == 1
    assert clips[0] == item


def test_add_clip_multiline(storage: ClipboardStorage):
    """Test inserting multiline text calculates correct line count."""
    text = "Line 1\nLine 2\nLine 3"
    item = storage.add_clip(text)

    assert item is not None
    assert item.line_count == 3
    assert item.char_count == len(text)


def test_add_clip_empty_or_whitespace_ignored(storage: ClipboardStorage):
    """Test that empty or whitespace-only inputs are ignored."""
    assert storage.add_clip("") is None
    assert storage.add_clip("   \n\t  ") is None
    assert storage.get_count() == 0


def test_duplicate_detection_bumps_to_top(storage: ClipboardStorage):
    """Test that copying identical text bumps it to the top without duplicate rows."""
    storage.add_clip("First Item")
    time.sleep(0.01)
    storage.add_clip("Second Item")
    time.sleep(0.01)

    assert storage.get_count() == 2
    clips = storage.get_clips()
    assert clips[0].content == "Second Item"
    assert clips[1].content == "First Item"

    # Re-copy "First Item"
    updated_item = storage.add_clip("First Item")
    assert updated_item is not None
    assert storage.get_count() == 2  # Total count unchanged!

    clips_after = storage.get_clips()
    assert len(clips_after) == 2
    # "First Item" is now bumped to the top (index 0)
    assert clips_after[0].content == "First Item"
    assert clips_after[1].content == "Second Item"
    assert clips_after[0].updated_at > clips_after[1].updated_at


def test_max_cap_auto_pruning(temp_db: Path):
    """Test that max capacity strictly limits stored clips and prunes oldest."""
    # Storage with small cap of 3
    small_storage = ClipboardStorage(db_path=temp_db, max_cap=3)

    small_storage.add_clip("Clip 1")
    time.sleep(0.01)
    small_storage.add_clip("Clip 2")
    time.sleep(0.01)
    small_storage.add_clip("Clip 3")
    time.sleep(0.01)

    assert small_storage.get_count() == 3

    # Add 4th item - "Clip 1" should be pruned
    small_storage.add_clip("Clip 4")
    assert small_storage.get_count() == 3

    contents = [c.content for c in small_storage.get_clips()]
    assert contents == ["Clip 4", "Clip 3", "Clip 2"]
    assert "Clip 1" not in contents


def test_delete_clip(storage: ClipboardStorage):
    """Test deleting a specific clip by ID."""
    item1 = storage.add_clip("Item 1")
    item2 = storage.add_clip("Item 2")
    assert item1 is not None and item2 is not None

    assert storage.get_count() == 2
    assert storage.delete_clip(item1.id) is True
    assert storage.get_count() == 1

    remaining = storage.get_clips()
    assert remaining[0].id == item2.id

    # Non-existent ID returns False
    assert storage.delete_clip(99999) is False


def test_clear_all(storage: ClipboardStorage):
    """Test wiping all clipboard history."""
    storage.add_clip("A")
    storage.add_clip("B")
    storage.add_clip("C")
    assert storage.get_count() == 3

    deleted_count = storage.clear_all()
    assert deleted_count == 3
    assert storage.get_count() == 0
    assert storage.get_clips() == []


def test_max_text_length_truncation(temp_db: Path):
    """Test that extremely large text is capped to prevent memory exhaustion."""
    storage_capped = ClipboardStorage(db_path=temp_db, max_cap=5, max_text_length=50)
    huge_text = "x" * 200
    item = storage_capped.add_clip(huge_text)

    assert item is not None
    assert len(item.content) == 50
    assert item.char_count == 50
