import tkinter as tk
import webbrowser

# --- Link definitions ---
LINKS = [
    {
        "name": "TryHackMe",
        "url": "https://tryhackme.com",
        "desc": "Learn cybersecurity through hands-on challenges",
        "emoji": "🔐",
        "color": "#1db954",
    },
    {
        "name": "Metadata2Go",
        "url": "https://www.metadata2go.com/",
        "desc": "View & edit file metadata online",
        "emoji": "🔍",
        "color": "#00b4d8",
    },
    {
        "name": "Audio Spectrogram",
        "url": "https://www.boxentriq.com/steganography/audio-spectrogram",
        "desc": "Analyze & decode audio spectrograms",
        "emoji": "🔊",
        "color": "#e76f51",
    },
    {
        "name": "CacheSleuth Decoder",
        "url": "https://www.cachesleuth.com/multidecoder/",
        "desc": "Multi-format cipher & encoding decoder",
        "emoji": "🧩",
        "color": "#f4a261",
    },
    {
        "name": "Spectrodraw",
        "url": "https://spectrodraw.com/app/",
        "desc": "Draw audio spectrograms",
        "emoji": "🎨",
        "color": "#9b5de5",
    },
    {
        "name": "Morse Code Translator",
        "url": "https://morsecode.world/international/translator.html",
        "desc": "Translate text to Morse code and back",
        "emoji": "📡",
        "color": "#2ec4b6",
    },
    {
        "name": "Morse Audio Decoder",
        "url": "https://morsecode.world/international/decoder/audio-decoder-adaptive.html",
        "desc": "Decode Morse code from audio adaptively",
        "emoji": "🎧",
        "color": "#a8dadc",
    },
    {
        "name": "Video → MP3",
        "url": "https://www.freeconvert.com/convert/video-to-mp3",
        "desc": "Convert video files to MP3 audio",
        "emoji": "🎵",
        "color": "#f72585",
    },
    {
        "name": "Decompiler",
        "url": "https://www.decompiler.com/",
        "desc": "Online decompiler for executables & binaries",
        "emoji": "🛠️",
        "color": "#ffb703",
    },
    {
        "name": "DeepHat App",
        "url": "https://app.deephat.ai/",
        "desc": "Access the DeepHat application",
        "emoji": "🚀",
        "color": "#ff6b6b",
    },
]

BG = "#0d0d0d"
CARD_BG = "#161616"
CARD_HOVER = "#1f1f1f"
TEXT_PRIMARY = "#f0f0f0"
TEXT_SECONDARY = "#888888"
FONT_TITLE = ("Consolas", 22, "bold")
FONT_CARD_NAME = ("Consolas", 13, "bold")
FONT_CARD_DESC = ("Consolas", 9)
FONT_LABEL = ("Consolas", 10)

def open_link(url):
    webbrowser.open(url)

def on_enter(frame, btn, color):
    frame.configure(bg=CARD_HOVER, highlightbackground=color)
    for child in frame.winfo_children():
        try:
            child.configure(bg=CARD_HOVER)
        except Exception:
            pass

def on_leave(frame, btn, color):
    frame.configure(bg=CARD_BG, highlightbackground="#2a2a2a")
    for child in frame.winfo_children():
        try:
            child.configure(bg=CARD_BG)
        except Exception:
            pass

def main():
    root = tk.Tk()
    root.title("🚀 Link Launcher")
    root.configure(bg=BG)
    root.resizable(False, False)

    # --- Title ---
    header = tk.Frame(root, bg=BG)
    header.pack(pady=(28, 6), padx=30)

    tk.Label(
        header,
        text="LINK LAUNCHER",
        font=FONT_TITLE,
        fg=TEXT_PRIMARY,
        bg=BG,
    ).pack()

    tk.Label(
        header,
        text="pick a destination",
        font=FONT_LABEL,
        fg=TEXT_SECONDARY,
        bg=BG,
    ).pack(pady=(2, 0))

    # Divider
    tk.Frame(root, bg="#2a2a2a", height=1).pack(fill="x", padx=30, pady=(14, 18))

    # --- Cards (2-column horizontal grid) ---
    cards_frame = tk.Frame(root, bg=BG)
    cards_frame.pack(padx=30, pady=(0, 24))

    for i, link in enumerate(LINKS):
        row = i // 2
        col = i % 2

        card = tk.Frame(
            cards_frame,
            bg=CARD_BG,
            highlightbackground="#2a2a2a",
            highlightthickness=1,
            cursor="hand2",
        )
        card.grid(row=row, column=col, padx=5, pady=5, ipadx=8, ipady=8, sticky="ew")
        cards_frame.columnconfigure(col, weight=1)

        inner = tk.Frame(card, bg=CARD_BG)
        inner.pack(fill="x", padx=10, pady=3)

        # Left: emoji + name
        left = tk.Frame(inner, bg=CARD_BG)
        left.pack(side="left", fill="y")

        tk.Label(
            left,
            text=link["emoji"],
            font=("Consolas", 18),
            bg=CARD_BG,
            fg=link["color"],
        ).pack(side="left", padx=(0, 8))

        text_block = tk.Frame(left, bg=CARD_BG)
        text_block.pack(side="left")

        tk.Label(
            text_block,
            text=link["name"],
            font=FONT_CARD_NAME,
            fg=link["color"],
            bg=CARD_BG,
            anchor="w",
        ).pack(anchor="w")

        tk.Label(
            text_block,
            text=link["desc"],
            font=FONT_CARD_DESC,
            fg=TEXT_SECONDARY,
            bg=CARD_BG,
            anchor="w",
            wraplength=200,
            justify="left",
        ).pack(anchor="w")

        # Right: open button
        btn = tk.Button(
            inner,
            text="OPEN →",
            font=("Consolas", 9, "bold"),
            bg=link["color"],
            fg="#000000",
            relief="flat",
            cursor="hand2",
            padx=10,
            pady=4,
            command=lambda url=link["url"]: open_link(url),
        )
        btn.pack(side="right", padx=(10, 0))

        # Hover effects
        for widget in [card, inner]:
            widget.bind("<Enter>", lambda e, f=card, b=btn, c=link["color"]: on_enter(f, b, c))
            widget.bind("<Leave>", lambda e, f=card, b=btn, c=link["color"]: on_leave(f, b, c))
            widget.bind("<Button-1>", lambda e, url=link["url"]: open_link(url))

    root.mainloop()

if __name__ == "__main__":
    main()