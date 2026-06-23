"""
yplay_tray.pyw — System tray icon for YPlay
Right-click menu: Play URL, Pause, Stop, Volume, Status, Exit
No console window (.pyw extension + pythonw)
Depends on: pystray, Pillow
"""

import sys
import os
import json
import ctypes
import ctypes.wintypes
import threading
import time
import subprocess
import tkinter as tk
from tkinter import simpledialog, messagebox

try:
    import pystray
    from pystray import MenuItem as item
    from PIL import Image, ImageDraw
except ImportError:
    # Auto-install if missing
    subprocess.run([sys.executable, "-m", "pip", "install", "pystray", "Pillow",
                    "--quiet", "--break-system-packages"], check=True)
    import pystray
    from pystray import MenuItem as item
    from PIL import Image, ImageDraw

# ── IPC (same as CLI client) ──────────────────────────────────────────────────
PIPE_NAME = r"\\.\pipe\yplay"
kernel32 = ctypes.windll.kernel32


def _send(payload: dict) -> dict | None:
    GENERIC_READ  = 0x80000000
    GENERIC_WRITE = 0x40000000
    OPEN_EXISTING = 3
    INVALID_HANDLE = ctypes.wintypes.HANDLE(-1).value

    h = kernel32.CreateFileW(PIPE_NAME, GENERIC_READ | GENERIC_WRITE, 0, None, OPEN_EXISTING, 0, None)
    if h == INVALID_HANDLE:
        return None
    try:
        mode = ctypes.wintypes.DWORD(0x00000002)
        kernel32.SetNamedPipeHandleState(h, ctypes.byref(mode), None, None)
        data    = json.dumps(payload).encode()
        written = ctypes.wintypes.DWORD(0)
        kernel32.WriteFile(h, data, len(data), ctypes.byref(written), None)
        buf  = ctypes.create_string_buffer(65536)
        read = ctypes.wintypes.DWORD(0)
        kernel32.ReadFile(h, buf, len(buf), ctypes.byref(read), None)
        raw = buf.raw[:read.value].decode(errors="replace").strip()
        return json.loads(raw) if raw else None
    finally:
        kernel32.CloseHandle(h)


