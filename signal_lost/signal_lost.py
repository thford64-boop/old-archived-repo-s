#!/usr/bin/env python3
"""
OPERATION: SIGNAL LOST
A terminal-based puzzle mystery game.
Solve 5 clues using your Link Launcher tools.
"""

import os
import sys
import time
import subprocess
import platform
import base64

# ── Colours (ANSI) ──────────────────────────────────────────────────────────
class C:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    GREEN   = "\033[92m"
    RED     = "\033[91m"
    YELLOW  = "\033[93m"
    CYAN    = "\033[96m"
    BLUE    = "\033[94m"
    MAGENTA = "\033[95m"
    WHITE   = "\033[97m"
    GRAY    = "\033[90m"

def c(color, text): return f"{color}{text}{C.RESET}"
def bold(text):     return c(C.BOLD, text)

# ── Helpers ──────────────────────────────────────────────────────────────────
def clear():
    os.system("cls" if platform.system() == "Windows" else "clear")

def slow(text, delay=0.025, newline=True):
    for ch in text:
        sys.stdout.write(ch)
        sys.stdout.flush()
        time.sleep(delay)
    if newline:
        print()

def pause(prompt="  Press ENTER to continue..."):
    input(c(C.GRAY, prompt))

def divider(char="─", width=60, color=C.GRAY):
    print(c(color, char * width))

def header(title, color=C.CYAN):
    clear()
    divider("═", 60, color)
    print(c(color + C.BOLD, f"  {title}"))
    divider("═", 60, color)
    print()

def prompt(text, color=C.CYAN):
    return input(c(color, f"  {text} → ")).strip()

def success(msg):
    print()
    print(c(C.GREEN + C.BOLD, f"  ✓  {msg}"))
    print()

def fail(msg):
    print()
    print(c(C.RED, f"  ✗  {msg}"))
    print()

def info(msg, indent=2):
    print(c(C.GRAY, " " * indent + msg))

def highlight(msg, indent=2):
    print(c(C.YELLOW, " " * indent + msg))

# ── Puzzle File Paths ────────────────────────────────────────────────────────
SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
PUZZLE_DIR   = os.path.join(SCRIPT_DIR, "puzzle_files")

FILES = {
    1: os.path.join(PUZZLE_DIR, "bench.jpg"),
    2: os.path.join(PUZZLE_DIR, "static_feed.wav"),
    3: os.path.join(PUZZLE_DIR, "signal.wav"),
    4: os.path.join(PUZZLE_DIR, "cipher_note.txt"),
    5: os.path.join(PUZZLE_DIR, "ringtone_wren.wav"),
}

# ── Puzzle Answers ───────────────────────────────────────────────────────────
ANSWERS = {
    1: "COBALT",
    2: "NINE",
    3: "GHOST",
    4: "SPHERE",
    5: "WREN",
}

# ── Tool URLs (matching Link Launcher) ───────────────────────────────────────
TOOLS = {
    "metadata": "https://www.metadata2go.com/",
    "spectrogram": "https://www.boxentriq.com/steganography/audio-spectrogram",
    "cachesleuth": "https://www.cachesleuth.com/multidecoder/",
    "spectrodraw": "https://spectrodraw.com/app/",
    "video2mp3": "https://www.freeconvert.com/convert/video-to-mp3",
    "morse": "https://morsecode.world/international/translator.html",
}

LINKS_MENU = [
    ("Metadata2Go",          TOOLS["metadata"],    "Read hidden EXIF metadata"),
    ("Audio Spectrogram",    TOOLS["spectrogram"], "See words drawn in frequencies"),
    ("Morse Translator",     TOOLS["morse"],       "Decode dots and dashes"),
    ("CacheSleuth Decoder",  TOOLS["cachesleuth"], "Decode Base64 and other ciphers"),
    ("Spectrodraw",          TOOLS["spectrodraw"], "Visualise audio spectrograms"),
    ("Video to MP3",         TOOLS["video2mp3"],   "Convert video to audio"),
]

