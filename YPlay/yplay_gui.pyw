"""
yplay_gui.pyw — Minimal floating GUI for YPlay
A compact always-on-top window: URL bar, transport controls, volume slider.
No console. Requires only tkinter (stdlib).
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
from tkinter import ttk, font as tkfont


# ── IPC ───────────────────────────────────────────────────────────────────────
PIPE_NAME = r"\\.\pipe\yplay"
kernel32  = ctypes.windll.kernel32


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
    if _send({"action": "status"}) is None:
        here    = os.path.dirname(os.path.abspath(__file__))
        daemon  = os.path.join(here, "yplay_daemon.py")
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


# ── Color scheme ──────────────────────────────────────────────────────────────
BG         = "#0f0f0f"
BG2        = "#1a1a1a"
BG3        = "#252525"
ACCENT     = "#ff3c50"
ACCENT2    = "#ff6b7a"
FG         = "#e8e8e8"
FG_DIM     = "#888"
BTN_PLAY   = "#22c55e"
BTN_PAUSE  = "#eab308"
BTN_STOP   = "#ef4444"
BTN_NAV    = "#3b82f6"


# ── Main GUI class ────────────────────────────────────────────────────────────
class YPlayGUI:
    WIDTH  = 420
    HEIGHT = 220
    POLL   = 2500   # ms between status polls

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("YPlay")
        self.root.geometry(f"{self.WIDTH}x{self.HEIGHT}+80+80")
        self.root.configure(bg=BG)
        self.root.resizable(False, False)
        self.root.attributes("-topmost", True)

        # Remove default title bar decorations on Win10/11
        # (keep a minimal custom header for dragging)
        self.root.overrideredirect(True)

        self._drag_x = 0
        self._drag_y = 0

        self._build_ui()
        self._poll()

    # ── UI Construction ────────────────────────────────────────────────────────
    def _build_ui(self):
        r = self.root

        # ── Custom title bar ────────────────────────────────────────────────
        hdr = tk.Frame(r, bg=BG3, height=28)
        hdr.pack(fill="x")

        tk.Label(hdr, text="  ♪  YPlay", bg=BG3, fg=ACCENT,
                 font=("Segoe UI", 9, "bold")).pack(side="left", padx=4)

        btn_close = tk.Label(hdr, text="✕", bg=BG3, fg=FG_DIM,
                             font=("Segoe UI", 10), cursor="hand2", padx=8)
        btn_close.pack(side="right")
        btn_close.bind("<Button-1>", self._on_close)

        btn_min = tk.Label(hdr, text="─", bg=BG3, fg=FG_DIM,
                           font=("Segoe UI", 10), cursor="hand2", padx=8)
        btn_min.pack(side="right")
        btn_min.bind("<Button-1>", lambda e: self.root.iconify())

        hdr.bind("<ButtonPress-1>",   self._drag_start)
        hdr.bind("<B1-Motion>",       self._drag_move)

        # ── Now-playing label ───────────────────────────────────────────────
        self.lbl_track = tk.Label(r, text="⏹  Stopped", bg=BG, fg=FG_DIM,
                                  font=("Segoe UI", 9), anchor="w", wraplength=400)
        self.lbl_track.pack(fill="x", padx=10, pady=(6, 0))

        # ── URL entry row ───────────────────────────────────────────────────
        url_frame = tk.Frame(r, bg=BG)
        url_frame.pack(fill="x", padx=10, pady=(4, 0))

        self.url_var = tk.StringVar()
        url_entry = tk.Entry(
            url_frame, textvariable=self.url_var,
            bg=BG2, fg=FG, insertbackground=FG,
            relief="flat", font=("Consolas", 9),
            bd=0, highlightthickness=1,
            highlightcolor=ACCENT, highlightbackground=BG3,
        )
        url_entry.pack(side="left", fill="x", expand=True, ipady=4, padx=(0, 6))
        url_entry.bind("<Return>", lambda e: self._play())
        url_entry.insert(0, "https://youtube.com/watch?v=...")
        url_entry.bind("<FocusIn>",  lambda e: (url_entry.delete(0, "end") if url_entry.get().startswith("https://youtube.com/watch?v=...") else None))

        btn_play = tk.Button(
            url_frame, text="▶ Play", bg=BTN_PLAY, fg="#000",
            font=("Segoe UI", 9, "bold"), relief="flat",
            cursor="hand2", padx=8, pady=3,
            command=self._play,
        )
        btn_play.pack(side="left")

        # ── Transport controls ──────────────────────────────────────────────
        ctrl_frame = tk.Frame(r, bg=BG)
        ctrl_frame.pack(pady=6)

        def _btn(parent, text, color, cmd, width=6):
            b = tk.Button(parent, text=text, bg=color, fg="#fff" if color != BTN_PAUSE else "#000",
                          font=("Segoe UI", 9, "bold"), relief="flat",
                          cursor="hand2", padx=6, pady=3, width=width, command=cmd)
            b.pack(side="left", padx=3)
            return b

        _btn(ctrl_frame, "⏪",     BTN_NAV,   self._prev,   width=3)
        self.btn_pause = _btn(ctrl_frame, "⏸ Pause", BTN_PAUSE, self._pause,  width=8)
        _btn(ctrl_frame, "⏹ Stop", BTN_STOP,  self._stop,   width=8)
        _btn(ctrl_frame, "⏩",     BTN_NAV,   self._next,   width=3)

        # ── Volume row ──────────────────────────────────────────────────────
        vol_frame = tk.Frame(r, bg=BG)
        vol_frame.pack(fill="x", padx=10, pady=(2, 6))

        tk.Label(vol_frame, text="🔊", bg=BG, fg=FG_DIM,
                 font=("Segoe UI", 9)).pack(side="left")

        self.vol_var = tk.IntVar(value=80)
        vol_slider = ttk.Scale(
            vol_frame, from_=0, to=150,
            variable=self.vol_var, orient="horizontal",
            command=self._on_volume,
        )
        # Style the slider
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Horizontal.TScale", background=BG,
                        troughcolor=BG3, sliderthickness=14)
        vol_slider.pack(side="left", fill="x", expand=True, padx=6)

        self.lbl_vol = tk.Label(vol_frame, text="80%", bg=BG, fg=FG_DIM,
                                font=("Segoe UI", 8), width=4)
        self.lbl_vol.pack(side="left")

        # ── Status bar ──────────────────────────────────────────────────────
        self.lbl_status = tk.Label(
            r, text="Daemon connecting...", bg=BG3, fg=FG_DIM,
            font=("Segoe UI", 7), anchor="w",
        )
        self.lbl_status.pack(fill="x", side="bottom", ipady=2, padx=0)

    # ── Drag support ───────────────────────────────────────────────────────────
    def _drag_start(self, e):
        self._drag_x = e.x
        self._drag_y = e.y

    def _drag_move(self, e):
        dx = e.x - self._drag_x
        dy = e.y - self._drag_y
        x  = self.root.winfo_x() + dx
        y  = self.root.winfo_y() + dy
        self.root.geometry(f"+{x}+{y}")

    # ── Actions ────────────────────────────────────────────────────────────────
    def _play(self):
        url = self.url_var.get().strip()
        if not url or url.startswith("https://youtube.com/watch?v=..."):
            return
        if not url.startswith("http"):
            url = f"https://www.youtube.com/watch?v={url}"
        self.lbl_status.config(text="Resolving stream...")
        self.root.update_idletasks()
        threading.Thread(target=lambda: _send({"action": "play", "url": url}), daemon=True).start()

    def _pause(self):
        r = _send({"action": "pause"})
        if r:
            self.lbl_status.config(text=r.get("msg", ""))

    def _stop(self):
        _send({"action": "stop"})

    def _next(self):
        _send({"action": "next"})

    def _prev(self):
        _send({"action": "prev"})

    def _on_volume(self, val):
        v = int(float(val))
        self.lbl_vol.config(text=f"{v}%")
        # Throttle: only send when user releases or every ~200ms
        if hasattr(self, "_vol_job"):
            self.root.after_cancel(self._vol_job)
        self._vol_job = self.root.after(200, lambda: _send({"action": "volume", "level": v}))

    def _on_close(self, e=None):
        # Close GUI only — daemon keeps running
        self.root.destroy()

    # ── Status polling ─────────────────────────────────────────────────────────
    def _poll(self):
        def _do():
            r = _send({"action": "status"})
            if r and r.get("ok"):
                s = r["status"]
                self.root.after(0, lambda: self._update_ui(s))
            else:
                self.root.after(0, lambda: self.lbl_status.config(
                    text="Daemon not running — run 'yplay start'", fg="#ef4444"))
            self.root.after(self.POLL, self._poll)
        threading.Thread(target=_do, daemon=True).start()

    def _update_ui(self, s: dict):
        vol = s.get("volume", 80)
        self.vol_var.set(vol)
        self.lbl_vol.config(text=f"{vol}%")

        if s.get("playing"):
            title = s.get("current_title", "Unknown")
            if s.get("paused"):
                self.lbl_track.config(text=f"⏸  {title}", fg=BTN_PAUSE)
                self.btn_pause.config(text="▶ Resume")
                self.lbl_status.config(text="Paused", fg=FG_DIM)
            else:
                self.lbl_track.config(text=f"▶  {title}", fg=BTN_PLAY)
                self.btn_pause.config(text="⏸ Pause")
                self.lbl_status.config(text="Playing", fg=BTN_PLAY)
        else:
            self.lbl_track.config(text="⏹  Stopped", fg=FG_DIM)
            self.btn_pause.config(text="⏸ Pause")
            self.lbl_status.config(text="Stopped", fg=FG_DIM)

    # ── Run ────────────────────────────────────────────────────────────────────
    def run(self):
        self.root.mainloop()


# ─────────────────────────────────────────────────────────────────────────────
def main():
    _ensure_daemon()
    app = YPlayGUI()
    app.run()


if __name__ == "__main__":
    main()
