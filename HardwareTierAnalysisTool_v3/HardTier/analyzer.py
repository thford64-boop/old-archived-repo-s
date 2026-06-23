#!/usr/bin/env python3
"""
Hardware Tier Analysis Tool — Analyzer v2
analyzer.py

Reads hardware_library.json and local_specs.json (scanner v3 format),
then produces a detailed Hardware Hierarchy Report showing where the
scanned system sits relative to the full library.

Supports both scanner v2 (legacy) and scanner v3 (systeminfo-backed) JSON.
"""

import json
import os
import sys
import re
from datetime import datetime
from pathlib import Path


# ─────────────────────────────────────────────────────────────
#  Config
# ─────────────────────────────────────────────────────────────
LIBRARY_FILE = "hardware_library.json"
SPECS_FILE   = "local_specs.json"
REPORT_FILE  = "hardware_report.txt"

TIER_ORDER = ["F", "E", "D", "C", "B", "A", "S", "S+"]
TIER_LABELS = {
    "F":  "Below Entry-Level",
    "E":  "Entry-Level",
    "D":  "Budget",
    "C":  "Mainstream",
    "B":  "Enthusiast",
    "A":  "High-End",
    "S":  "Flagship / Workstation",
    "S+": "Absolute Pinnacle",
}
TIER_ICONS = {
    "F": "░", "E": "▒", "D": "▓",
    "C": "█", "B": "◆", "A": "◈",
    "S": "★", "S+": "✦",
}


# ─────────────────────────────────────────────────────────────
#  Compat: normalize both v2 and v3 local_specs formats
# ─────────────────────────────────────────────────────────────
def normalize_specs(raw: dict) -> dict:
    """
    Scanner v2 had flat os string; v3 nests it under os.name.
    Also v3 adds system{}, hotfixes, nics, etc.
    Return a uniform dict with keys: os_str, cpu, ram, gpu, system, extras.
    """
    version = raw.get("scanner_version", "2.0.0")

    # OS string
    if isinstance(raw.get("os"), dict):
        os_str = raw["os"].get("name", "Unknown")
    else:
        os_str = raw.get("os", "Unknown")

    # CPU
    cpu = raw.get("cpu", {})

    # RAM
    ram = raw.get("ram", {})

    # GPU
    gpu = raw.get("gpu", {})

    # System block (v3 only)
    system = raw.get("system", {})

    extras = {
        "hotfixes": raw.get("hotfixes_installed", None),
        "nics":     raw.get("nics_installed", None),
        "version":  version,
        "battery":  raw.get("battery", {}),
    }

    return {
        "os_str":  os_str,
        "cpu":     cpu,
        "ram":     ram,
        "gpu":     gpu,
        "system":  system,
        "extras":  extras,
    }


# ─────────────────────────────────────────────────────────────
#  Fuzzy matching
# ─────────────────────────────────────────────────────────────
def _tokenize(s: str) -> set:
    s = s.lower()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    return set(s.split())


def fuzzy_score_match(scanned: str, lib_model: str) -> float:
    a = _tokenize(scanned)
    b = _tokenize(lib_model)
    if not a or not b:
        return 0.0
    overlap = len(a & b)
    return overlap / min(len(a), len(b))


def find_best_library_match(scanned_model: str, library: list, threshold: float = 0.50):
    """
    Find best match. Lower threshold (0.50 vs 0.55) helps catch
    generic names like 'AMD Radeon Graphics'.
    """
    best_entry = None
    best_score = 0.0
    for entry in library:
        s = fuzzy_score_match(scanned_model, entry["model"])
        if s > best_score:
            best_score = s
            best_entry = entry
    if best_score >= threshold:
        return best_entry, best_score
    return None, 0.0


