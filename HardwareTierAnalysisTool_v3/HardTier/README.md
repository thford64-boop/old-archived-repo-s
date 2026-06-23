# Hardware Tier Analysis Tool v3

A Windows-native multi-language project that scans your system hardware,
matches it against a curated benchmark library, and produces a detailed
**Hardware Hierarchy Report** showing where your machine sits relative to
every tier in the library. Includes **battery health analysis** for laptops.

**v3 improvements over v2:**
- Scanner uses `systeminfo` for richer data: manufacturer, model, BIOS, time zone, last boot, hotfix count, NIC count
- **Battery scanning**: charge level, status, chemistry, health %, cycle count (laptops only)
- Expanded library: **80 CPUs x 85 GPUs** (was 30x30)
- Library includes integrated GPUs (AMD Radeon Graphics, Intel Iris Xe, etc.)
- Analyzer handles both v2 and v3 JSON formats (backward compatible)
- New **Upgrade Advice** and **Battery** sections in reports
- Better fuzzy matching threshold for generic GPU names
- Fixed: `run_analysis.bat` no longer crashes with `: was unexpected at this time`
- Fixed: `scanner.exe` no longer blocks the pipeline waiting for keyboard input

---

## IMPORTANT: Updating from a Previous Version

You **must replace all three core files** when updating. Do not mix versions:

| File | Action |
|------|--------|
| `run_analysis.bat` | Replace old file |
| `scanner.c` | Replace old file |
| `analyzer.py` | Replace old file |
| `hardware_library.json` | Keep yours (backward compatible) |

Easiest method: delete the old three files, drop in the new ones, done.

---

## Project Structure

```
HardwareTierAnalysisTool/
|-- scanner.c              <- C program (systeminfo + PowerShell + WinAPI + battery)
|-- analyzer.py            <- Python script -- library comparison & report
|-- hardware_library.json  <- Benchmark library (80 CPUs x 85 GPUs)
|-- run_analysis.bat       <- One-click build + run pipeline
|-- instructions.txt       <- Plain English setup + usage guide
|
|   (generated at runtime)
|-- scanner.exe            <- Compiled scanner binary
|-- local_specs.json       <- Scanned hardware output (v3 format)
+-- hardware_report.txt    <- Final hierarchy report
```

---

## Requirements

