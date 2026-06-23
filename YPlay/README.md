# YPlay 🎵
### Lightweight Background YouTube Audio Player for Windows 10/11

No browser. No Electron. No spyware. Just audio.

---

## What It Is

YPlay is a three-piece Python app:

| Component | File | Purpose |
|-----------|------|---------|
| **Daemon** | `src/yplay_daemon.py` | Background process — controls mpv, owns all state |
| **CLI** | `src/yplay.py` | Terminal client — sends commands to daemon |
| **Tray** | `src/yplay_tray.pyw` | System tray icon — GUI control (optional) |
| **GUI** | `src/yplay_gui.pyw` | Floating mini-player window (optional) |

---

## Requirements

| Tool | Purpose | Install |
|------|---------|---------|
| **Python 3.10+** | Runtime | https://python.org |
| **yt-dlp** | Stream URL extraction | `winget install yt-dlp.yt-dlp` or `pip install yt-dlp` |
| **mpv** | Audio playback | `winget install mpv.mpv` or https://mpv.io |
| **pystray** | System tray (optional) | `pip install pystray` |
| **Pillow** | Tray icon rendering (optional) | `pip install Pillow` |

---

## Installation

### 1. One-time setup
```bat
python setup.py
```
This installs pip packages, checks for yt-dlp/mpv, and creates `.bat` launcher files.

### 2. Add to PATH (optional, for global `yplay` command)
```powershell
# Run as Administrator
$old = [Environment]::GetEnvironmentVariable("PATH","Machine")
[Environment]::SetEnvironmentVariable("PATH", "$old;C:\path\to\yplay", "Machine")
```

---

## Usage

### CLI
```bat
yplay start                                    :: launch daemon
yplay play https://youtu.be/dQw4w9WgXcQ       :: play by URL
yplay play dQw4w9WgXcQ                         :: or bare video ID
yplay pause                                    :: toggle pause/resume
yplay resume                                   :: resume if paused
yplay stop                                     :: stop playback
yplay volume 70                                :: set volume (0-150)
yplay status                                   :: show current state
yplay queue https://youtu.be/another_video     :: add to queue
yplay next                                     :: next in queue
yplay prev                                     :: previous in queue
yplay exit                                     :: stop daemon completely
yplay log                                      :: show log file path
```

### System Tray (no terminal)
Double-click `yplay_tray.bat` — a tray icon appears (bottom-right).
Right-click for the menu.

### Floating GUI
Double-click `yplay_gui.bat` — a compact always-on-top player appears.

---

## Architecture

### Why it works after closing CMD

```
CMD (closes) ──► yplay.py ──► Named Pipe ──► yplay_daemon.py (lives on)
                                                      │
                                          subprocess.DETACHED_PROCESS
                                          CREATE_NO_WINDOW
                                          CREATE_NEW_PROCESS_GROUP
                                                      │
                                              yt-dlp (resolve URL)
                                                      │
                                              mpv (play audio) ◄── mpv IPC pipe
```

**Key flags used in `subprocess.Popen`:**
- `DETACHED_PROCESS` — severs the new process from the parent's console session
- `CREATE_NO_WINDOW` — no console window is created
- `CREATE_NEW_PROCESS_GROUP` — new process group, immune to Ctrl+C propagation
- `pythonw.exe` — Python interpreter with no console attachment at all

### IPC: Windows Named Pipe

All control flows through a Named Pipe at `\\.\pipe\yplay`.

```
Client                           Daemon
  │── JSON: {"action":"play"...} ──►│
  │◄── JSON: {"ok":true,...}    ────│
```

Protocol is simple JSON, one request/response per connection. Message-mode pipes ensure clean framing with no length-prefix needed.

### mpv Control: mpv's own IPC pipe

```
Daemon ──► mpv --input-ipc-server=\\.\pipe\yplay-mpv
         │
         └── JSON commands: set_property, get_property, etc.
```

mpv is launched with:
- `--no-video` — audio only
- `--no-terminal` — no console output
- `--audio-display=no` — suppresses album-art window
- `--input-ipc-server` — named pipe for runtime control

### Stream Resolution (yt-dlp)

```python
yt-dlp --get-url --get-title -f "bestaudio[ext=webm]/bestaudio[ext=m4a]/bestaudio" <url>
```

Picks highest quality audio stream. Prefers WebM/Opus (no transcoding overhead). Returns a direct HTTPS stream URL that mpv plays natively.

### State Machine

```
STOPPED ──► play() ──► RESOLVING ──► PLAYING ──► PAUSED
    ▲                      │              │          │
    └──────── stop() ──────┘         pause()    resume()
                           └─── error ──► STOPPED
```

State is persisted to `%APPDATA%\yplay\state.json` for crash recovery (volume setting preserved across restarts).

---

## File Layout

```
yplay/
├── README.md
├── setup.py              ← run once to set up
├── yplay.bat             ← created by setup.py — CLI launcher
├── yplay_tray.bat        ← created by setup.py — tray launcher
├── yplay_gui.bat         ← created by setup.py — GUI launcher
└── src/
    ├── yplay_daemon.py   ← background daemon (run via pythonw)
    ├── yplay.py          ← CLI client
    ├── yplay_tray.pyw    ← system tray (pystray + Pillow)
    └── yplay_gui.pyw     ← floating mini-player (tkinter only)
```

---

## Troubleshooting

**Audio doesn't start:**
```bat
yplay log
:: then open the log file to see yt-dlp/mpv errors
```

**"Daemon not running":**
```bat
yplay start
:: or manually:
pythonw src\yplay_daemon.py
```

**yt-dlp format errors (age-restricted or geo-blocked):**
```bat
yt-dlp --cookies-from-browser chrome <url>   :: use browser cookies
```
Then set `YTDLP_EXTRA_ARGS=--cookies-from-browser chrome` or pass the stream URL directly.

**mpv not found:**
Set the environment variable `MPV_PATH=C:\tools\mpv\mpv.exe` before starting.

**Volume above 100%:**
YPlay supports 0–150% (mpv's software volume boost). Values above 100 may distort.

---

## Privacy

- Zero telemetry, zero cloud, zero accounts
- Only network traffic: YouTube stream requests (yt-dlp + mpv)
- All IPC is local named pipes (not TCP, not loopback, not internet)
- No data leaves your machine

---

## Extending

### Add a playlist file
```python
# In yplay.py, add a "playlist" command:
if cmd == "playlist":
    with open(sys.argv[2]) as f:
        for line in f:
            url = line.strip()
            if url:
                send({"action": "queue_add", "url": url})
    send({"action": "next"})
```

### Auto-start with Windows
```bat
:: Add to shell:startup (Win+R → shell:startup)
start "" "C:\path\to\yplay\yplay_tray.bat"
```

### Custom mpv options
Edit `_spawn_mpv()` in `yplay_daemon.py` to add flags like:
- `--af=lavfi=[loudnorm]` — loudness normalization
- `--ao=wasapi` — WASAPI audio output (lower latency)
- `--audio-channels=stereo` — force stereo

---

## License

Do whatever you want with this. No warranty.
