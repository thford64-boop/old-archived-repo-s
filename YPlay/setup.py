"""
setup.py — YPlay one-time setup script
Run once to:
  - Check Python version
  - Install pip packages (pystray, Pillow)
  - Check for yt-dlp and mpv in PATH (or common install locations)
  - Create yplay.bat in the project folder for easy CLI use
  - Optionally add a Start Menu shortcut for the tray app
"""

import sys
import os
import subprocess
import shutil
import textwrap

HERE = os.path.dirname(os.path.abspath(__file__))
SRC  = os.path.join(HERE, "src")

# ── Console colours ────────────────────────────────────────────────────────────
RED    = "\033[91m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

try:
    import ctypes
    k = ctypes.windll.kernel32
    h = k.GetStdHandle(-11)
    m = ctypes.wintypes.DWORD(); k.GetConsoleMode(h, ctypes.byref(m))
    k.SetConsoleMode(h, m.value | 0x0004)
except Exception:
    pass

LINE = f"{BOLD}{'─'*60}{RESET}"


def ok(msg):  print(f"  {GREEN}✓{RESET}  {msg}")
def err(msg): print(f"  {RED}✗{RESET}  {msg}")
def warn(msg):print(f"  {YELLOW}!{RESET}  {msg}")
def hdr(msg): print(f"\n{LINE}\n  {BOLD}{msg}{RESET}\n{LINE}")


# ─────────────────────────────────────────────────────────────────────────────
hdr("YPlay Setup")
print(f"\n  Installing to: {CYAN}{HERE}{RESET}")

# ── Python version ────────────────────────────────────────────────────────────
hdr("1 · Python version")
major, minor = sys.version_info[:2]
print(f"  Python {major}.{minor}")
if major < 3 or minor < 10:
    err("Python 3.10+ required (needed for match statements, union types)")
    sys.exit(1)
ok("Python version OK")

# ── pip packages ──────────────────────────────────────────────────────────────
hdr("2 · Installing pip packages")
PACKAGES = ["pystray", "Pillow"]
for pkg in PACKAGES:
    print(f"  Installing {CYAN}{pkg}{RESET}...")
    r = subprocess.run(
        [sys.executable, "-m", "pip", "install", pkg, "--quiet"],
        capture_output=True, text=True,
    )
    if r.returncode == 0:
        ok(pkg)
    else:
        warn(f"{pkg} install may have failed: {r.stderr.strip()[:120]}")

# ── yt-dlp check ──────────────────────────────────────────────────────────────
hdr("3 · Checking yt-dlp")
ytdlp = shutil.which("yt-dlp")
if ytdlp:
    ok(f"Found: {ytdlp}")
else:
    warn("yt-dlp not found in PATH.")
    print(f"""
  Install options:
    {CYAN}winget install yt-dlp.yt-dlp{RESET}
    {CYAN}pip install yt-dlp{RESET}
    Or download from: https://github.com/yt-dlp/yt-dlp/releases
    Place yt-dlp.exe somewhere in your PATH (e.g. C:\\Windows\\System32).
""")
    ans = input("  Install via pip now? [y/N] ").strip().lower()
    if ans == "y":
        subprocess.run([sys.executable, "-m", "pip", "install", "yt-dlp", "--quiet"])
        ok("yt-dlp installed via pip")
    else:
        warn("Skipping — install yt-dlp before using YPlay")

# ── mpv check ────────────────────────────────────────────────────────────────
hdr("4 · Checking mpv")
mpv_bin = shutil.which("mpv")
if mpv_bin:
    ok(f"Found: {mpv_bin}")
else:
    warn("mpv not found in PATH.")
    print(f"""
  Install options:
    {CYAN}winget install mpv.mpv{RESET}
    Or download from: https://mpv.io/installation/
    Place mpv.exe somewhere in your PATH (e.g. C:\\tools\\mpv\\).
    The %MPV_PATH% environment variable can override the path if needed.
""")

# ── Create yplay.bat CLI wrapper ───────────────────────────────────────────────
hdr("5 · Creating CLI wrapper")
bat_path = os.path.join(HERE, "yplay.bat")
bat = textwrap.dedent(f"""\
    @echo off
    :: YPlay CLI wrapper — add this folder to PATH for global access
    python "{os.path.join(SRC, 'yplay.py')}" %*
""")
with open(bat_path, "w") as f:
    f.write(bat)
ok(f"Created: {bat_path}")

# ── Create start_tray.bat shortcut ───────────────────────────────────────────
tray_bat = os.path.join(HERE, "yplay_tray.bat")
pythonw  = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
if not os.path.exists(pythonw):
    pythonw = sys.executable
with open(tray_bat, "w") as f:
    f.write(f'@echo off\nstart "" "{pythonw}" "{os.path.join(SRC, "yplay_tray.pyw")}"\n')
ok(f"Created: {tray_bat}")

# ── Create start_gui.bat shortcut ─────────────────────────────────────────────
gui_bat = os.path.join(HERE, "yplay_gui.bat")
with open(gui_bat, "w") as f:
    f.write(f'@echo off\nstart "" "{pythonw}" "{os.path.join(SRC, "yplay_gui.pyw")}"\n')
ok(f"Created: {gui_bat}")

# ── PATH reminder ─────────────────────────────────────────────────────────────
hdr("6 · PATH setup (optional)")
print(f"""
  To use  {CYAN}yplay{RESET}  from anywhere, add this folder to your PATH:
    {CYAN}{HERE}{RESET}

  Quick method (run as Admin in PowerShell):
    {CYAN}$env:PATH += ";{HERE}"; [Environment]::SetEnvironmentVariable("PATH", $env:PATH, "Machine"){RESET}

  Or manually: Settings → System → Advanced → Environment Variables → Path
""")

# ── Done ──────────────────────────────────────────────────────────────────────
hdr("Setup complete!")
print(f"""
  {BOLD}Quick start:{RESET}
    {CYAN}yplay start{RESET}                           — start background daemon
    {CYAN}yplay play https://youtu.be/dQw4w9WgXcQ{RESET}  — play a video
    {CYAN}yplay pause{RESET}                           — pause/resume
    {CYAN}yplay volume 70{RESET}                       — set volume
    {CYAN}yplay status{RESET}                          — show what's playing
    {CYAN}yplay exit{RESET}                            — stop and kill daemon

  {BOLD}System tray (no terminal needed):{RESET}
    Double-click  {CYAN}yplay_tray.bat{RESET}

  {BOLD}Floating GUI:{RESET}
    Double-click  {CYAN}yplay_gui.bat{RESET}

  {BOLD}Daemon log:{RESET}
    {CYAN}%APPDATA%\\yplay\\daemon.log{RESET}
""")
