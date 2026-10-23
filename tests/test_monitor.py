"""Unit tests for Clipboard Monitor and helper utilities."""

import time
import pytest
from unittest.mock import MagicMock
from src.monitor import ClipboardMonitor, format_relative_time


def test_format_relative_time():
    """Test relative time formatting for UI badges."""
    now = time.time()

    # Just now (< 60s)
    assert format_relative_time(now - 10, now=now) == "Just now"
    assert format_relative_time(now - 55, now=now) == "Just now"

    # Minutes ago
    assert format_relative_time(now - 120, now=now) == "2m ago"
    assert format_relative_time(now - 600, now=now) == "10m ago"

    # Hours ago
    assert format_relative_time(now - 3600, now=now) == "1h ago"
    assert format_relative_time(now - 7200, now=now) == "2h ago"

    # Days ago
    assert format_relative_time(now - 86400 * 2, now=now) == "2d ago"


def test_monitor_deduplication():
    """Test that monitor ignores duplicate consecutive text clips."""
    callback = MagicMock()
    monitor = ClipboardMonitor(on_clip=callback)

    # First text
    assert monitor.process_text("First clip") is True
    callback.assert_called_once_with("First clip")

    # Same text again immediately -> ignored by monitor memory cache
    callback.reset_mock()
    assert monitor.process_text("First clip") is False
    callback.assert_not_called()

    # New text
    assert monitor.process_text("Second clip") is True
    callback.assert_called_once_with("Second clip")


def test_monitor_empty_text_ignored():
    """Test that empty or whitespace text is ignored by monitor."""
    callback = MagicMock()
    monitor = ClipboardMonitor(on_clip=callback)

    assert monitor.process_text("") is False
    assert monitor.process_text("   \n\t") is False
    callback.assert_not_called()


def test_monitor_callback_error_resilience():
    """Test that if callback throws an error, monitor logs and does not crash."""
    failing_callback = MagicMock(side_effect=RuntimeError("Database lock"))
    monitor = ClipboardMonitor(on_clip=failing_callback)

    # Should not raise exception
    res = monitor.process_text("Safe text")
    assert res is True
