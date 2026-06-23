#!/usr/bin/env bash
# build_fxpack.sh — Complete MSYS2 MINGW64 setup + build guide (as a runnable script)
#
# Copy-paste each block into your MINGW64 terminal, OR run this whole file:
#   bash build_fxpack.sh
#
# Assumes your project root is at:   ~/FXPack   (adjust PROJ below if not)

set -e
PROJ="$HOME/FXPack"   # ← change this if your folder is elsewhere
cd "$PROJ"

# ─────────────────────────────────────────────────────────────────────────────
# BLOCK 1 — Install required MSYS2 packages (one-time, run as normal user)
# ─────────────────────────────────────────────────────────────────────────────
pacman -Syu --noconfirm
pacman -S --needed --noconfirm \
    mingw-w64-x86_64-gcc \
    mingw-w64-x86_64-gcc-libs \
    mingw-w64-x86_64-binutils \
    make

# ─────────────────────────────────────────────────────────────────────────────
# BLOCK 2 — Verify compiler is on PATH
# ─────────────────────────────────────────────────────────────────────────────
x86_64-w64-mingw32-g++ --version
which x86_64-w64-mingw32-g++

# ─────────────────────────────────────────────────────────────────────────────
# BLOCK 3 — Create the full directory tree
# ─────────────────────────────────────────────────────────────────────────────
mkdir -p src include build/Release build/Debug \
         bundle/FXPack.ofx.bundle/Contents/Win64

# ─────────────────────────────────────────────────────────────────────────────
# BLOCK 4 — Build (Release)
# ─────────────────────────────────────────────────────────────────────────────
mingw32-make

# ─────────────────────────────────────────────────────────────────────────────
# BLOCK 5 — Build (Debug, optional)
# ─────────────────────────────────────────────────────────────────────────────
# mingw32-make DEBUG=1

# ─────────────────────────────────────────────────────────────────────────────
# BLOCK 6 — Verify the .ofx binary looks correct
# ─────────────────────────────────────────────────────────────────────────────
file bundle/FXPack.ofx.bundle/Contents/Win64/FXPack.ofx

# Expected output:
#   FXPack.ofx: PE32+ executable (DLL) (GUI) x86-64, for MS Windows

# Check the two required exports are present
x86_64-w64-mingw32-objdump -p bundle/FXPack.ofx.bundle/Contents/Win64/FXPack.ofx \
    | grep -E "OfxGetNumberOfPlugins|OfxGetPlugin"

# Expected output (two lines):
#   [  0] OfxGetNumberOfPlugins
#   [  1] OfxGetPlugin

# ─────────────────────────────────────────────────────────────────────────────
# BLOCK 7 — Install into DaVinci Resolve
# (Run MINGW64 terminal as Administrator for this block only)
# ─────────────────────────────────────────────────────────────────────────────
OFX_DIR="/c/Program Files/Common Files/OFX/Plugins"
BUNDLE_SRC="bundle/FXPack.ofx.bundle"
BUNDLE_DST="$OFX_DIR/FXPack.ofx.bundle"

mkdir -p "$BUNDLE_DST/Contents/Win64"
cp -rf "$BUNDLE_SRC/." "$BUNDLE_DST/"
echo "Installed to: $BUNDLE_DST"

# ─────────────────────────────────────────────────────────────────────────────
# After installation: close Resolve completely, relaunch it, then look in
# Effects Library → OpenFX → FXPack
# ─────────────────────────────────────────────────────────────────────────────
