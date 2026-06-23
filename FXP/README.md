# FXPack — OFX Plugin Suite for DaVinci Resolve

A collection of 5 CPU-based OpenFX effects built for DaVinci Resolve 20.  
All effects support both **8-bit** and **32-bit float** pipelines and are fully keyframeable.

---

## Effects

### 🔵 FXPack Gaussian Blur
Two-pass separable Gaussian blur with independent horizontal and vertical radius control.

| Parameter | Range | Default | Description |
|-----------|-------|---------|-------------|
| Radius X | 0–100 | 5 | Blur radius in pixels (horizontal pass) |
| Radius Y | 0–100 | 5 | Blur radius in pixels (vertical pass) |

> Set Radius X and Y independently to create directional motion blur looks.

---

### ✨ FXPack Glow/Bloom
Threshold-based bloom — bright areas spread light additively onto the image.  
Uses a fast 3-pass box blur approximation of Gaussian for large radii.

| Parameter | Range | Default | Description |
|-----------|-------|---------|-------------|
| Threshold | 0–1 | 0.7 | Luminance level above which glow is generated |
| Glow Radius | 1–80 | 15 | Spread of the bloom in pixels |
| Glow Intensity | 0–5 | 1.0 | Strength of the additive bloom composite |
| Glow Saturation | 0–2 | 0.8 | 0 = white glow, 1 = matches source colour |

> Lower the threshold to bloom shadows; raise saturation for colourful neon looks.

---

### 🎞️ FXPack Film Grain
Animated per-frame pseudo-random film grain using a fast LCG noise generator.  
Grain pattern changes every frame based on time and speed — no two frames are identical.

| Parameter | Range | Default | Description |
|-----------|-------|---------|-------------|
| Grain Intensity | 0–1 | 0.3 | Amount of grain (0 = none, 1 = heavy) |
| Grain Size | 1–8 | 1 | Pixel size of individual grain particles |
| Color Grain | on/off | off | Enable RGB colour grain instead of luminance-only |
| Animation Speed | 0.1–10 | 1.0 | How fast the grain pattern changes per frame |

> Color Grain off = classic B&W film feel. Color Grain on = pushed colour negative look.

---

### 📷 FXPack Camera Shake
Simulates handheld or earthquake camera motion via per-frame pixel offset and rotation.  
Blends between a smooth sine wave and random noise for natural-feeling motion.

| Parameter | Range | Default | Description |
|-----------|-------|---------|-------------|
| Intensity | 0–200 | 20 | Maximum shake displacement in pixels |
| Frequency | 0.1–60 | 8.0 | Shakes per second — higher = faster trembling |
| Randomness | 0–1 | 0.7 | 0 = regular sine wave, 1 = fully random noise |
| Max Rotation | 0–15° | 1.0 | Maximum rotation in degrees added by shake |

> Intensity is keyframeable — ramp it up on a hit frame and back down for impact shake.

---

### 🎬 FXPack Transitions
Cross-dissolve and zoom transitions between two clips. Apply via the **Transitions** tab in the Effects Library (drag to the cut point between two clips).

| Parameter | Range | Default | Description |
|-----------|-------|---------|-------------|
| Transition | 0–1 | 0 | Progress from source (0) to destination (1) — driven automatically by Resolve |
| Transition Type | — | Cross Dissolve | Cross Dissolve / Zoom / Dissolve + Zoom |
| Zoom Scale | 1–4 | 1.5 | Maximum zoom amount during zoom transition |

> All three modes use smoothstep easing automatically for a polished look.

---

## Installation

### Requirements
- Windows 10/11 x64
- DaVinci Resolve 17 or later (tested on Resolve 20)
- MSYS2 with MINGW64 (for building from source)

### Pre-built install
If you already have `FXPack.ofx` built:

1. Open **MSYS2 MINGW64 as Administrator**
2. Run:
```bash
mkdir -p "/c/Program Files/Common Files/OFX/Plugins"
cp -rf bundle/FXPack.ofx.bundle "/c/Program Files/Common Files/OFX/Plugins/"
```
3. Fully close and relaunch DaVinci Resolve
4. Open **Effects → Open FX** — FXPack will appear

