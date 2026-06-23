r"""
yplay_daemon.py — Background audio daemon for YPlay
Runs as a hidden process, survives CMD closure, controls mpv subprocess.
Communicates via Windows Named Pipe: \\.\pipe\yplay
"""

import sys
import os
import json
import time
import threading
import subprocess
import ctypes
import ctypes.wintypes
import logging
import signal
import re
import tempfile

# ── Logging (file only, no console) ──────────────────────────────────────────
LOG_PATH = os.path.join(os.environ.get("APPDATA", tempfile.gettempdir()), "yplay", "daemon.log")
os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)

logging.basicConfig(
    filename=LOG_PATH,
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("yplay-daemon")

# ── Constants ─────────────────────────────────────────────────────────────────
PIPE_NAME        = r"\\.\pipe\yplay"
PIPE_BUFFER_SIZE = 65536
STATE_PATH       = os.path.join(os.path.dirname(LOG_PATH), "state.json")
YTDLP_PATH       = os.environ.get("YTDLP_PATH", "yt-dlp")
MPV_PATH         = os.environ.get("MPV_PATH", "mpv")

# ── Win32 named-pipe constants ────────────────────────────────────────────────
PIPE_ACCESS_DUPLEX       = 0x00000003
PIPE_TYPE_MESSAGE        = 0x00000004
PIPE_READMODE_MESSAGE    = 0x00000002
PIPE_WAIT                = 0x00000000
FILE_FLAG_OVERLAPPED     = 0x40000000
PIPE_UNLIMITED_INSTANCES = 255
INVALID_HANDLE_VALUE     = ctypes.wintypes.HANDLE(-1).value
ERROR_PIPE_CONNECTED     = 535
ERROR_NO_DATA            = 232

kernel32 = ctypes.windll.kernel32


# ─────────────────────────────────────────────────────────────────────────────
# Player state
# ─────────────────────────────────────────────────────────────────────────────
class PlayerState:
    def __init__(self):
        self.lock         = threading.Lock()
        self.mpv_proc     = None      # subprocess.Popen
        self.mpv_ipc_path = None      # mpv --input-ipc-server path
        self.current_url  = ""
        self.current_title= ""
        self.volume       = 80        # 0-100
        self.paused       = False
        self.playing      = False
        self.queue        = []
        self.queue_idx    = -1
        self._resolve_thread = None

    def to_dict(self):
        with self.lock:
            return {
                "playing":       self.playing,
                "paused":        self.paused,
                "volume":        self.volume,
                "current_url":   self.current_url,
                "current_title": self.current_title,
                "queue_length":  len(self.queue),
                "queue_idx":     self.queue_idx,
            }


state = PlayerState()


# ─────────────────────────────────────────────────────────────────────────────
# yt-dlp helpers
# ─────────────────────────────────────────────────────────────────────────────
def resolve_audio_url(youtube_url: str) -> tuple[str, str]:
    """
    Returns (stream_url, title) using yt-dlp.
    Picks bestaudio, prefers opus/webm to avoid transcode overhead.
    """
    log.info(f"Resolving audio URL for: {youtube_url}")
    cmd = [
        YTDLP_PATH,
        "--no-playlist",
        "-f", "bestaudio[ext=webm]/bestaudio[ext=m4a]/bestaudio",
        "--get-url",
        "--get-title",
        "--no-warnings",
        youtube_url,
    ]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp error: {result.stderr.strip()}")

    lines = [l.strip() for l in result.stdout.strip().splitlines() if l.strip()]
    if len(lines) < 2:
        raise RuntimeError("yt-dlp returned unexpected output")

    # yt-dlp --get-title --get-url outputs: title first, then URL
    title, stream_url = lines[0], lines[1]
    log.info(f"Resolved: {title} → {stream_url[:80]}...")
    return stream_url, title


# ─────────────────────────────────────────────────────────────────────────────
# mpv control via IPC socket (JSON protocol)
# ─────────────────────────────────────────────────────────────────────────────
class MpvIPC:
    """
    Sends commands to mpv's --input-ipc-server (Windows named pipe).
    mpv on Windows uses a named pipe for its IPC.
    """
    PIPE_TIMEOUT = 2000  # ms

    def __init__(self, ipc_path: str):
        self.ipc_path = ipc_path
        self._id = 0

    def _next_id(self):
        self._id += 1
        return self._id

    def send(self, command: list) -> dict | None:
        payload = json.dumps({"command": command, "request_id": self._next_id()}) + "\n"
        try:
            # Open mpv's IPC pipe
            h = kernel32.CreateFileW(
                self.ipc_path,
                0xC0000000,  # GENERIC_READ | GENERIC_WRITE
                0,
                None,
                3,           # OPEN_EXISTING
                0,
                None,
            )
            if h == INVALID_HANDLE_VALUE:
                return None

            data = payload.encode()
            written = ctypes.wintypes.DWORD(0)
            kernel32.WriteFile(h, data, len(data), ctypes.byref(written), None)

            buf = ctypes.create_string_buffer(4096)
            read = ctypes.wintypes.DWORD(0)
            kernel32.ReadFile(h, buf, len(buf), ctypes.byref(read), None)
            kernel32.CloseHandle(h)

            response = buf.raw[:read.value].decode(errors="replace").strip()
            if response:
                return json.loads(response)
        except Exception as e:
            log.debug(f"MpvIPC.send error: {e}")
        return None

    def set_property(self, prop: str, value) -> bool:
        r = self.send(["set_property", prop, value])
        return r is not None

    def get_property(self, prop: str):
        r = self.send(["get_property", prop])
        if r and r.get("error") == "success":
            return r.get("data")
        return None

    def command(self, *args) -> bool:
        r = self.send(list(args))
        return r is not None


# ─────────────────────────────────────────────────────────────────────────────
# Player control functions
# ─────────────────────────────────────────────────────────────────────────────
def _mpv_ipc_path() -> str:
    return r"\\.\pipe\yplay-mpv"


def _kill_mpv():
    with state.lock:
        if state.mpv_proc and state.mpv_proc.poll() is None:
            try:
                state.mpv_proc.terminate()
                state.mpv_proc.wait(timeout=3)
            except Exception:
                pass
        state.mpv_proc  = None
        state.playing   = False
        state.paused    = False
        state.current_url   = ""
        state.current_title = ""


def _spawn_mpv(stream_url: str, title: str):
    """Launch mpv in audio-only, headless, background mode."""
    _kill_mpv()

    ipc = _mpv_ipc_path()
    cmd = [
        MPV_PATH,
        "--no-video",
        "--no-terminal",
        "--audio-display=no",
        f"--input-ipc-server={ipc}",
        f"--volume={state.volume}",
        "--keep-open=no",
        "--idle=no",
        "--really-quiet",
        stream_url,
    ]

    log.info(f"Spawning mpv: {' '.join(cmd[:6])} ...")
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS,
    )

    with state.lock:
        state.mpv_proc      = proc
        state.mpv_ipc_path  = ipc
        state.current_url   = title   # store title here for display
        state.current_title = title
        state.playing       = True
        state.paused        = False

    log.info(f"mpv PID={proc.pid} playing: {title}")


