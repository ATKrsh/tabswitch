# Assistive Tab Switcher

A premium, always-on-top floating desktop widget for Windows that switches tabs in the currently active window.

## Features

- **Always-on-top** translucent circular widget with two interactive zones
- **Mode 1 (Outer Donut)**: Click the outer ring to send `Ctrl+Tab` — cycles to the **next tab**
- **Mode 2 (Inner Circle)**: Click the inner circle to send `Ctrl+Shift+Tab` — cycles to the **previous/recent tab**
- **Drag to reposition** anywhere on screen
- **Lock position** with `Shift+Click`
- **Close** with `Alt+Click` or via system tray
- **System tray** icon with context menu
- Smooth opacity animations and ambient glow effects

## Requirements

- Python 3.8+
- PyQt5
- Pillow (only for icon generation)

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```bash
python tabswitcher.py
```

### Controls

| Action | Effect |
|---|---|
| Click outer donut | Mode 1: `Ctrl+Tab` (next tab) |
| Click inner circle | Mode 2: `Ctrl+Shift+Tab` (previous tab) |
| Drag | Move the widget |
| `Shift` + Click | Toggle lock position |
| `Alt` + Click | Quit the app |
| System Tray → Right Click | Context menu (hide/show, lock, quit) |

## Icon Generation

To regenerate the icon:

```bash
python generate_icon.py
python embed_icon.py
```

## License

MIT