| Requirement | Notes |
|-------------|-------|
| Windows 10 / 11 | systeminfo, PowerShell, and Windows API are Windows-only |
| GCC / MinGW-w64 | Add `bin\` to `PATH`. [Download MSYS2](https://www.msys2.org/) |
| Python 3.8+ | Standard library only -- no pip installs needed |

### Install MinGW-w64 via MSYS2 (recommended)

```powershell
# In MSYS2 UCRT64 shell:
pacman -S mingw-w64-ucrt-x86_64-gcc
# Then add C:\msys64\ucrt64\bin to your Windows PATH
```

---

## Quick Start

Double-click **`run_analysis.bat`** or run from a command prompt:

```cmd
cd HardwareTierAnalysisTool
run_analysis.bat
```

The script will:
1. **Compile** `scanner.c` -> `scanner.exe`
2. **Run** the scanner -> writes `local_specs.json` (takes ~15-20 sec)
3. **Run** the Python analyzer -> prints + saves `hardware_report.txt`

---

## Manual Steps

### Compile only
```cmd
gcc scanner.c -o scanner.exe -O2
```
Fallback (if the above fails):
```cmd
gcc scanner.c -o scanner.exe -lole32 -loleaut32 -lwbemuuid -lws2_32 -DUNICODE -D_UNICODE -O2
```

### Run scanner only
```cmd
scanner.exe
```

### Run analyzer only (requires existing local_specs.json)
```cmd
python analyzer.py
```

---

## What `local_specs.json` Contains (v3)

```json
{
  "scanner_version": "3.0.0",
  "system": {
    "host_name": "DOG",
    "manufacturer": "HP",
    "model": "HP ENVY x360 2-in-1 Laptop 15-ey0xxx",
    "type": "x64-based PC",
    "bios_version": "Insyde F.14, 7/5/2023",
    "domain": "WORKGROUP",
    "logon_server": "\\\\DOG",
    "time_zone": "(UTC-06:00) Central Time (US & Canada)",
    "boot_time": "6/5/2026, 11:06:51 PM"
  },
  "os": {
    "name": "Microsoft Windows 10 Home",
    "version": "10.0.19045 N/A Build 19045"
  },
  "cpu": { "model": "...", "logical_cores": 12, "physical_cores": 6, "base_mhz": 2301 },
  "ram": { "total_gb": 16, "total_mb": 15680, "available_mb": 5637 },
  "gpu": { "model": "...", "driver_version": "...", "vram": "...", "all_gpus": "..." },
  "hotfixes_installed": 13,
  "nics_installed": 5,
  "battery": {
    "present": true,
    "charge_pct": 87,
    "status": "AC - Full",
    "chemistry": "Li-Ion",
    "design_capacity_mwh": 55000,
    "full_capacity_mwh": 48200,
    "health_pct": 87,
    "cycle_count": 214
  }
}
```

Battery fields when no battery is detected (desktop):
```json
"battery": { "present": false, "charge_pct": 0, "status": "None", ... }
```

---

## Report Sections

| Section | Contents |
|---------|----------|
| SYSTEM SNAPSHOT | OS, model, CPU, RAM, GPU, BIOS, time zone, boot time, hotfixes, NICs, battery status |
| CPU ANALYSIS | Library match, score, tier, percentile, distribution chart, top 5 outperformed, next 5 upgrade targets |
| GPU ANALYSIS | Same as CPU analysis for your GPU |
| RAM CONTEXT | Capacity tier (F through S+) with description |
| BATTERY | Charge bar, status, chemistry, health % with grade, capacity (Wh), cycle count with wear assessment |
| UPGRADE ADVICE | Targeted tips based on your component scores |
| OVERALL SUMMARY | Combined CPU+GPU percentile, verdict (Elite / High Performer / etc.) |

---

## Tier Scale (PassMark-inspired)

| Range | Tier | Description |
|-------|------|-------------|
| < 2,000 | F | Below entry-level |
| 2,000-5,000 | E | Entry-level |
| 5,000-10,000 | D | Budget |
| 10,000-20,000 | C | Mainstream |
| 20,000-35,000 | B | Enthusiast |
| 35,000-55,000 | A | High-End |
| 55,000-75,000 | S | Flagship / Workstation |
| 75,000+ | S+ | Absolute Pinnacle |

Score reference: [CPU Benchmark](https://www.cpubenchmark.net) - [GPU Benchmark](https://www.videocardbenchmark.net)

---

## Extending the Library

`hardware_library.json` uses a simple schema -- add entries freely:

```json
{
  "id":      "cpu_081",
  "model":   "AMD Ryzen 9 9950X",
  "tier":    "S+",
  "cores":   32,
  "score":   82000,
  "notes":   "Zen 5 flagship"
}
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `run_analysis.bat` crashes with `: was unexpected at this time` | You are running an **old version**. Replace `run_analysis.bat` with the new one. |
| `[ERROR] Spec file not found: local_specs.json` when running `analyzer.py` directly | Run `scanner.exe` first, or use `run_analysis.bat` which does this automatically. |
| `gcc: command not found` | Open a **new** CMD window after adding MinGW to PATH. Old windows don't pick up PATH changes. |
| Compilation fails with `undefined reference to WMI` | Use extended flags: `gcc scanner.c -o scanner.exe -lole32 -loleaut32 -lwbemuuid -lws2_32 -DUNICODE -D_UNICODE -O2` |
| GPU shows "Could not match..." | Add your GPU manually to `hardware_library.json` under `gpu_library`. |
| Battery cycle count shows "Not reported" | Your laptop firmware does not expose `BatteryCycleCount` via ACPI WMI. This is a hardware limitation. |
| `systeminfo` hangs for 30+ seconds | Normal on first run -- it queries WMI internally. Wait it out. |

---

## License

MIT -- free to use, modify, and distribute.