# ── Hint system ──────────────────────────────────────────────────────────────
HINTS = {
    1: [
        "Upload bench.jpg to Metadata2Go and scan ALL fields.",
        "Look at the 'Artist' field — it contains a single word that is not a person's name.",
        "The answer is a colour. It's used as a codename.",
    ],
    2: [
        "Load static_feed.wav into a media player or the spectrogram tool.",
        "Listen for rhythmic beeping underneath the static — it's Morse code.",
        "Morse: N = -.   I = ..   N = -.   E = .   |   The word is a number.",
    ],
    3: [
        "Upload signal.wav to the Audio Spectrogram tool on boxentriq.com.",
        "Look at the frequency band between 8,000 Hz and 17,000 Hz.",
        "A five-letter word is spelled out visually in the bright bands.",
    ],
    4: [
        "Open cipher_note.txt — it contains a long string of characters.",
        "Paste the encoded string into CacheSleuth and try Base64 first.",
        "The decoded message contains a word in ALL CAPS. That is your fragment.",
    ],
    5: [
        "Upload ringtone_wren.wav to the Audio Spectrogram tool.",
        "Look at the 6,000 Hz – 15,000 Hz range between 0.8s and 7.2s.",
        "Four letters appear — Agent Wren's own codename.",
    ],
}

# ── State ────────────────────────────────────────────────────────────────────
state = {
    "solved":    set(),
    "hints_used": {i: 0 for i in range(1, 6)},
    "score":     1000,
    "started":   False,
}