# ─────────────────────────────────────────────────────────────
#  Hierarchy analysis
# ─────────────────────────────────────────────────────────────
def analyze_component(scanned_model: str, score: int, library: list, component_type: str):
    below = [e for e in library if e["score"] <  score]
    equal = [e for e in library if e["score"] == score]
    above = [e for e in library if e["score"] >  score]
    total = len(library)

    pct_below = (len(below) / total * 100) if total else 0
    pct_equal = (len(equal) / total * 100) if total else 0
    pct_above = (len(above) / total * 100) if total else 0

    return {
        "component_type":    component_type,
        "scanned_model":     scanned_model,
        "resolved_score":    score,
        "total_in_library":  total,
        "below_count":       len(below),
        "equal_count":       len(equal),
        "above_count":       len(above),
        "pct_below":         round(pct_below, 1),
        "pct_equal":         round(pct_equal, 1),
        "pct_above":         round(pct_above, 1),
        "below_entries":     sorted(below, key=lambda x: x["score"], reverse=True),
        "above_entries":     sorted(above, key=lambda x: x["score"]),
    }


# ─────────────────────────────────────────────────────────────
#  Tier distribution bar
# ─────────────────────────────────────────────────────────────
def tier_distribution(library: list, highlight_tier: str) -> str:
    counts = {t: 0 for t in TIER_ORDER}
    for e in library:
        t = e.get("tier", "?")
        if t in counts:
            counts[t] += 1
    total = sum(counts.values()) or 1
    lines = []
    for t in TIER_ORDER:
        c = counts[t]
        bar_len = int(c / total * 36)
        bar = "█" * bar_len
        marker = " ◄ YOUR HARDWARE" if t == highlight_tier else ""
        lines.append(f"  {t:2s}  [{bar:<36}] {c:2d}{marker}")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────
#  Progress bar helper
# ─────────────────────────────────────────────────────────────
def progress_bar(pct: float, width: int = 40) -> str:
    filled = int(pct / 100 * width)
    return "█" * filled + "░" * (width - filled)


# ─────────────────────────────────────────────────────────────
#  Upgrade advice
# ─────────────────────────────────────────────────────────────
def upgrade_advice(cpu_pct: float, gpu_match, gpu_pct: float, ram_gb: int) -> str:
    lines = []
    if ram_gb < 16:
        lines.append("  💡 RAM: Upgrading to 16 GB is the highest-value upgrade for under $30.")
    if gpu_match is None:
        lines.append("  💡 GPU: No GPU match found — consider adding a discrete card for major gains.")
    elif gpu_pct < 30:
        lines.append("  💡 GPU: Your GPU is a significant bottleneck. A mid-range upgrade would transform performance.")
    if cpu_pct < 20:
        lines.append("  💡 CPU: Your CPU is aging; even a budget platform upgrade would help.")
    if not lines:
        lines.append("  ✅ Your system is well-balanced. No urgent upgrade needed.")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────