---

## Building from Source

### 1. Install MSYS2
Download from [msys2.org](https://www.msys2.org) and install. Open the **MINGW64** terminal.

### 2. Install the toolchain (one-time)
```bash
pacman -Syu --noconfirm
pacman -S --needed --noconfirm mingw-w64-x86_64-gcc mingw-w64-x86_64-binutils make
```

### 3. Arrange files
```
FXPack/
├── Makefile
├── src/
│   ├── FXPackPlugin.cpp
│   ├── FXPack.def
│   ├── effectBlur.cpp
│   ├── effectGlow.cpp
│   ├── effectGrain.cpp
│   ├── effectShake.cpp
│   └── effectTransition.cpp
├── include/
│   ├── ofxCore.h
│   ├── pluginGlobals.h
│   ├── effectBlur.h
│   ├── effectGlow.h
│   ├── effectGrain.h
│   ├── effectShake.h
│   └── effectTransition.h
└── bundle/
    └── FXPack.ofx.bundle/
        └── Contents/
            ├── Info.plist
            └── Win64/
```

Or from a flat folder, run this one-liner to arrange and build in one shot:
```bash
mkdir -p src include bundle/FXPack.ofx.bundle/Contents/Win64 && mv effectBlur.cpp effectGlow.cpp effectGrain.cpp effectShake.cpp effectTransition.cpp FXPackPlugin.cpp FXPack.def src/ && mv effectBlur.h effectGlow.h effectGrain.h effectShake.h effectTransition.h ofxCore.h pluginGlobals.h include/ && mv Info.plist bundle/FXPack.ofx.bundle/Contents/ && make
```

### 4. Build
```bash
cd /path/to/FXPack
make
```

Output: `bundle/FXPack.ofx.bundle/Contents/Win64/FXPack.ofx`

### 5. Install (Administrator terminal)
```bash
mkdir -p "/c/Program Files/Common Files/OFX/Plugins"
cp -rf bundle/FXPack.ofx.bundle "/c/Program Files/Common Files/OFX/Plugins/"
```

---

## Project Structure

```
FXPack/
├── src/
│   ├── FXPackPlugin.cpp       — OFX entry point, plugin registration, action dispatch
│   ├── FXPack.def             — DLL export definition (OfxGetNumberOfPlugins, OfxGetPlugin)
│   ├── effectBlur.cpp         — Separable Gaussian blur (two-pass)
│   ├── effectGlow.cpp         — Threshold bloom with box-blur approximation
│   ├── effectGrain.cpp        — Animated LCG film grain
│   ├── effectShake.cpp        — Sine + noise camera shake with rotation
│   └── effectTransition.cpp   — Cross-dissolve and zoom transition
├── include/
│   ├── ofxCore.h              — Minimal OFX API definitions
│   ├── pluginGlobals.h        — Shared suite pointers and helper macros
│   └── effect*.h              — Per-effect declarations
├── bundle/
│   └── FXPack.ofx.bundle/     — OFX bundle (copied to OFX/Plugins to install)
│       └── Contents/
│           ├── Info.plist     — Bundle metadata
│           └── Win64/
│               └── FXPack.ofx — The compiled plugin (DLL renamed .ofx)
├── Makefile                   — MSYS2 MINGW64 build file
└── README.md                  — This file
```

---

## Tips for Use in Resolve

- **Blur + Glow combo:** stack Gaussian Blur first, then Glow on top for a dreamy diffusion look
- **Grain on top of grade:** apply Film Grain as the last effect in the chain so it sits on top of colour work
- **Shake on action hits:** keyframe Intensity to 0 before the hit frame, spike it to 80–100 on the hit, back to 0 two frames later
- **Transitions:** drag FXPack Transitions to the **cut point** between two clips (not onto a clip) — Resolve drives the Transition parameter automatically

---

## License

MIT — free to use, modify, and distribute.