# ── Utility ──────────────────────────────────────────────────────────────────
def open_file(path):
    """Open a file with the OS default app."""
    if platform.system() == "Darwin":
        subprocess.run(["open", path])
    elif platform.system() == "Windows":
        os.startfile(path)
    else:
        subprocess.run(["xdg-open", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def open_folder(path):
    """Open puzzle_files folder."""
    open_file(path)

def check_answer(puzzle_num, user_input):
    return user_input.strip().upper() == ANSWERS[puzzle_num]

def fragments_collected():
    return [ANSWERS[i] for i in sorted(state["solved"])]

def all_solved():
    return len(state["solved"]) == 5

# ── Screens ──────────────────────────────────────────────────────────────────
def intro_screen():
    clear()
    print()
    slow(c(C.CYAN + C.BOLD,
        "  ╔══════════════════════════════════════════════════════╗"), 0.005)
    slow(c(C.CYAN + C.BOLD,
        "  ║          O P E R A T I O N :  S I G N A L           ║"), 0.005)
    slow(c(C.CYAN + C.BOLD,
        "  ║                    L O S T                          ║"), 0.005)
    slow(c(C.CYAN + C.BOLD,
        "  ╚══════════════════════════════════════════════════════╝"), 0.005)
    print()
    time.sleep(0.3)
    slow(c(C.GRAY, "  Initialising secure channel..."), 0.04)
    time.sleep(0.5)
    slow(c(C.GRAY, "  Decrypting dossier..."), 0.04)
    time.sleep(0.4)
    slow(c(C.GRAY, "  ACCESS GRANTED."), 0.04)
    print()
    time.sleep(0.5)
    divider()
    print()
    slow(c(C.WHITE,
        "  Three days ago, field agent WREN went dark."), 0.03)
    time.sleep(0.2)
    slow(c(C.WHITE,
        "  Before losing contact, WREN left behind 5 files"), 0.03)
    slow(c(C.WHITE,
        "  — each hiding one fragment of a secret passphrase."), 0.03)
    print()
    time.sleep(0.2)
    slow(c(C.YELLOW,
        "  Your mission: recover all 5 fragments."), 0.03)
    slow(c(C.YELLOW,
        "  Assemble the passphrase. Find out what WREN knew."), 0.03)
    print()
    divider()
    print()
    slow(c(C.GRAY,
        "  You will need your Link Launcher to open the right tools."), 0.03)
    slow(c(C.GRAY,
        "  Each puzzle file is in the puzzle_files/ folder."), 0.03)
    print()
    pause("  Press ENTER to begin the operation...")
    state["started"] = True

def main_menu():
    while True:
        header("OPERATION: SIGNAL LOST  //  MAIN MENU", C.CYAN)

        # Status bar
        solved_count = len(state["solved"])
        bar = ""
        for i in range(1, 6):
            bar += c(C.GREEN, " ■") if i in state["solved"] else c(C.GRAY, " □")
        print(f"  Fragments recovered:{bar}   {c(C.YELLOW, str(solved_count))}{c(C.GRAY, '/5')}")
        print(f"  Score: {c(C.YELLOW + C.BOLD, str(state['score']))}")
        print()
        divider()
        print()

        # Case file list
        for i in range(1, 6):
            status = c(C.GREEN, "SOLVED ✓") if i in state["solved"] else c(C.GRAY, "OPEN   ·")
            labels = {
                1: "bench.jpg        │ Metadata2Go",
                2: "static_feed.wav  │ Media player / Spectrogram",
                3: "signal.wav       │ Audio Spectrogram",
                4: "cipher_note.txt  │ CacheSleuth Decoder",
                5: "ringtone_wren.wav│ Spectrodraw / Spectrogram",
            }
            print(f"  [{i}] {status}  CASE {i:02d}: {c(C.WHITE, labels[i])}")
        print()
        divider()
        print()
        print(f"  {c(C.CYAN, '[F]')} Open puzzle_files folder")
        print(f"  {c(C.CYAN, '[L]')} Links  {c(C.GRAY, '(open tools in browser)')}")
        print(f"  {c(C.CYAN, '[H]')} Hint for a case  {c(C.GRAY, '(costs 50 pts each)')}")
        if all_solved():
            print(f"  {c(C.GREEN + C.BOLD, '[P]')} ★  ENTER FINAL PASSPHRASE  ★")
        print(f"  {c(C.RED, '[Q]')} Quit")
        print()

        choice = prompt("Choose", C.CYAN).upper()

        if choice in ("1", "2", "3", "4", "5"):
            run_puzzle(int(choice))
        elif choice == "F":
            open_folder(PUZZLE_DIR)
            info("Opened puzzle_files folder.")
            pause()
        elif choice == "L":
            links_menu()
        elif choice == "H":
            hint_menu()
        elif choice == "P" and all_solved():
            final_screen()
            return
        elif choice == "Q":
            quit_screen()
            return
        else:
            fail("Unknown command.")
            time.sleep(0.8)

def run_puzzle(num):
    header(f"CASE FILE {num:02d}", C.MAGENTA)

    puzzle_info = {
        1: {
            "title":   "THE PHOTO THAT WASN'T",
            "file":    "bench.jpg",
            "tool":    "Metadata2Go",
            "url":     TOOLS["metadata"],
            "story": [
                "WREN left a photograph of a park bench.",
                "Analysts dismissed it as personal. They were wrong.",
                "Something is buried in the file's metadata — a word",
                "that has no business being there.",
            ],
            "instructions": [
                "1. Open bench.jpg from the puzzle_files/ folder",
                "2. Upload it to a metadata viewer and scan ALL fields",
                "3. Look for a word that doesn't belong",
                "   (not a camera setting or timestamp)",
                "4. The odd word IS the fragment.",
            ],
        },
        2: {
            "title":   "THE DEAD CHANNEL",
            "file":    "static_feed.wav",
            "tool":    "Audio Player or Spectrogram",
            "url":     TOOLS["spectrogram"],
            "story": [
                "WREN's last transmission was labelled 'static noise'.",
                "But analysts missed something in the audio.",
                "Beneath the hiss, a rhythm pulses — deliberate, coded.",
                "Someone is speaking in the language of dots and dashes.",
            ],
            "instructions": [
                "1. Open static_feed.wav in your media player or analysis tool",
                "2. Listen carefully — you'll hear rhythmic beeping",
                "   beneath the white noise",
                "3. The beeps are Morse code. Decode them.",
                "   Tip: short beep = dot (·)  long beep = dash (−)",
                "4. OR: analyse the audio visually",
                "   (look at the 800 Hz frequency band around 2s and 7s)",
            ],
        },
        3: {
            "title":   "THE INVISIBLE WORD",
            "file":    "signal.wav",
            "tool":    "Audio Spectrogram (Boxentriq)",
            "url":     TOOLS["spectrogram"],
            "story": [
                "This audio file appears to contain only ambient tone.",
                "But WREN painted something into the frequencies.",
                "A word exists in this file that can only be seen,",
                "not heard — hidden above the range of normal listening.",
            ],
            "instructions": [
                "1. Open signal.wav and analyse it visually",
                "2. Look at the frequency range 8,000 – 17,000 Hz",
                "3. Between 0.5s and 5.5s, a 5-letter word is drawn",
                "   as bright lines in the upper frequency bands",
                "4. Read the word. That's your fragment.",
            ],
        },
        4: {
            "title":   "THE SCRAMBLED NOTE",
            "file":    "cipher_note.txt",
            "tool":    "CacheSleuth Multi-Decoder",
            "url":     TOOLS["cachesleuth"],
            "story": [
                "A text file recovered from WREN's dead drop.",
                "It contains an intercepted transmission — garbled,",
                "encoded in a scheme the analysts couldn't identify.",
                "But the encoding is simple. You just need the right tool.",
            ],
            "instructions": [
                "1. Open cipher_note.txt — read the encoded string",
                "2. Copy the long text string between the dashes",
                "3. Paste it into a decoder and try common encoding schemes",
                "4. Read the decoded message carefully",
                "5. A word in ALL CAPS appears in the plaintext.",
                "   That word is the fragment.",
            ],
        },
        5: {
            "title":   "THE FINAL SIGNAL",
            "file":    "ringtone_wren.wav",
            "tool":    "Audio Spectrogram or Spectrodraw",
            "url":     TOOLS["spectrogram"],
            "story": [
                "WREN's last known act was sending a ringtone.",
                "It sounds innocent — a few gentle musical notes.",
                "But WREN encoded one final message in the frequencies:",
                "a name. Their own.",
            ],
            "instructions": [
                "1. Open ringtone_wren.wav and analyse it visually",
                "2. Look at the 6,000 – 15,000 Hz frequency range",
                "3. Between 0.8s and 7.2s, 4 letters are drawn in the",
                "   upper frequency bands",
                "4. The 4-letter word is the final fragment.",
            ],
        },
    }

    p = puzzle_info[num]
    already_solved = num in state["solved"]

    # Title
    print(c(C.MAGENTA + C.BOLD, f"  ▸ {p['title']}"))
    print(c(C.GRAY, f"  File: {p['file']}"))
    if already_solved:
        print(c(C.GREEN, f"  Status: SOLVED — Fragment: {ANSWERS[num]}"))
    print()
    divider()
    print()

    # Story
    for line in p["story"]:
        slow(c(C.WHITE, f"  {line}"), 0.015)
    print()

    # Instructions
    print(c(C.CYAN + C.BOLD, "  HOW TO SOLVE:"))
    print()
    for line in p["instructions"]:
        info(line, 4)
    print()
    divider()
    print()

    # Options
    print(f"  {c(C.CYAN, '[A]')} Answer this puzzle")
    hints_used_count = state["hints_used"][num]
    print(f"  {c(C.CYAN, '[H]')} Get a hint  {c(C.GRAY, f'(used: {hints_used_count}/3)')}")
    print(f"  {c(C.CYAN, '[B]')} Back to menu")
    print()

    while True:
        choice = prompt("Choose", C.CYAN).upper()

        if choice == "A":
            print()
            ans = prompt(f"  Enter Fragment #{num}", C.YELLOW).strip().upper()
            if check_answer(num, ans):
                state["solved"].add(num)
                penalty = state["hints_used"][num] * 50
                pts = max(0, 200 - penalty)
                state["score"] += pts
                success(f"CORRECT!  Fragment #{num} confirmed: {c(C.GREEN + C.BOLD, ANSWERS[num])}")
                info(f"+ {pts} points  (hints used: {state['hints_used'][num]})")
                print()
                if all_solved():
                    slow(c(C.YELLOW + C.BOLD,
                        "  ★  All fragments recovered! Return to menu to enter the final passphrase."), 0.02)
                    print()
                pause()
                return
            else:
                state["score"] = max(0, state["score"] - 10)
                fail("Incorrect. Check the file again with your tool.")
                info("(-10 points)")
                print()

        elif choice == "H":
            show_hint(num)
            print()

        elif choice == "B":
            return

def show_hint(num):
    used = state["hints_used"][num]
    hints = HINTS[num]
    if used >= len(hints):
        info("No more hints available for this puzzle.")
        return
    state["score"] = max(0, state["score"] - 50)
    print()
    print(c(C.YELLOW + C.BOLD, f"  HINT {used + 1}/3:"))
    print(c(C.YELLOW, f"  {hints[used]}"))
    state["hints_used"][num] = used + 1
    info(f"  (-50 points)")

def links_menu():
    import webbrowser
    while True:
        header("LINKS  //  OPEN TOOLS", C.CYAN)
        print(c(C.GRAY, "  Open any tool in your browser."))
        print()
        for i, (name, url, desc) in enumerate(LINKS_MENU, 1):
            print(f"  {c(C.CYAN, f'[{i}]')} {c(C.WHITE, name)}")
            info(desc, 6)
        print()
        print(f"  {c(C.CYAN, '[B]')} Back to menu")
        print()
        choice = prompt("Choose", C.CYAN).upper()
        if choice == "B":
            return
        elif choice.isdigit() and 1 <= int(choice) <= len(LINKS_MENU):
            name, url, desc = LINKS_MENU[int(choice) - 1]
            webbrowser.open(url)
            info(f"Opened {name} in your browser.")
            pause()
        else:
            fail("Unknown command.")
            time.sleep(0.6)

def hint_menu():
    header("HINT SYSTEM", C.YELLOW)
    print(c(C.GRAY, "  Each hint costs 50 points. Max 3 hints per puzzle."))
    print()
    for i in range(1, 6):
        status = "SOLVED" if i in state["solved"] else f"hints used: {state['hints_used'][i]}/3"
        print(f"  [{i}] Case {i:02d}  {c(C.GRAY, status)}")
    print(f"  [B] Back")
    print()
    choice = prompt("Which puzzle?", C.YELLOW).upper()
    if choice in ("1", "2", "3", "4", "5"):
        num = int(choice)
        if num in state["solved"]:
            info("Already solved — no hints needed!")
        else:
            show_hint(num)
    pause()

def final_screen():
    header("FINAL PASSPHRASE", C.GREEN)

    frags = [ANSWERS[i] for i in range(1, 6)]
    passphrase = " ".join(frags)

    slow(c(C.WHITE,
        "  You have recovered all five fragments from WREN's files."), 0.03)
    slow(c(C.WHITE,
        "  Now assemble them in order into the final passphrase."), 0.03)
    print()
    print(c(C.GRAY, "  Fragment order: #1 · #2 · #3 · #4 · #5"))
    print()
    divider()
    print()

    for _ in range(3):
        ans = prompt("Enter the full passphrase (5 words, space-separated)", C.CYAN).strip().upper()
        if ans == passphrase.upper():
            break
        fail("Not quite. Check your fragments and try again.")
        info(f"You have {2 - _ } attempt(s) remaining before a hint appears.")
        if _ == 1:
            print()
            print(c(C.YELLOW, "  HINT: The passphrase is exactly:"))
            for i, w in enumerate(frags, 1):
                print(c(C.YELLOW, f"    Fragment #{i} = {w}"))
            print()
    else:
        print()
        print(c(C.YELLOW + C.BOLD, "  The passphrase is: ") + c(C.GREEN + C.BOLD, passphrase))
        print()

    clear()
    time.sleep(0.5)
    divider("═", 60, C.GREEN)
    print()
    slow(c(C.GREEN + C.BOLD, "  OPERATION: SIGNAL LOST — MISSION COMPLETE"), 0.02)
    print()
    divider("═", 60, C.GREEN)
    print()
    time.sleep(0.3)
    slow(c(C.WHITE, "  Passphrase accepted. Archive unlocked."), 0.03)
    print()
    time.sleep(0.5)
    slow(c(C.CYAN, f"  ┌─────────────────────────────────────────┐"), 0.005)
    slow(c(C.CYAN, f"  │  PASSPHRASE: ") + c(C.GREEN + C.BOLD, f"{passphrase:<27}") + c(C.CYAN, "│"), 0.005)
    slow(c(C.CYAN, f"  └─────────────────────────────────────────┘"), 0.005)
    print()
    time.sleep(0.5)
    slow(c(C.GRAY, "  Agent WREN's final message reads:"), 0.03)
    print()
    slow(c(C.WHITE, '  "If you found this, the operation succeeded.'), 0.025)
    slow(c(C.WHITE, '   COBALT NINE was real. The GHOST protocol exists.'), 0.025)
    slow(c(C.WHITE, '   The SPHERE must never reach them.'), 0.025)
    slow(c(C.WHITE, '   — WREN"'), 0.025)
    print()
    time.sleep(0.5)
    divider("─", 60, C.GRAY)
    print()
    hints_penalty = sum(state["hints_used"][i] for i in range(1, 6)) * 50
    print(f"  Final Score:  {c(C.YELLOW + C.BOLD, str(state['score']))}")
    print(f"  Puzzles solved: {c(C.GREEN, '5/5')}")
    print(f"  Hints used: {c(C.GRAY, str(sum(state['hints_used'].values())))}")
    print()
    if state["score"] >= 900:
        print(c(C.GREEN + C.BOLD, "  ★★★  MASTER OPERATIVE  ★★★"))
    elif state["score"] >= 700:
        print(c(C.CYAN + C.BOLD, "  ★★   FIELD AGENT"))
    elif state["score"] >= 400:
        print(c(C.YELLOW, "  ★    JUNIOR ANALYST"))
    else:
        print(c(C.GRAY, "       ROOKIE (but you finished — that's what matters)"))
    print()
    pause("  Press ENTER to exit...")

def quit_screen():
    clear()
    print()
    slow(c(C.GRAY, "  Closing secure channel..."), 0.04)
    time.sleep(0.5)
    print()
    solved = len(state["solved"])
    if solved == 0:
        slow(c(C.RED, "  WREN's files remain undiscovered."), 0.03)
    elif solved < 5:
        slow(c(C.YELLOW, f"  {solved}/5 fragments recovered. The mission is unfinished."), 0.03)
    else:
        slow(c(C.GREEN, "  Operation complete. Good work, analyst."), 0.03)
    print()
    slow(c(C.GRAY, "  // END SESSION"), 0.03)
    print()

# ── Entry Point ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Validate puzzle files exist
    missing = [FILES[i] for i in range(1, 6) if not os.path.exists(FILES[i])]
    if missing:
        clear()
        print()
        print(c(C.RED + C.BOLD, "  ERROR: Puzzle files not found!"))
        print()
        print(c(C.GRAY, "  Missing files:"))
        for f in missing:
            print(c(C.RED, f"    • {f}"))
        print()
        print(c(C.YELLOW, "  Run this first to generate the puzzle files:"))
        print(c(C.WHITE, "    python3 make_files.py"))
        print()
        sys.exit(1)

    try:
        intro_screen()
        main_menu()
    except KeyboardInterrupt:
        print()
        quit_screen()
