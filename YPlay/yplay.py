"""
yplay.py — CLI client for YPlay daemon
Usage:
  yplay play <url>
  yplay pause
  yplay resume
  yplay stop
  yplay volume <0-150>
  yplay status
  yplay next / prev
  yplay queue <url>
  yplay exit
  yplay start       (launches daemon if not running)
"""

import sys
import os
import json
import ctypes
import ctypes.wintypes
import subprocess
import time
import argparse

PIPE_NAME = r"\\.\pipe\yplay"
TIMEOUT_MS = 5000

kernel32 = ctypes.windll.kernel32

# ANSI colors (Windows 10+ supports them in terminal)
RED    = "\033[91m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def _enable_ansi():
    """Enable ANSI escape codes on Windows console."""
    try:
        import ctypes
        k = ctypes.windll.kernel32
        h = k.GetStdHandle(-11)
        mode = ctypes.wintypes.DWORD()
        k.GetConsoleMode(h, ctypes.byref(mode))
        k.SetConsoleMode(h, mode.value | 0x0004)
    except Exception:
        pass

_enable_ansi()


# ─────────────────────────────────────────────────────────────────────────────
# IPC
# ─────────────────────────────────────────────────────────────────────────────
def _send(payload: dict) -> dict | None:
    """Send a command to the daemon and return the response."""
    GENERIC_READ  = 0x80000000
    GENERIC_WRITE = 0x40000000
    OPEN_EXISTING = 3
    INVALID_HANDLE = ctypes.wintypes.HANDLE(-1).value

    h = kernel32.CreateFileW(
        PIPE_NAME,
        GENERIC_READ | GENERIC_WRITE,
        0,
        None,
        OPEN_EXISTING,
        0,
        None,
    )

    if h == INVALID_HANDLE:
        return None   # daemon not running

    try:
        # Switch to message-read mode
        mode = ctypes.wintypes.DWORD(0x00000002)  # PIPE_READMODE_MESSAGE
        kernel32.SetNamedPipeHandleState(h, ctypes.byref(mode), None, None)

        data    = json.dumps(payload).encode()
        written = ctypes.wintypes.DWORD(0)
        kernel32.WriteFile(h, data, len(data), ctypes.byref(written), None)

        buf  = ctypes.create_string_buffer(65536)
        read = ctypes.wintypes.DWORD(0)
        kernel32.ReadFile(h, buf, len(buf), ctypes.byref(read), None)

        raw = buf.raw[:read.value].decode(errors="replace").strip()
        if raw:
            return json.loads(raw)
    finally:
        kernel32.CloseHandle(h)
    return None


def send(payload: dict) -> dict:
    """Send with auto-start fallback."""
    r = _send(payload)
    if r is not None:
        return r

    # Daemon not running — start it
    print(f"{YELLOW}Daemon not running. Starting...{RESET}")
    start_daemon()
    time.sleep(1.5)

    r = _send(payload)
    if r is None:
        print(f"{RED}Could not connect to daemon after start. Check logs.{RESET}")
        daemon_log = os.path.join(os.environ.get("APPDATA", ""), "yplay", "daemon.log")
        print(f"  Log: {daemon_log}")
        sys.exit(1)
    return r


# ─────────────────────────────────────────────────────────────────────────────
# Daemon management
# ─────────────────────────────────────────────────────────────────────────────
def _daemon_script_path() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, "yplay_daemon.py")


