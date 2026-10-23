# LightClip 📋

> **Ultra-lightweight, attractive native Linux clipboard manager.**  
> Built with zero third-party dependencies using Python 3 and native GTK3 styling.

---

## ✨ Features

- **🚀 Zero Third-Party Libraries:** Runs directly using Python standard library (`sqlite3`, `socket`, `time`, `threading`) and the system's pre-installed `PyGObject` (GTK3). No `pip install` required!
- **🎨 Modern Floating Design:** Clean, dark Catppuccin Mocha-inspired floating window with rounded corners, subtle glass borders, and smooth hover interactions.
- **⚡ Super+V Instant Toggle:** Managed via a lightweight Unix domain socket (`lightclip.sock`) delivering sub-5ms popup response times.
- **🔄 Smart Deduplication:** Copying text that already exists in history bumps it to the top with a refreshed timestamp instead of creating duplicate records.
- **🛡️ Auto-Pruning Max Capacity:** Enforces a configurable cap (default 50 items) so your history never overflows disk or memory.
- **⌨️ Keyboard & Mouse Copy:**
  - **Mouse:** Single-click any card to copy immediately to system clipboard and dismiss window.
  - **Keyboard:** `Up` / `Down` arrows to navigate cards, `Enter` to copy selected card and dismiss, `Esc` to close without copying, `Del` to delete a specific clip.
- **🧹 Instant Clear:** Header action button to wipe history with a single click.
- **⏱️ Live Metadata Badges:** Real-time relative timestamps (`Just now`, `5m ago`, `2h ago`) and line/character count badges (`3 lines`, `42 chars`).
- **🐧 Wayland & X11 Native:** Full compatibility with modern Ubuntu GNOME, Wayland sessions, and traditional X11 desktops.

---

## 🚀 Quick Start

### 1. Run Directly
```bash
./run.sh
```
Or toggle the floating popup:
```bash
./run.sh --toggle
```

### 2. Command Line Options
```bash
./run.sh --help       # Show help and CLI options
./run.sh --toggle     # Toggle the floating window (ideal for shortcut binding)
./run.sh --daemon     # Start monitoring in background (window remains hidden until summoned)
./run.sh --list       # View current clipboard history directly in terminal
./run.sh --clear      # Wipe clipboard history from terminal
```

---

## ⌨️ Bind to Super + V in Ubuntu / GNOME

To make LightClip appear when pressing **Super + V** (just like Windows Clipboard History or macOS Raycast):

1. Open **Settings** on Ubuntu.
2. Go to **Keyboard** → **View and Customize Shortcuts** (at the bottom).
3. Scroll down and click **Custom Shortcuts** → **Add Shortcut (+)**.
4. Fill in the following details:
   - **Name:** `Clipboard History`
   - **Command:** `/home/sahan-weerasiri/projects/clipboard/run.sh --toggle`
   - **Shortcut:** Press <kbd>Super</kbd> + <kbd>V</kbd> (or <kbd>Ctrl</kbd> + <kbd>Alt</kbd> + <kbd>V</kbd>)
5. Click **Add**.

Now, whenever you press **Super + V**, LightClip will float smoothly in the center of your screen!

---

## 📁 Project Architecture

```text
clipboard/
├── src/
│   ├── __init__.py
│   ├── config.py         # Configuration settings & environment variable overrides
│   ├── storage.py        # SQLite persistence, duplicate bumping, max cap pruning
│   ├── monitor.py        # System clipboard listener (GTK signals + polling fallback)
│   ├── ui.py             # GTK3 floating window, Catppuccin CSS styling, key/mouse events
│   └── app.py            # Single-instance IPC server, CLI parser, application coordinator
├── tests/
│   ├── __init__.py
│   ├── test_app.py       # IPC socket and application lifecycle tests
│   ├── test_monitor.py   # Clipboard deduplication and relative time tests
│   ├── test_storage.py   # SQLite persistence, deduplication, and max cap pruning tests
│   └── test_ui.py        # GTK3 widgets, CSS parsing, and UI interaction tests
├── docs/
│   └── adr/              # Architecture Decision Records
│       ├── 0001-lightweight-clipboard-manager-architecture.md
│       └── README.md
├── run.sh                # Executable launcher script
└── lightclip.desktop     # GNOME desktop launcher entry
```

---

## ⚙️ Configuration

LightClip works out of the box with optimal defaults, but can be customized using environment variables:

| Variable | Default | Description |
|---|---|---|
| `LIGHTCLIP_MAX_CAP` | `50` | Maximum number of clips to retain before pruning oldest |
| `LIGHTCLIP_DB_PATH` | `~/.local/share/lightclip/clipboard.db` | Path to SQLite database file |
| `LIGHTCLIP_MAX_TEXT_LEN` | `200000` | Maximum characters per single clip (prevents accidental bloat) |

Example:
```bash
export LIGHTCLIP_MAX_CAP=100
./run.sh
```

---

## 🧪 Testing

The test suite enforces full test coverage across storage, deduplication, auto-pruning, UI parsing, and IPC communication:

```bash
python3 -m pytest tests/ -v
```

All 22 unit tests run in less than **0.5 seconds**.

---

## 📄 Architecture Decisions

Read [ADR-0001](docs/adr/0001-lightweight-clipboard-manager-architecture.md) for detailed analysis of alternatives considered (Electron, PyQt, Tkinter) and the engineering rationale behind choosing native GTK3 + Python standard library.