def _ensure_daemon():
    """Start daemon if not alive."""
    if _send({"action": "status"}) is None:
        here   = os.path.dirname(os.path.abspath(__file__))
        daemon = os.path.join(here, "yplay_daemon.py")
        pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        if not os.path.exists(pythonw):
            pythonw = sys.executable
        subprocess.Popen(
            [pythonw, daemon],
            creationflags=(subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW |
                           subprocess.CREATE_NEW_PROCESS_GROUP),
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        time.sleep(1.5)


# ── Tray icon image (generated at runtime, no external files needed) ──────────
def _make_icon(color: tuple = (255, 60, 80)) -> Image.Image:
    """Draw a minimal play-button icon."""
    size = 64
    img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d    = ImageDraw.Draw(img)
    # Circle background
    d.ellipse([2, 2, size-2, size-2], fill=(30, 30, 30, 220))
    # Play triangle
    margin = 18
    pts = [
        (margin + 4, margin - 2),
        (margin + 4, size - margin + 2),
        (size - margin + 4, size // 2),
    ]
    d.polygon(pts, fill=color)
    return img


def _make_icon_paused() -> Image.Image:
    size = 64
    img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d    = ImageDraw.Draw(img)
    d.ellipse([2, 2, size-2, size-2], fill=(30, 30, 30, 220))
    # Two pause bars
    d.rectangle([18, 16, 26, 48], fill=(255, 200, 0, 255))
    d.rectangle([36, 16, 44, 48], fill=(255, 200, 0, 255))
    return img


def _make_icon_stopped() -> Image.Image:
    size = 64
    img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d    = ImageDraw.Draw(img)
    d.ellipse([2, 2, size-2, size-2], fill=(30, 30, 30, 220))
    d.rectangle([18, 18, 46, 46], fill=(160, 160, 160, 200))
    return img


# ── Status polling ────────────────────────────────────────────────────────────
_state_cache = {}
_icon_ref    = None


def _poll_status():
    global _state_cache
    while True:
        time.sleep(3)
        try:
            r = _send({"action": "status"})
            if r and r.get("ok"):
                _state_cache = r.get("status", {})
                _refresh_icon()
        except Exception:
            pass


def _refresh_icon():
    global _icon_ref
    if _icon_ref is None:
        return
    s = _state_cache
    if s.get("playing") and not s.get("paused"):
        _icon_ref.icon  = _make_icon()
        title = s.get("current_title", "Playing")
        _icon_ref.title = f"YPlay ▶ {title[:40]}"
    elif s.get("paused"):
        _icon_ref.icon  = _make_icon_paused()
        _icon_ref.title = "YPlay ⏸ Paused"
    else:
        _icon_ref.icon  = _make_icon_stopped()
        _icon_ref.title = "YPlay ⏹ Stopped"


# ── Tray menu actions ─────────────────────────────────────────────────────────
def _tk_hidden_root():
    """Return a hidden Tk root for dialogs."""
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    return root


def action_play(icon, item_):
    root = _tk_hidden_root()
    url = simpledialog.askstring(
        "Play YouTube",
        "Enter YouTube URL or video ID:",
        parent=root,
    )
    root.destroy()
    if not url:
        return
    if not url.startswith("http"):
        url = f"https://www.youtube.com/watch?v={url}"
    _send({"action": "play", "url": url})


def action_pause(icon, item_):
    _send({"action": "pause"})


def action_resume(icon, item_):
    _send({"action": "resume"})


def action_stop(icon, item_):
    _send({"action": "stop"})


def action_volume(icon, item_):
    root = _tk_hidden_root()
    vol = simpledialog.askinteger(
        "Volume",
        "Set volume (0–150):",
        minvalue=0, maxvalue=150,
        parent=root,
    )
    root.destroy()
    if vol is not None:
        _send({"action": "volume", "level": vol})


def action_status(icon, item_):
    r = _send({"action": "status"})
    if r and r.get("ok"):
        s = r["status"]
        if s.get("playing"):
            state_str = "⏸ PAUSED" if s.get("paused") else "▶ PLAYING"
            msg = (
                f"{state_str}\n"
                f"Track:  {s.get('current_title', '?')}\n"
                f"Volume: {s.get('volume')}%"
            )
        else:
            msg = "⏹ STOPPED"
        root = _tk_hidden_root()
        messagebox.showinfo("YPlay Status", msg, parent=root)
        root.destroy()


def action_next(icon, item_):
    _send({"action": "next"})


def action_prev(icon, item_):
    _send({"action": "prev"})


def action_exit(icon, item_):
    _send({"action": "exit"})
    time.sleep(0.4)
    icon.stop()


# ── Main tray loop ────────────────────────────────────────────────────────────
def main():
    global _icon_ref
    _ensure_daemon()

    menu = pystray.Menu(
        item("▶  Play URL...",   action_play, default=True),
        item("⏸  Pause / Resume", action_pause),
        item("⏩  Next",           action_next),
        item("⏪  Prev",           action_prev),
        item("⏹  Stop",           action_stop),
        pystray.Menu.SEPARATOR,
        item("🔊  Volume...",      action_volume),
        item("ℹ️  Status",         action_status),
        pystray.Menu.SEPARATOR,
        item("✖  Exit YPlay",     action_exit),
    )

    icon = pystray.Icon(
        "YPlay",
        _make_icon_stopped(),
        "YPlay ⏹ Stopped",
        menu,
    )
    _icon_ref = icon

    # Background poll thread
    t = threading.Thread(target=_poll_status, daemon=True)
    t.start()

    icon.run()


if __name__ == "__main__":
    main()
