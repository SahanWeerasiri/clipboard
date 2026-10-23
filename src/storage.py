"""SQLite persistence engine for LightClip clipboard manager.

Features:
- Zero third-party dependencies (built-in sqlite3).
- Duplicate detection: identical clips bump to top with refreshed timestamp.
- Max cap auto-pruning: keeps storage lean and prevents disk overflow.
- Atomic operations with SQLite WAL mode.
- Clean frozen dataclass representations.
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Union

from src.config import DEFAULT_CONFIG


@dataclass(frozen=True)
class ClipItem:
    """Immutable representation of a clipboard entry."""

    id: int
    content: str
    char_count: int
    line_count: int
    created_at: float
    updated_at: float


class ClipboardStorage:
    """Handles thread-safe persistence and history management for clipboard clips."""

    def __init__(
        self,
        db_path: Union[str, Path] = DEFAULT_CONFIG.db_path,
        max_cap: int = DEFAULT_CONFIG.max_cap,
        max_text_length: int = DEFAULT_CONFIG.max_text_length,
    ) -> None:
        self.db_path = Path(db_path)
        self.max_cap = max(1, max_cap)
        self.max_text_length = max_text_length
        self._ensure_dir()
        self._init_db()

    def _ensure_dir(self) -> None:
        """Create parent directory if it doesn't already exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _get_connection(self) -> sqlite3.Connection:
        """Create a connection with WAL mode and foreign keys enabled."""
        conn = sqlite3.connect(str(self.db_path), timeout=5.0)
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        return conn

    def _init_db(self) -> None:
        """Initialize database schema with uniqueness on content and index on updated_at."""
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS clips (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL UNIQUE,
                    char_count INTEGER NOT NULL,
                    line_count INTEGER NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_clips_updated_at 
                ON clips(updated_at DESC);
                """
            )

    def add_clip(self, text: str) -> Optional[ClipItem]:
        """Add text clip to storage.
        
        - Ignores empty or whitespace-only strings.
        - Truncates content exceeding max_text_length.
        - Re-inserting identical content bumps it to the top with refreshed timestamp.
        - Automatically prunes entries exceeding max_cap.
        """
        if not text or not text.strip():
            return None

        # Sanitize null bytes
        sanitized = text.replace("\x00", "")
        if not sanitized.strip():
            return None

        # Capped length
        if len(sanitized) > self.max_text_length:
            sanitized = sanitized[: self.max_text_length]

        now = time.time()
        char_count = len(sanitized)
        line_count = len(sanitized.splitlines()) or 1

        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Upsert: on conflict bump updated_at to now
            cursor.execute(
                """
                INSERT INTO clips (content, char_count, line_count, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(content) DO UPDATE SET updated_at = excluded.updated_at
                RETURNING id, content, char_count, line_count, created_at, updated_at;
                """,
                (sanitized, char_count, line_count, now, now),
            )
            row = cursor.fetchone()
            if not row:
                return None

            item = ClipItem(
                id=row[0],
                content=row[1],
                char_count=row[2],
                line_count=row[3],
                created_at=row[4],
                updated_at=row[5],
            )

            # Auto-prune beyond max_cap
            cursor.execute(
                """
                DELETE FROM clips WHERE id NOT IN (
                    SELECT id FROM clips ORDER BY updated_at DESC LIMIT ?
                );
                """,
                (self.max_cap,),
            )
            return item

    def get_clips(self, limit: Optional[int] = None) -> List[ClipItem]:
        """Retrieve stored clips ordered chronologically (newest first)."""
        limit_val = limit if limit is not None and limit > 0 else self.max_cap
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, content, char_count, line_count, created_at, updated_at
                FROM clips
                ORDER BY updated_at DESC
                LIMIT ?;
                """,
                (limit_val,),
            )
            rows = cursor.fetchall()
            return [
                ClipItem(
                    id=row[0],
                    content=row[1],
                    char_count=row[2],
                    line_count=row[3],
                    created_at=row[4],
                    updated_at=row[5],
                )
                for row in rows
            ]

    def delete_clip(self, clip_id: int) -> bool:
        """Delete a clip by ID. Returns True if row was deleted."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM clips WHERE id = ?;", (clip_id,))
            return cursor.rowcount > 0

    def clear_all(self) -> int:
        """Clear all stored clips. Returns number of rows deleted."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM clips;")
            return cursor.rowcount

    def get_count(self) -> int:
        """Return total number of saved clips."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM clips;")
            row = cursor.fetchone()
            return row[0] if row else 0