def cmd_play(url: str) -> dict:
    """Resolve + play a YouTube URL (runs yt-dlp in background thread)."""
    def _do():
        try:
            stream_url, title = resolve_audio_url(url)
            _spawn_mpv(stream_url, title)
            save_state()
        except Exception as e:
            log.error(f"Play error: {e}")
            with state.lock:
                state.playing = False
                state.current_title = f"Error: {e}"

    t = threading.Thread(target=_do, daemon=True)
    t.start()
    state._resolve_thread = t
    return {"ok": True, "msg": "Resolving audio stream, playback starting shortly..."}


def cmd_pause() -> dict:
    if not state.playing:
        return {"ok": False, "msg": "Nothing is playing"}
    ipc = MpvIPC(_mpv_ipc_path())
    if state.paused:
        ipc.set_property("pause", False)
        state.paused = False
        return {"ok": True, "msg": "Resumed"}
    else:
        ipc.set_property("pause", True)
        state.paused = True
        return {"ok": True, "msg": "Paused"}


def cmd_resume() -> dict:
    if not state.playing:
        return {"ok": False, "msg": "Nothing is playing"}
    ipc = MpvIPC(_mpv_ipc_path())
    ipc.set_property("pause", False)
    state.paused = False
    return {"ok": True, "msg": "Resumed"}


def cmd_stop() -> dict:
    _kill_mpv()
    save_state()
    return {"ok": True, "msg": "Stopped"}


def cmd_volume(vol: int) -> dict:
    vol = max(0, min(150, int(vol)))
    state.volume = vol
    if state.playing:
        ipc = MpvIPC(_mpv_ipc_path())
        ipc.set_property("volume", vol)
    save_state()
    return {"ok": True, "msg": f"Volume set to {vol}"}


def cmd_status() -> dict:
    s = state.to_dict()
    if state.mpv_proc and state.mpv_proc.poll() is not None:
        # mpv died (song ended)
        state.playing = False
        state.paused  = False
        s = state.to_dict()
    return {"ok": True, "status": s}


def cmd_queue_add(url: str) -> dict:
    state.queue.append(url)
    return {"ok": True, "msg": f"Added to queue (pos {len(state.queue)})"}


def cmd_queue_next() -> dict:
    if not state.queue:
        return {"ok": False, "msg": "Queue is empty"}
    state.queue_idx = (state.queue_idx + 1) % len(state.queue)
    url = state.queue[state.queue_idx]
    return cmd_play(url)


def cmd_queue_prev() -> dict:
    if not state.queue:
        return {"ok": False, "msg": "Queue is empty"}
    state.queue_idx = (state.queue_idx - 1) % len(state.queue)
    url = state.queue[state.queue_idx]
    return cmd_play(url)


def cmd_exit() -> dict:
    _kill_mpv()
    log.info("Daemon exit requested")
    threading.Thread(target=lambda: (time.sleep(0.3), os._exit(0)), daemon=True).start()
    return {"ok": True, "msg": "Daemon shutting down"}


