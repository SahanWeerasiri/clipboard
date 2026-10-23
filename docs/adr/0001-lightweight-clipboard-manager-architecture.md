# 1. Ultra-Lightweight Native Linux Clipboard Manager Architecture

**Date:** 2026-10-23  
**Status:** Accepted  

## Context

Linux desktop environments (especially GNOME running under Wayland) historically lack a fast, beautiful, low-code clipboard manager comparable to macOS Raycast/Maccy or Windows Clipboard History (`Win + V`). 

Existing solutions typically suffer from:
1. **Excessive bloat:** Electron or webview wrappers consuming 200MB–400MB of RAM for a simple utility.
2. **Heavy third-party dependencies:** Requiring extensive `pip install` setups (PyQt, PySide, custom C++ wheel extensions) that break across Python upgrades.
3. **Clunky legacy UI:** Outdated X11-era interfaces lacking dark mode, smooth typography, or rounded cards.

We needed a low-code, lightweight, visually attractive clipboard manager with **zero third-party dependencies**.

## Alternatives Considered

| Alternative | Pros | Cons | Decision |
|---|---|---|---|
| **Electron / Node.js** | Fast prototyping, HTML/CSS | Huge memory footprint (>250MB RAM), slow startup | Rejected |
| **PyQt5 / PySide6** | Modern widgets | Requires heavy external pip packages (>150MB), non-native GNOME feel | Rejected |
| **Tkinter** | Standard library | Outdated visual styling, poor Wayland support, no CSS | Rejected |
| **Python stdlib + System PyGObject (GTK3)** | Built-in on Ubuntu/Debian/Fedora, zero pip packages, <25MB RAM, instant startup, GTK CSS styling | Requires Linux desktop environment with GTK | **Accepted** |

## Decision & Rationale

We chose **Python 3 Standard Library + Pre-installed System PyGObject (GTK3 + Gdk)** with the following core components:

1. **Storage Engine (`src/storage.py`):**
   - Built with Python's built-in `sqlite3` in WAL mode for atomic operations.
   - **Duplicate Detection:** Copying identical text bumps the existing entry to the top with a refreshed timestamp instead of creating duplicate records.
   - **Max Cap Pruning:** Enforces a configurable cap (default 50 items) to prevent disk and storage overflow.

2. **UI & Aesthetics (`src/ui.py`):**
   - Borderless floating card popup inspired by Raycast and Catppuccin Mocha.
   - Styled using native **GTK CSS** (`#181825` dark background, `#1e1e2e` cards, `#cba6f7` lavender active accent, rounded corners, pill badges for character/line counts and relative time).
   - Instant dual-mode interaction:
     - **Mouse:** Single-click any card to copy back to clipboard and dismiss.
     - **Keyboard:** `Up`/`Down` arrows to navigate, `Enter` to copy selected item and dismiss, `Esc` to close, `Delete` to remove entry.
   - Header with dynamic clip counter badge and one-click "Clear" button.

3. **Instant Toggle via IPC (`src/app.py`):**
   - Single-instance lifecycle managed by a Unix domain socket (`/run/user/$UID/lightclip.sock`).
   - Pressing **Super + V** sends a toggle signal in `<5ms` without restarting the process.

4. **Background Monitoring (`src/monitor.py`):**
   - Uses GTK clipboard `owner-change` signals combined with an adaptive polling fallback to capture clipboard updates across Wayland and X11 applications.

## Consequences

* **Positive:**
  - **Zero Third-Party Libraries:** Runs directly using Ubuntu's pre-installed Python and PyGObject. No `pip install` required.
  - **Ultra-Lightweight:** Startup time `<50ms`, memory footprint `<25MB` RAM.
  - **Low Code:** Clean, modular codebase (~300 lines of code total), easily auditable and customizable.
  - **Distraction-Free:** Direct card list without search clutter, auto-selecting the latest clip for instant keyboard pasting.

* **Trade-offs:**
  - Requires a GTK-compatible desktop environment (standard on Ubuntu, Fedora, Debian, Pop!_OS, Linux Mint).