def start_daemon():
    """
    Launch daemon as a detached hidden process using pythonw.exe.
    pythonw has no console window; DETACHED_PROCESS ensures it survives
    closure of the launching terminal.
    """
    daemon_py = _daemon_script_path()
    if not os.path.exists(daemon_py):
        print(f"{RED}Cannot find daemon: {daemon_py}{RESET}")
        sys.exit(1)

    # Use pythonw (no console) if available, else python with hidden window
    pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    if not os.path.exists(pythonw):
        pythonw = sys.executable

    subprocess.Popen(
        [pythonw, daemon_py],
        creationflags=(
            subprocess.DETACHED_PROCESS |
            subprocess.CREATE_NO_WINDOW |
            subprocess.CREATE_NEW_PROCESS_GROUP
        ),
        close_fds=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    print(f"{GREEN}Daemon started.{RESET}")


def stop_daemon():
    r = _send({"action": "exit"})
    if r:
        print(f"{GREEN}{r.get('msg', 'Done')}{RESET}")
    else:
        print(f"{YELLOW}Daemon was not running.{RESET}")


def is_daemon_alive() -> bool:
    return _send({"action": "status"}) is not None


# ─────────────────────────────────────────────────────────────────────────────
# Pretty output
# ─────────────────────────────────────────────────────────────────────────────
def print_response(r: dict):
    ok  = r.get("ok", False)
    msg = r.get("msg", "")
    if msg:
        color = GREEN if ok else RED
        print(f"{color}{msg}{RESET}")


def print_status(r: dict):
    s = r.get("status", {})
    if not s:
        print_response(r)
        return

    print(f"\n{BOLD}{'─'*44}{RESET}")
    if s.get("playing"):
        state_str = f"{YELLOW}⏸ PAUSED{RESET}" if s.get("paused") else f"{GREEN}▶ PLAYING{RESET}"
        print(f"  Status : {state_str}")
        print(f"  Track  : {CYAN}{s.get('current_title', '?')}{RESET}")
    else:
        print(f"  Status : {YELLOW}⏹ STOPPED{RESET}")
    print(f"  Volume : {s.get('volume', '?')}%")
    q = s.get("queue_length", 0)
    if q:
        print(f"  Queue  : {q} item(s), idx={s.get('queue_idx', -1)}")
    print(f"{BOLD}{'─'*44}{RESET}\n")


# ─────────────────────────────────────────────────────────────────────────────
# CLI dispatch
# ─────────────────────────────────────────────────────────────────────────────
HELP = f"""
{BOLD}YPlay — Lightweight Background YouTube Audio Player{RESET}

{CYAN}USAGE:{RESET}
  yplay <command> [args]

{CYAN}COMMANDS:{RESET}
  {GREEN}start{RESET}              Start the background daemon
  {GREEN}play <url>{RESET}         Play a YouTube URL or video ID
  {GREEN}pause{RESET}              Toggle pause/resume
  {GREEN}resume{RESET}             Resume if paused
  {GREEN}stop{RESET}               Stop playback
  {GREEN}volume <0-150>{RESET}     Set volume (default 80)
  {GREEN}status{RESET}             Show current playback status
  {GREEN}queue <url>{RESET}        Add URL to queue
  {GREEN}next{RESET}               Skip to next in queue
  {GREEN}prev{RESET}               Go to previous in queue
  {GREEN}exit{RESET}               Stop playback and kill daemon
  {GREEN}log{RESET}                Show daemon log path

{CYAN}EXAMPLES:{RESET}
  yplay play https://youtu.be/dQw4w9WgXcQ
  yplay volume 60
  yplay pause
  yplay status
"""


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        print(HELP)
        return

    cmd = sys.argv[1].lower()

    if cmd == "start":
        if is_daemon_alive():
            print(f"{GREEN}Daemon is already running.{RESET}")
        else:
            start_daemon()
        return

    if cmd == "log":
        path = os.path.join(os.environ.get("APPDATA", ""), "yplay", "daemon.log")
        print(f"Daemon log: {CYAN}{path}{RESET}")
        return

    if cmd == "exit":
        stop_daemon()
        return

    if cmd == "play":
        if len(sys.argv) < 3:
            print(f"{RED}Usage: yplay play <url>{RESET}")
            sys.exit(1)
        url = sys.argv[2]
        # Normalise bare video IDs
        if not url.startswith("http"):
            url = f"https://www.youtube.com/watch?v={url}"
        r = send({"action": "play", "url": url})
        print_response(r)
        return

    if cmd == "volume":
        if len(sys.argv) < 3:
            print(f"{RED}Usage: yplay volume <0-150>{RESET}")
            sys.exit(1)
        try:
            lvl = int(sys.argv[2])
        except ValueError:
            print(f"{RED}Volume must be an integer 0-150{RESET}")
            sys.exit(1)
        r = send({"action": "volume", "level": lvl})
        print_response(r)
        return

    if cmd == "queue":
        if len(sys.argv) < 3:
            print(f"{RED}Usage: yplay queue <url>{RESET}")
            sys.exit(1)
        url = sys.argv[2]
        if not url.startswith("http"):
            url = f"https://www.youtube.com/watch?v={url}"
        r = send({"action": "queue_add", "url": url})
        print_response(r)
        return

    SIMPLE = {
        "pause":  {"action": "pause"},
        "resume": {"action": "resume"},
        "stop":   {"action": "stop"},
        "status": {"action": "status"},
        "next":   {"action": "next"},
        "prev":   {"action": "prev"},
    }

    if cmd in SIMPLE:
        r = send(SIMPLE[cmd])
        if cmd == "status":
            print_status(r)
        else:
            print_response(r)
        return

    print(f"{RED}Unknown command: {cmd}{RESET}")
    print(f"Run  {CYAN}yplay help{RESET}  for usage.")
    sys.exit(1)


if __name__ == "__main__":
    main()