#  Report generation
# ─────────────────────────────────────────────────────────────
def build_report(specs: dict, library: dict) -> str:
    lines = []
    sep  = "═" * 72
    thin = "─" * 72

    def h1(title): lines.append(f"\n{sep}\n  {title}\n{sep}")
    def h2(title): lines.append(f"\n{thin}\n  {title}\n{thin}")
    def add(*args): lines.append(" ".join(str(a) for a in args))

    os_str = specs["os_str"]
    cpu    = specs["cpu"]
    ram    = specs["ram"]
    gpu    = specs["gpu"]
    system = specs["system"]
    extras = specs["extras"]

    # ── Header ────────────────────────────────────────────────
    lines.append(sep)
    lines.append("  ██╗  ██╗ █████╗ ██████╗ ██████╗     ████████╗██╗███████╗██████╗")
    lines.append("  ██║  ██║██╔══██╗██╔══██╗██╔══██╗       ██╔══╝██║██╔════╝██╔══██╗")
    lines.append("  ███████║███████║██████╔╝██║  ██║        ██║   ██║█████╗  ██████╔╝")
    lines.append("  ██╔══██║██╔══██║██╔══██╗██║  ██║        ██║   ██║██╔══╝  ██╔══██╗")
    lines.append("  ██║  ██║██║  ██║██║  ██║██████╔╝        ██║   ██║███████╗██║  ██║")
    lines.append("  ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝         ╚═╝   ╚═╝╚══════╝╚═╝  ╚═╝")
    lines.append(sep)
    lines.append(f"  Hardware Hierarchy Report  |  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"  Scanner version: {extras.get('version', 'unknown')}")
    lines.append(sep)

    # ── System Snapshot ───────────────────────────────────────
    h1("SYSTEM SNAPSHOT")
    add(f"  Operating System   : {os_str}")
    if system.get("manufacturer") and system["manufacturer"] != "Unknown":
        add(f"  System Manufacturer: {system['manufacturer']}")
    if system.get("model") and system["model"] != "Unknown":
        add(f"  System Model       : {system['model']}")
    if system.get("type") and system["type"] != "Unknown":
        add(f"  System Type        : {system['type']}")
    add(f"  CPU Model          : {cpu.get('model', 'Unknown')}")
    add(f"  Logical Cores      : {cpu.get('logical_cores', '?')}")
    if cpu.get("physical_cores") and cpu["physical_cores"] != cpu.get("logical_cores"):
        add(f"  Physical Cores     : {cpu.get('physical_cores', '?')}")
    if cpu.get("base_mhz") and cpu["base_mhz"] > 0:
        add(f"  CPU Base Speed     : {cpu['base_mhz']:,} MHz")
    add(f"  Total RAM          : {ram.get('total_gb', '?')} GB  ({ram.get('total_mb', '?'):,} MB installed)")
    if ram.get("available_mb"):
        used_mb = int(ram.get("total_mb", 0)) - int(ram.get("available_mb", 0))
        add(f"  RAM In Use         : {used_mb:,} MB  ({ram['available_mb']:,} MB free)")
    add(f"  GPU Model          : {gpu.get('model', 'Unknown')}")
    if gpu.get("vram") and gpu["vram"] not in ("0 MB", "Unknown", ""):
        add(f"  GPU VRAM           : {gpu['vram']}")
    if gpu.get("driver_version") and gpu["driver_version"] != "Unknown":
        add(f"  GPU Driver         : {gpu['driver_version']}")
    if gpu.get("all_gpus") and gpu["all_gpus"] not in ("Unknown", gpu.get("model", "")):
        add(f"  All Display Adapters: {gpu['all_gpus']}")
    if system.get("host_name") and system["host_name"] != "Unknown":
        add(f"  Host Name          : {system['host_name']}")
    if system.get("time_zone") and system["time_zone"] != "Unknown":
        add(f"  Time Zone          : {system['time_zone']}")
    if system.get("boot_time") and system["boot_time"] != "Unknown":
        add(f"  Last Boot          : {system['boot_time']}")
    if system.get("bios_version") and system["bios_version"] != "Unknown":
        add(f"  BIOS               : {system['bios_version']}")
    if extras.get("hotfixes") is not None:
        add(f"  Hotfixes Installed : {extras['hotfixes']}")
    if extras.get("nics") is not None:
        add(f"  Network Adapters   : {extras['nics']}")

    # Battery quick-line in snapshot
    bat = extras.get("battery", {})
    if bat.get("present"):
        bat_line = f"  Battery            : {bat.get('charge_pct', '?')}% charge | {bat.get('status', '?')}"
        if bat.get("health_pct", 0) > 0:
            bat_line += f" | Health ~{bat['health_pct']}%"
        if bat.get("cycle_count", -1) >= 0:
            bat_line += f" | {bat['cycle_count']} cycles"
        add(bat_line)
    else:
        add("  Battery            : None (desktop or AC-only)")

    results      = []
    cpu_pct      = 0.0
    gpu_pct      = 0.0
    gpu_match_ok = False

    # ── CPU Analysis ──────────────────────────────────────────
    h1("CPU ANALYSIS")
    cpu_model = cpu.get("model", "")
    cpu_lib   = library.get("cpu_library", [])
    match, conf = find_best_library_match(cpu_model, cpu_lib)

    if match:
        add(f"  Library Match    : {match['model']}")
        add(f"  Match Confidence : {conf*100:.0f}%")
        add(f"  Benchmark Score  : {match['score']:,}")
        add(f"  Tier             : {match['tier']} — {TIER_LABELS.get(match['tier'], '')}")
        add(f"  Notes            : {match.get('notes', '')}")
        add("")

        res = analyze_component(cpu_model, match["score"], cpu_lib, "CPU")
        results.append({**res, "resolved_tier": match["tier"]})
        cpu_pct = res["pct_below"]

        add(f"  HIERARCHY POSITION")
        add(f"  {'Below your CPU':<22}: {res['below_count']:>3} / {res['total_in_library']}  ({res['pct_below']:5.1f}%)")
        add(f"  {'At your level':<22}: {res['equal_count']:>3} / {res['total_in_library']}  ({res['pct_equal']:5.1f}%)")
        add(f"  {'Above your CPU':<22}: {res['above_count']:>3} / {res['total_in_library']}  ({res['pct_above']:5.1f}%)")
        add("")
        add(f"  Performance Percentile:  {res['pct_below']:.1f}th percentile")
        add(f"  [{progress_bar(res['pct_below'])}] {res['pct_below']:.1f}%")

        h2("CPU Tier Distribution (library)")
        add(tier_distribution(cpu_lib, match["tier"]))

        if res["below_entries"]:
            h2("Top 5 CPUs Outperformed by Your System")
            for e in res["below_entries"][:5]:
                add(f"  {TIER_ICONS.get(e['tier'],'?')} [{e['tier']:2s}] {e['model']:<46}  score {e['score']:>7,}")

        if res["above_entries"]:
            h2("Next 5 CPUs Ahead of Your System  (Upgrade Targets)")
            for e in res["above_entries"][:5]:
                gap = e["score"] - match["score"]
                add(f"  {TIER_ICONS.get(e['tier'],'?')} [{e['tier']:2s}] {e['model']:<46}  score {e['score']:>7,}  (+{gap:,})")
    else:
        add(f"  Could not match '{cpu_model}' to any library entry.")
        add("  Tip: Check hardware_library.json and add your CPU manually.")

    # ── GPU Analysis ──────────────────────────────────────────
    h1("GPU ANALYSIS")
    gpu_model    = gpu.get("model", "")
    gpu_lib      = library.get("gpu_library", [])
    match_g, cg  = find_best_library_match(gpu_model, gpu_lib)

    if match_g:
        gpu_match_ok = True
        add(f"  Library Match    : {match_g['model']}")
        add(f"  Match Confidence : {cg*100:.0f}%")
        add(f"  Benchmark Score  : {match_g['score']:,}")
        add(f"  VRAM (library)   : {match_g.get('vram_gb', '?')} GB")
        add(f"  Tier             : {match_g['tier']} — {TIER_LABELS.get(match_g['tier'], '')}")
        add(f"  Notes            : {match_g.get('notes', '')}")
        add("")

        res_g = analyze_component(gpu_model, match_g["score"], gpu_lib, "GPU")
        results.append({**res_g, "resolved_tier": match_g["tier"]})
        gpu_pct = res_g["pct_below"]

        add(f"  HIERARCHY POSITION")
        add(f"  {'Below your GPU':<22}: {res_g['below_count']:>3} / {res_g['total_in_library']}  ({res_g['pct_below']:5.1f}%)")
        add(f"  {'At your level':<22}: {res_g['equal_count']:>3} / {res_g['total_in_library']}  ({res_g['pct_equal']:5.1f}%)")
        add(f"  {'Above your GPU':<22}: {res_g['above_count']:>3} / {res_g['total_in_library']}  ({res_g['pct_above']:5.1f}%)")
        add("")
        add(f"  Performance Percentile:  {res_g['pct_below']:.1f}th percentile")
        add(f"  [{progress_bar(res_g['pct_below'])}] {res_g['pct_below']:.1f}%")

        h2("GPU Tier Distribution (library)")
        add(tier_distribution(gpu_lib, match_g["tier"]))

        if res_g["below_entries"]:
            h2("Top 5 GPUs Outperformed by Your System")
            for e in res_g["below_entries"][:5]:
                add(f"  {TIER_ICONS.get(e['tier'],'?')} [{e['tier']:2s}] {e['model']:<48}  score {e['score']:>7,}")

        if res_g["above_entries"]:
            h2("Next 5 GPUs Ahead of Your System  (Upgrade Targets)")
            for e in res_g["above_entries"][:5]:
                gap = e["score"] - match_g["score"]
                add(f"  {TIER_ICONS.get(e['tier'],'?')} [{e['tier']:2s}] {e['model']:<48}  score {e['score']:>7,}  (+{gap:,})")
    else:
        add(f"  Could not match '{gpu_model}' to any library entry.")
        add("")
        add("  Note: Integrated GPUs (e.g. 'AMD Radeon Graphics', 'Intel UHD Graphics')")
        add("  are now in the library. If yours still doesn't match, add it manually.")
        add("  Tip: Check hardware_library.json — add your GPU under gpu_library.")

    # ── RAM Context ───────────────────────────────────────────
    h1("RAM CONTEXT")
    total_gb = ram.get("total_gb", 0)
    brackets = [
        (4,   "F",  "Severely limited — many modern apps will struggle"),
        (8,   "D",  "Minimum viable — adequate for light tasks"),
        (16,  "C",  "Mainstream sweet-spot — comfortable for most workloads"),
        (32,  "B",  "Enthusiast — handles heavy multitasking and dev work"),
        (64,  "A",  "High-end — workstation / content-creation territory"),
        (128, "S",  "Professional — server and heavy simulation workloads"),
        (999, "S+", "Extreme — enterprise / scientific computing"),
    ]
    ram_tier, ram_desc = "?", "Unknown"
    for limit, tier, desc in brackets:
        if total_gb <= limit:
            ram_tier, ram_desc = tier, desc
            break

    add(f"  Installed RAM    : {total_gb} GB")
    add(f"  RAM Tier         : {ram_tier} — {TIER_LABELS.get(ram_tier, '')}")
    add(f"  Assessment       : {ram_desc}")

    # ── Battery Analysis ──────────────────────────────────────
    h1("BATTERY")
    bat = extras.get("battery", {})
    if bat.get("present"):
        charge = bat.get("charge_pct", "?")
        status = bat.get("status", "Unknown")
        chemistry = bat.get("chemistry", "Unknown")
        health = bat.get("health_pct", 0)
        cycles = bat.get("cycle_count", -1)
        design = bat.get("design_capacity_mwh", 0)
        full   = bat.get("full_capacity_mwh", 0)

        add(f"  Charge Level     : {charge}%")
        add(f"  [{progress_bar(charge if isinstance(charge, (int,float)) else 0)}] {charge}%")
        add(f"  Status           : {status}")
        if chemistry and chemistry not in ("Unknown", ""):
            add(f"  Chemistry        : {chemistry}")

        if health > 0:
            add(f"  Battery Health   : ~{health}%")
            add(f"  [{progress_bar(health)}] {health}%")
            if health >= 85:
                add("  Health Grade     : ✅ Excellent — battery in great condition")
            elif health >= 65:
                add("  Health Grade     : ⚠  Fair — noticeable wear; plan for replacement within 1-2 years")
            elif health >= 40:
                add("  Health Grade     : ⚠  Poor — significant degradation; replacement recommended")
            else:
                add("  Health Grade     : 🔴 Critical — battery likely needs immediate replacement")

        if design > 0 and full > 0:
            add(f"  Design Capacity  : {design:,} mWh  ({design/1000:.1f} Wh)")
            add(f"  Current Max Cap  : {full:,} mWh  ({full/1000:.1f} Wh)")

        if cycles >= 0:
            add(f"  Charge Cycles    : {cycles}")
            if cycles < 300:
                add("  Cycle Assessment : ✅ Low cycle count — battery is relatively fresh")
            elif cycles < 600:
                add("  Cycle Assessment : ⚠  Moderate wear — normal for a 1-3 year old laptop")
            elif cycles < 1000:
                add("  Cycle Assessment : ⚠  High wear — consider replacement soon")
            else:
                add("  Cycle Assessment : 🔴 Very high cycle count — replacement strongly recommended")
        else:
            add("  Charge Cycles    : Not reported by this device")
    else:
        add("  No battery detected — this appears to be a desktop or AC-only system.")

    # ── Upgrade Advice ────────────────────────────────────────
    h1("UPGRADE ADVICE")
    add(upgrade_advice(cpu_pct, match_g if gpu_match_ok else None, gpu_pct, int(total_gb)))

    # ── Overall Summary ───────────────────────────────────────
    h1("OVERALL SUMMARY")
    if results:
        avg_pct = sum(r["pct_below"] for r in results) / len(results)
        tiers   = [r["resolved_tier"] for r in results]
        def tier_idx(t): return TIER_ORDER.index(t) if t in TIER_ORDER else -1
        overall_tier = min(tiers, key=tier_idx)

        add(f"  Combined Performance Percentile : {avg_pct:.1f}th")
        add(f"  [{progress_bar(avg_pct)}] {avg_pct:.1f}%")
        add("")
        add(f"  Overall System Tier  : {overall_tier} — {TIER_LABELS.get(overall_tier, '')}")
        add("")

        if avg_pct >= 90:
            verdict = "🏆 Elite Tier — Your system outperforms the vast majority of the library."
        elif avg_pct >= 70:
            verdict = "🥇 High Performer — Well above average, suitable for demanding workloads."
        elif avg_pct >= 50:
            verdict = "🥈 Above Average — Solid mid-to-high system with meaningful headroom."
        elif avg_pct >= 30:
            verdict = "🥉 Mainstream — Competent for everyday tasks; upgrades worth considering."
        elif avg_pct >= 10:
            verdict = "⚠  Budget Segment — Limited headroom; targeted upgrade recommended."
        else:
            verdict = "🔴 Entry / Legacy — Significant upgrade recommended for modern workloads."

        add(f"  {verdict}")
        add("")
        add("  Component breakdown:")
        for r in results:
            icon = TIER_ICONS.get(r["resolved_tier"], "?")
            add(f"    {icon} {r['component_type']:5s}  Tier {r['resolved_tier']:2s}  |  "
                f"Outperforms {r['pct_below']:5.1f}% of library  "
                f"({r['below_count']}/{r['total_in_library']} entries below)")
        add(f"       RAM   Tier {ram_tier:2s}  |  {total_gb} GB — {ram_desc}")
    else:
        add("  Insufficient matches to compute a combined percentile.")
        add("  Extend hardware_library.json with your hardware for full analysis.")

    h1("END OF REPORT")
    add(f"  Report saved to: {REPORT_FILE}")
    add(sep)

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────────────────────
def main():
    print("[Analyzer] Hardware Tier Analysis Tool — Python Analyzer v2")
    print("[Analyzer] Loading library and local specs...\n")

    if not Path(LIBRARY_FILE).exists():
        print(f"[ERROR] Library file not found: {LIBRARY_FILE}", file=sys.stderr)
        sys.exit(1)
    with open(LIBRARY_FILE, "r", encoding="utf-8") as f:
        library = json.load(f)

    cpu_count = len(library.get("cpu_library", []))
    gpu_count = len(library.get("gpu_library", []))
    print(f"[Analyzer] Library loaded — {cpu_count} CPU entries, {gpu_count} GPU entries.")

    if not Path(SPECS_FILE).exists():
        print(f"[ERROR] Spec file not found: {SPECS_FILE}", file=sys.stderr)
        print("[ERROR] Please run scanner.exe first to generate local_specs.json", file=sys.stderr)
        sys.exit(1)
    with open(SPECS_FILE, "r", encoding="utf-8") as f:
        raw_specs = json.load(f)

    specs = normalize_specs(raw_specs)
    print(f"[Analyzer] Local specs loaded from {SPECS_FILE}.")
    print(f"           OS:  {specs['os_str']}")
    print(f"           CPU: {specs['cpu'].get('model', 'Unknown')}")
    print(f"           GPU: {specs['gpu'].get('model', 'Unknown')}")
    print(f"           RAM: {specs['ram'].get('total_gb', '?')} GB\n")

    report = build_report(specs, library)

    print(report)

    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"\n[Analyzer] Report written to {REPORT_FILE}")


if __name__ == "__main__":
    main()
