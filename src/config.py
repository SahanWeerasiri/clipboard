"""Configuration module for LightClip clipboard manager."""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    """Immutable application configuration."""

    max_cap: int = int(os.environ.get("LIGHTCLIP_MAX_CAP", "50"))
    max_text_length: int = int(os.environ.get("LIGHTCLIP_MAX_TEXT_LEN", "200000"))
    db_path: Path = Path(
        os.environ.get(
            "LIGHTCLIP_DB_PATH",
            str(Path.home() / ".local" / "share" / "lightclip" / "clipboard.db"),
        )
    )
    window_width: int = 420
    window_height: int = 540
    poll_interval_ms: int = 400


DEFAULT_CONFIG = Config()