# ─────────────────────────────────────────────────────────────────────────────
# State persistence
# ─────────────────────────────────────────────────────────────────────────────
def save_state():
    try:
        with open(STATE_PATH, "w") as f:
            json.dump(state.to_dict(), f, indent=2)
    except Exception as e:
        log.warning(f"save_state error: {e}")


def load_state():
    try:
        if os.path.exists(STATE_PATH):
            with open(STATE_PATH) as f:
                d = json.load(f)
            state.volume = d.get("volume", 80)
            log.info(f"Loaded state: volume={state.volume}")
    except Exception as e:
        log.warning(f"load_state error: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Named-pipe IPC server
# ─────────────────────────────────────────────────────────────────────────────
DISPATCH = {
    "play":       lambda args: cmd_play(args.get("url", "")),
    "pause":      lambda args: cmd_pause(),
    "resume":     lambda args: cmd_resume(),
    "stop":       lambda args: cmd_stop(),
    "volume":     lambda args: cmd_volume(args.get("level", 80)),
    "status":     lambda args: cmd_status(),
    "queue_add":  lambda args: cmd_queue_add(args.get("url", "")),
    "next":       lambda args: cmd_queue_next(),
    "prev":       lambda args: cmd_queue_prev(),
    "exit":       lambda args: cmd_exit(),
}


def _handle_client(h_pipe):
    """Read one request from a pipe instance, dispatch, write response."""
    try:
        buf  = ctypes.create_string_buffer(PIPE_BUFFER_SIZE)
        read = ctypes.wintypes.DWORD(0)
        ok   = kernel32.ReadFile(h_pipe, buf, PIPE_BUFFER_SIZE, ctypes.byref(read), None)
        if not ok or read.value == 0:
            return

        raw = buf.raw[:read.value].decode(errors="replace").strip()
        log.debug(f"IPC recv: {raw}")

        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            response = {"ok": False, "msg": "Invalid JSON"}
        else:
            action = msg.get("action", "")
            handler = DISPATCH.get(action)
            if handler:
                response = handler(msg)
            else:
                response = {"ok": False, "msg": f"Unknown action: {action}"}

        log.debug(f"IPC send: {response}")
        data    = json.dumps(response).encode()
        written = ctypes.wintypes.DWORD(0)
        kernel32.WriteFile(h_pipe, data, len(data), ctypes.byref(written), None)

    except Exception as e:
        log.error(f"_handle_client error: {e}")
    finally:
        kernel32.FlushFileBuffers(h_pipe)
        kernel32.DisconnectNamedPipe(h_pipe)
        kernel32.CloseHandle(h_pipe)


def pipe_server_loop():
    """
    Continuously creates new pipe instances and waits for clients.
    Each connected client is handled in a short-lived thread.
    """
    log.info(f"Pipe server listening on {PIPE_NAME}")
    while True:
        h_pipe = kernel32.CreateNamedPipeW(
            PIPE_NAME,
            PIPE_ACCESS_DUPLEX,
            PIPE_TYPE_MESSAGE | PIPE_READMODE_MESSAGE | PIPE_WAIT,
            PIPE_UNLIMITED_INSTANCES,
            PIPE_BUFFER_SIZE,
            PIPE_BUFFER_SIZE,
            0,
            None,
        )
        if h_pipe == INVALID_HANDLE_VALUE:
            err = kernel32.GetLastError()
            log.error(f"CreateNamedPipe failed: {err}")
            time.sleep(1)
            continue

        # Block until a client connects
        connected = kernel32.ConnectNamedPipe(h_pipe, None)
        err = kernel32.GetLastError()

        if connected or err == ERROR_PIPE_CONNECTED:
            t = threading.Thread(target=_handle_client, args=(h_pipe,), daemon=True)
            t.start()
        else:
            kernel32.CloseHandle(h_pipe)


# ─────────────────────────────────────────────────────────────────────────────
# Watchdog: restart mpv if it dies mid-queue
# ─────────────────────────────────────────────────────────────────────────────
def _watchdog():
    while True:
        time.sleep(3)
        with state.lock:
            proc    = state.mpv_proc
            playing = state.playing

        if playing and proc is not None and proc.poll() is not None:
            log.info("mpv process died — track ended or crashed")
            with state.lock:
                state.playing = False
                state.paused  = False
            # Auto-advance queue if items remain
            if state.queue and state.queue_idx < len(state.queue) - 1:
                log.info("Auto-advancing queue")
                cmd_queue_next()


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────
def main():
    log.info("=" * 60)
    log.info("YPlay daemon starting")
    log.info(f"Log: {LOG_PATH}")
    log.info(f"State: {STATE_PATH}")

    load_state()

    # Watchdog thread
    threading.Thread(target=_watchdog, daemon=True).start()

    # IPC pipe server (blocking, this is the main thread's job)
    try:
        pipe_server_loop()
    except KeyboardInterrupt:
        log.info("Daemon interrupted")
        _kill_mpv()


if __name__ == "__main__":
    main()
