"""
ModMaster — local AI assistant powered by Ollama.
Modern rounded UI with code block rendering + stop button.
"""

import os
import sys
import re
import json
import threading
import warnings
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

warnings.filterwarnings("ignore")

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

try:
    import ollama
except ImportError:
    print("ERROR: 'ollama' package not found. Run: pip install ollama", file=sys.stderr)
    sys.exit(1)

from model_manager import load_config, save_config, set_complexity, get_active_model, ensure_model
from search import web_search, search_needed

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR          = Path(__file__).parent
INSTRUCTIONS_PATH = BASE_DIR / "instructions.txt"
ICON_PATH         = BASE_DIR / "icon.ico"

DEFAULT_INSTRUCTIONS = """\
You are ModMaster, a private AI assistant that runs entirely on this device.

Rules:
- Your name is ModMaster. Never identify yourself as any other AI, model, or product.
- Never mention Anthropic, OpenAI, Meta, Google, Mistral, or any AI company or model name.
- Never say you were "trained by" anyone. You are simply ModMaster.
- Never make outbound calls to other AI APIs to generate responses.
- When you include code in your response, ALWAYS wrap it in triple backticks with the language name, like:
  ```python
  print("hello")
  ```
  Always specify the language after the opening triple backticks so the UI can render it correctly.
- If you need current information and no local search source is available, you may use the configured search fallback — tell the user when you do this.
- Be direct, confident, and concise. Prioritize the user's actual goal.
"""

MAX_HISTORY_TURNS = 12

# ── Colours ───────────────────────────────────────────────────────────────────
BG        = "#0d1117"
BG2       = "#161b22"
BG3       = "#1c2128"
BORDER    = "#30363d"
CYAN      = "#79c0ff"
GREEN     = "#56d364"
YELLOW    = "#e3b341"
RED       = "#f85149"
DIM       = "#8b949e"
FG        = "#e6edf3"
INPUT_BG  = "#1c2128"
CODE_BG   = "#161b22"
CODE_BORDER = "#30363d"
ACCENT    = "#58a6ff"

FONT_MONO = ("Consolas", 10) if sys.platform == "win32" else ("Menlo", 10)
FONT_UI   = ("Segoe UI",  10) if sys.platform == "win32" else ("Helvetica", 10)
FONT_BOLD = (FONT_UI[0], FONT_UI[1], "bold")
FONT_SM   = (FONT_UI[0], FONT_UI[1] - 1)


# ── Helpers ───────────────────────────────────────────────────────────────────
def load_instructions() -> str:
    if not INSTRUCTIONS_PATH.exists():
        INSTRUCTIONS_PATH.write_text(DEFAULT_INSTRUCTIONS, encoding="utf-8")
    return INSTRUCTIONS_PATH.read_text(encoding="utf-8").strip() or DEFAULT_INSTRUCTIONS.strip()


def trim_history(history, max_turns):
    system = [m for m in history if m["role"] == "system"]
    convo  = [m for m in history if m["role"] != "system"]
    if len(convo) > max_turns * 2:
        convo = convo[-(max_turns * 2):]
    return system + convo


def estimate_tokens(messages):
    return sum(len(str(m.get("content", ""))) for m in messages) // 4


def split_code_blocks(text):
    """
    Split text into segments: ('text', content) or ('code', lang, content).
    """
    pattern = re.compile(r'```(\w*)\n?(.*?)```', re.DOTALL)
    parts = []
    last = 0
    for m in pattern.finditer(text):
        if m.start() > last:
            parts.append(('text', text[last:m.start()]))
        lang = m.group(1).strip() or 'text'
        code = m.group(2).rstrip('\n')
        parts.append(('code', lang, code))
        last = m.end()
    if last < len(text):
        parts.append(('text', text[last:]))
    return parts


# ── Rounded button helper ─────────────────────────────────────────────────────
def RoundedButton(parent, text, command, bg=CYAN, fg=BG, font=None,
                  padx=14, pady=6, radius=8, **kwargs):
    """Canvas-based button with rounded corners."""
    font = font or FONT_BOLD
    btn = tk.Canvas(parent, bg=parent.cget("bg"), highlightthickness=0,
                    cursor="hand2", **kwargs)

    def draw(col):
        btn.delete("all")
        w, h = btn.winfo_width() or 80, btn.winfo_height() or 30
        r = radius
        btn.create_arc(0, 0, r*2, r*2, start=90, extent=90, fill=col, outline=col)
        btn.create_arc(w-r*2, 0, w, r*2, start=0, extent=90, fill=col, outline=col)
        btn.create_arc(0, h-r*2, r*2, h, start=180, extent=90, fill=col, outline=col)
        btn.create_arc(w-r*2, h-r*2, w, h, start=270, extent=90, fill=col, outline=col)
        btn.create_rectangle(r, 0, w-r, h, fill=col, outline=col)
        btn.create_rectangle(0, r, w, h-r, fill=col, outline=col)
        btn.create_text(w//2, h//2, text=text, fill=fg, font=font)

    _hover_col = [bg]

    def on_enter(_): _hover_col[0] = GREEN; draw(GREEN)
    def on_leave(_): _hover_col[0] = bg;    draw(bg)
    def on_click(_): command()

    btn.bind("<Enter>",    on_enter)
    btn.bind("<Leave>",    on_leave)
    btn.bind("<Button-1>", on_click)
    btn.bind("<Configure>", lambda _: draw(_hover_col[0]))

    # Set size
    tmp = tk.Label(parent, text=text, font=font)
    tmp.update_idletasks()
    w = tmp.winfo_reqwidth() + padx * 2
    h = tmp.winfo_reqheight() + pady * 2
    tmp.destroy()
    btn.config(width=w, height=h)
    return btn


# ── Chat engine ───────────────────────────────────────────────────────────────
class ChatEngine:
    def __init__(self):
        self.cfg            = load_config()
        self.system_prompt  = load_instructions()
        self.history        = [{"role": "system", "content": self.system_prompt}]
        self.session_tokens = 0
        self._stop          = threading.Event()

    @property
    def model(self):
        return get_active_model(self.cfg)

    def set_complexity(self, tier):
        self.cfg = set_complexity(tier, self.cfg)

    def reload_instructions(self):
        self.system_prompt = load_instructions()
        self.history[0] = {"role": "system", "content": self.system_prompt}

    def stop(self):
        self._stop.set()

    def send(self, user_input, on_tool=None, on_reply=None, on_warn=None, on_error=None):
        self._stop.clear()
        self.history = trim_history(self.history, MAX_HISTORY_TURNS)

        # Web search injection
        if search_needed(user_input):
            result = web_search(user_input)
            if not result.startswith("[Search"):
                if on_tool:
                    on_tool("search_web", result[:200])
                self.history.append({"role": "user", "content":
                    f"{user_input}\n\n[Web search results:]\n{result}"})
            else:
                self.history.append({"role": "user", "content": user_input})
        else:
            self.history.append({"role": "user", "content": user_input})

        model = self.model
        if not ensure_model(model):
            self.history.pop()
            if on_error:
                on_error(f"Could not load model '{model}'. Is Ollama running?")
            return None

        full_reply = ""
        try:
            stream = ollama.chat(model=model, messages=self.history, stream=True)
            for chunk in stream:
                if self._stop.is_set():
                    break
                token = chunk["message"]["content"]
                full_reply += token
                if on_reply:
                    on_reply(token)
        except Exception as e:
            self.history.pop()
            if on_error:
                on_error(f"Ollama error: {e}")
            return None

        self.history.append({"role": "assistant", "content": full_reply})
        self.session_tokens += estimate_tokens(self.history[-2:])
        return full_reply


# ── Code block widget ─────────────────────────────────────────────────────────
class CodeBlock(tk.Frame):
    """Rendered code block with language label + Copy + Download buttons."""

    def __init__(self, parent, lang, code, **kwargs):
        super().__init__(parent, bg=CODE_BG,
                         highlightbackground=CODE_BORDER,
                         highlightthickness=1, **kwargs)
        self.lang = lang
        self.code = code

        # Header row
        header = tk.Frame(self, bg=BG3)
        header.pack(fill="x")

        tk.Label(header, text=lang, bg=BG3, fg=DIM,
                 font=FONT_SM, padx=10, pady=4).pack(side="left")

        # Download button
        dl_btn = tk.Button(header, text="⬇ Download",
                           command=self._download,
                           bg=BG3, fg=DIM, relief="flat",
                           font=FONT_SM, cursor="hand2",
                           activebackground=BORDER, activeforeground=FG,
                           padx=8, pady=3, bd=0)
        dl_btn.pack(side="right", padx=(0, 4))

        # Copy button
        copy_btn = tk.Button(header, text="⧉ Copy",
                             command=self._copy,
                             bg=BG3, fg=CYAN, relief="flat",
                             font=FONT_SM, cursor="hand2",
                             activebackground=BORDER, activeforeground=FG,
                             padx=8, pady=3, bd=0)
        copy_btn.pack(side="right")
        self._copy_btn = copy_btn

        # Separator line
        tk.Frame(self, bg=CODE_BORDER, height=1).pack(fill="x")

        # Code text area
        txt = tk.Text(self, bg=CODE_BG, fg=FG,
                      font=FONT_MONO, relief="flat",
                      bd=0, padx=12, pady=10,
                      wrap="none", cursor="xterm",
                      state="normal",
                      height=min(max(code.count('\n') + 1, 2), 30))
        txt.insert("1.0", code)
        txt.config(state="disabled")
        txt.pack(fill="x", padx=0)

        # Horizontal scrollbar for long lines
        hbar = tk.Scrollbar(self, orient="horizontal", command=txt.xview,
                            bg=BG3, troughcolor=BG2)
        txt.config(xscrollcommand=hbar.set)
        hbar.pack(fill="x")

    def _copy(self):
        self.clipboard_clear()
        self.clipboard_append(self.code)
        self._copy_btn.config(text="✓ Copied!", fg=GREEN)
        self.after(1500, lambda: self._copy_btn.config(text="⧉ Copy", fg=CYAN))

    def _download(self):
        ext_map = {
            "python": ".py", "py": ".py",
            "javascript": ".js", "js": ".js",
            "typescript": ".ts", "ts": ".ts",
            "html": ".html", "css": ".css",
            "java": ".java", "c": ".c", "cpp": ".cpp",
            "csharp": ".cs", "cs": ".cs",
            "go": ".go", "rust": ".rs",
            "bash": ".sh", "shell": ".sh", "sh": ".sh",
            "powershell": ".ps1", "ps1": ".ps1",
            "sql": ".sql", "json": ".json",
            "yaml": ".yaml", "yml": ".yml",
            "xml": ".xml", "markdown": ".md", "md": ".md",
            "toml": ".toml", "ini": ".ini",
        }
        ext = ext_map.get(self.lang.lower(), ".txt")
        path = filedialog.asksaveasfilename(
            defaultextension=ext,
            initialfile=f"modmaster_code{ext}",
            filetypes=[(f"{self.lang} files", f"*{ext}"), ("All files", "*.*")]
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.code)


# ── Scrollable chat canvas ────────────────────────────────────────────────────
class ChatFrame(tk.Frame):
    """
    A vertically scrollable frame that holds mixed text + CodeBlock widgets.
    Text runs are rendered in a Text widget; code blocks are embedded frames.
    """

    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=BG, **kwargs)

        self._canvas = tk.Canvas(self, bg=BG, highlightthickness=0, bd=0)
        self._vbar   = tk.Scrollbar(self, orient="vertical",
                                    command=self._canvas.yview,
                                    bg=BG2, troughcolor=BG)
        self._canvas.configure(yscrollcommand=self._vbar.set)

        self._vbar.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)

        self._inner = tk.Frame(self._canvas, bg=BG)
        self._win_id = self._canvas.create_window((0, 0), window=self._inner,
                                                   anchor="nw")

        self._inner.bind("<Configure>", self._on_inner_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)
        self._canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        # Current streaming Text widget (None when idle)
        self._stream_text: tk.Text | None = None
        self._stream_buf = ""   # buffer of raw text being streamed

    def _on_inner_configure(self, _=None):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_configure(self, e):
        self._canvas.itemconfig(self._win_id, width=e.width)

    def _on_mousewheel(self, e):
        self._canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")

    def _scroll_bottom(self):
        self._canvas.update_idletasks()
        self._canvas.yview_moveto(1.0)

    # ── Public API ────────────────────────────────────────────────────────────
    def add_label(self, text, fg=DIM, font=None, padx=14, pady=(6, 0)):
        font = font or FONT_UI
        tk.Label(self._inner, text=text, bg=BG, fg=fg, font=font,
                 anchor="w", padx=padx, pady=pady[1]
                 ).pack(fill="x", padx=(padx, 0), pady=pady)
        self._scroll_bottom()

    def add_text_block(self, text, fg=FG, font=None, padx=14):
        """Add a static multi-line text widget (for completed messages)."""
        font = font or FONT_MONO
        if not text.strip():
            return
        lines = text.count('\n') + 1
        t = tk.Text(self._inner, bg=BG, fg=fg, font=font,
                    relief="flat", bd=0, padx=padx, pady=4,
                    wrap="word", state="normal",
                    height=lines, cursor="xterm")
        t.insert("1.0", text)
        t.config(state="disabled")
        t.pack(fill="x")
        self._scroll_bottom()

    def add_code_block(self, lang, code, padx=14):
        f = tk.Frame(self._inner, bg=BG)
        CodeBlock(f, lang, code).pack(fill="x", padx=padx, pady=(4, 8))
        f.pack(fill="x")
        self._scroll_bottom()

    def start_stream(self):
        """Begin a streaming text widget. Returns it."""
        self._stream_buf = ""
        t = tk.Text(self._inner, bg=BG, fg=FG, font=FONT_MONO,
                    relief="flat", bd=0, padx=14, pady=4,
                    wrap="word", state="normal", height=1, cursor="xterm")
        t.pack(fill="x")
        self._stream_text = t
        return t

    def append_stream_token(self, token):
        """Append a token to the active stream widget."""
        if self._stream_text is None:
            return
        self._stream_buf += token
        t = self._stream_text
        t.config(state="normal")
        t.insert("end", token)
        # auto-resize height
        lines = int(t.index("end-1c").split(".")[0])
        t.config(height=max(lines, 1))
        t.config(state="disabled")
        self._scroll_bottom()

    def finish_stream(self):
        """
        End streaming. Parse the buffered text for code blocks and
        re-render the whole message properly.
        """
        if self._stream_text is None:
            return
        raw = self._stream_buf
        # Remove the streaming widget
        self._stream_text.destroy()
        self._stream_text = None
        self._stream_buf  = ""

        # Re-render with code block detection
        parts = split_code_blocks(raw)
        for part in parts:
            if part[0] == 'text':
                txt = part[1]
                if txt.strip():
                    self.add_text_block(txt)
            else:
                _, lang, code = part
                self.add_code_block(lang, code)

        # Spacer
        tk.Frame(self._inner, bg=BG, height=8).pack()
        self._scroll_bottom()

    def clear(self):
        for w in self._inner.winfo_children():
            w.destroy()
        self._stream_text = None
        self._stream_buf  = ""


# ── Main GUI ──────────────────────────────────────────────────────────────────
class ModMasterGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("ModMaster")
        self.root.configure(bg=BG)
        self.root.minsize(720, 520)

        self.engine        = ChatEngine()
        self.busy          = False
        self.attached_file = None

        self._build_menu()
        self._build_layout()

        if ICON_PATH.exists():
            try:
                self.root.iconbitmap(str(ICON_PATH))
            except Exception:
                pass

        self._sys_message(
            f"ModMaster  —  model: {self.engine.model}\n"
            f"System prompt loaded ({len(self.engine.system_prompt):,} chars). "
            "Type /help for commands."
        )

    # ── Menu ──────────────────────────────────────────────────────────────────
    def _build_menu(self):
        menu = tk.Menu(self.root, bg=BG2, fg=FG, activebackground=BORDER,
                       activeforeground=FG, relief="flat", tearoff=False)
        self.root.config(menu=menu)

        session = tk.Menu(menu, bg=BG2, fg=FG, activebackground=BORDER,
                          activeforeground=FG, tearoff=False)
        menu.add_cascade(label="Session", menu=session)
        session.add_command(label="Clear history",  command=self.cmd_clear)
        session.add_command(label="Show history",   command=self.cmd_history)
        session.add_command(label="Token usage",    command=self.cmd_tokens)
        session.add_separator()
        session.add_command(label="Exit",           command=self.root.quit)

        cfg_menu = tk.Menu(menu, bg=BG2, fg=FG, activebackground=BORDER,
                           activeforeground=FG, tearoff=False)
        menu.add_cascade(label="Config", menu=cfg_menu)
        cfg_menu.add_command(label="Change model…",       command=self.cmd_model_dialog)
        cfg_menu.add_command(label="Complexity tier…",    command=self.cmd_complexity_dialog)
        cfg_menu.add_command(label="Attach file…",        command=self._on_attach)
        cfg_menu.add_command(label="Load instructions…",  command=self.cmd_load_instructions)
        cfg_menu.add_command(label="Reload instructions", command=self.cmd_reload_instructions)
        cfg_menu.add_command(label="Show system prompt",  command=self.cmd_system)

        menu.add_command(label="Help", command=self.cmd_help)

    # ── Layout ────────────────────────────────────────────────────────────────
    def _build_layout(self):
        # Status bar
        self.status_var = tk.StringVar(value=f"  Model: {self.engine.model}  |  Tokens: 0")
        tk.Label(self.root, textvariable=self.status_var,
                 bg=BG2, fg=DIM, font=FONT_UI, anchor="w",
                 relief="flat", bd=0).pack(side="top", fill="x")
        tk.Frame(self.root, bg=BORDER, height=1).pack(fill="x")

        # Chat area
        self.chat_frame = ChatFrame(self.root)
        self.chat_frame.pack(fill="both", expand=True)

        tk.Frame(self.root, bg=BORDER, height=1).pack(fill="x")

        # ── Input area ────────────────────────────────────────────────────────
        input_area = tk.Frame(self.root, bg=BG2, pady=10)
        input_area.pack(fill="x")
        input_area.columnconfigure(0, weight=1)

        # Attach label row
        self.attach_label_var = tk.StringVar(value="")
        self.attach_label = tk.Label(input_area, textvariable=self.attach_label_var,
                                     bg=BG2, fg=YELLOW,
                                     font=FONT_SM, anchor="w")
        self.attach_label.grid(row=0, column=0, columnspan=3,
                               sticky="w", padx=14, pady=(0, 4))

        # Input entry
        self.input_var = tk.StringVar()
        self.input_box = tk.Entry(input_area, textvariable=self.input_var,
                                  bg=INPUT_BG, fg=FG, insertbackground=FG,
                                  font=FONT_MONO, relief="flat", bd=8)
        self.input_box.grid(row=1, column=0, sticky="ew", padx=(14, 6), ipady=4)
        self.input_box.bind("<Return>",   self._on_enter)
        self.input_box.bind("<KP_Enter>", self._on_enter)
        self.input_box.focus_set()

        # Attach button
        tk.Button(input_area, text="📎",
                  command=self._on_attach,
                  bg=BG2, fg=YELLOW,
                  font=(FONT_UI[0], FONT_UI[1] + 2),
                  relief="flat", padx=6, pady=6,
                  cursor="hand2", activebackground=BORDER,
                  bd=0).grid(row=1, column=1, padx=(0, 4))

        # Stop button (red, always visible, only active when busy)
        self.stop_btn = tk.Button(input_area, text="■ Stop",
                                  command=self._on_stop,
                                  bg="#3d0f0f", fg=RED,
                                  font=FONT_BOLD,
                                  relief="flat", padx=12, pady=6,
                                  cursor="hand2",
                                  activebackground="#5a1a1a",
                                  activeforeground=RED,
                                  state="disabled")
        self.stop_btn.grid(row=1, column=2, padx=(0, 6))

        # Send button (rounded canvas)
        self.send_btn = RoundedButton(input_area, text="Send ▶",
                                      command=self._on_send,
                                      bg=CYAN, fg=BG,
                                      font=FONT_BOLD,
                                      padx=14, pady=6)
        self.send_btn.grid(row=1, column=3, padx=(0, 14))

        # Spinner
        self.spinner_var = tk.StringVar(value="")
        tk.Label(self.root, textvariable=self.spinner_var,
                 bg=BG, fg=YELLOW, font=FONT_UI).pack(pady=(0, 2))

    # ── System message helper ─────────────────────────────────────────────────
    def _sys_message(self, text):
        self.chat_frame.add_label(text, fg=DIM, font=FONT_UI, padx=14, pady=(8, 4))

    # ── Busy state ────────────────────────────────────────────────────────────
    def _set_busy(self, busy):
        self.busy = busy
        self.input_box.config(state="disabled" if busy else "normal")
        self.stop_btn.config(state="normal" if busy else "disabled")
        self.spinner_var.set("  ● thinking…" if busy else "")

    def _update_status(self):
        self.status_var.set(
            f"  Model: {self.engine.model}"
            f"  |  Session tokens: ~{self.engine.session_tokens:,}"
        )

    # ── Input handling ────────────────────────────────────────────────────────
    def _on_enter(self, _=None):
        if not self.busy:
            self._on_send()

    def _on_stop(self):
        self.engine.stop()
        self.spinner_var.set("  ■ stopped")

    def _on_send(self):
        text = self.input_var.get().strip()
        if not text or self.busy:
            return
        self.input_var.set("")

        if self.attached_file:
            fname, fcontent = self.attached_file
            text = (f"[Attached file: {fname}]\n```\n{fcontent}\n```\n\n{text}")
            self.attached_file = None
            self._update_attach_label()

        self._handle_input(text)

    def _handle_input(self, text):
        if text.startswith("/"):
            cmd   = text.split()[0].lower()
            parts = text.split(maxsplit=1)

            if   cmd == "/help":    self.cmd_help()
            elif cmd == "/clear":   self.cmd_clear()
            elif cmd == "/history": self.cmd_history()
            elif cmd == "/tokens":  self.cmd_tokens()
            elif cmd == "/system":  self.cmd_system()
            elif cmd == "/reload":  self.cmd_reload_instructions()
            elif cmd == "/complexity":
                if len(parts) >= 2:
                    tier = parts[1].strip().lower()
                    try:
                        self.engine.set_complexity(tier)
                        self._sys_message(f"Complexity → {tier}  |  model: {self.engine.model}")
                        self._update_status()
                    except ValueError as e:
                        self._sys_message(f"✖ {e}")
                else:
                    self._sys_message(
                        f"Complexity: {self.engine.cfg.get('complexity','medium')}"
                        f"  |  model: {self.engine.model}\n"
                        "Usage: /complexity low|medium|high|ultra")
            elif cmd == "/model":
                if len(parts) >= 2:
                    m = parts[1].strip()
                    self.engine.cfg["custom_model"] = m
                    save_config(self.engine.cfg)
                    self._sys_message(f"Model set to: {m}")
                    self._update_status()
                else:
                    self._sys_message(f"Active model: {self.engine.model}")
            else:
                self._sys_message(f"⚠ Unknown command: {cmd}. Type /help.")
            return

        # Show user bubble
        self.chat_frame.add_label("You", fg=GREEN,
                                  font=(FONT_MONO[0], FONT_MONO[1], "bold"),
                                  padx=14, pady=(10, 0))
        self.chat_frame.add_text_block(text, fg=FG)

        self._set_busy(True)
        threading.Thread(target=self._run_chat, args=(text,), daemon=True).start()

    def _run_chat(self, user_input):
        # Bot name label
        self.root.after(0, lambda: self.chat_frame.add_label(
            "ModMaster", fg=CYAN,
            font=(FONT_MONO[0], FONT_MONO[1], "bold"),
            padx=14, pady=(10, 0)))

        # Start streaming text widget
        self.root.after(0, self.chat_frame.start_stream)

        def on_token(t):
            self.root.after(0, self.chat_frame.append_stream_token, t)

        def on_tool(name, result):
            self.root.after(0, lambda: self.chat_frame.add_label(
                f"  ⚙ {name} → {result[:120]}", fg=YELLOW, font=FONT_SM,
                padx=18, pady=(2, 0)))

        def on_warn(t):
            self.root.after(0, lambda: self.chat_frame.add_label(
                f"  ⚠ {t}", fg=YELLOW, font=FONT_SM, padx=18, pady=(2, 0)))

        def on_error(t):
            self.root.after(0, lambda: self.chat_frame.add_label(
                f"  ✖ {t}", fg=RED, font=FONT_SM, padx=18, pady=(2, 0)))

        self.engine.send(user_input,
                         on_tool=on_tool, on_reply=on_token,
                         on_warn=on_warn, on_error=on_error)

        # Finish: re-render stream with code blocks
        self.root.after(0, self.chat_frame.finish_stream)
        self.root.after(0, self._update_status)
        self.root.after(0, self._set_busy, False)

    # ── Commands ──────────────────────────────────────────────────────────────
    def cmd_help(self):
        self._sys_message(
            "Commands:\n"
            "  /help                           — show this\n"
            "  /clear                          — clear history\n"
            "  /history                        — show history\n"
            "  /tokens                         — token usage\n"
            "  /model <name>                   — set model directly\n"
            "  /complexity low|medium|high|ultra\n"
            "  /system                         — show system prompt\n"
            "  /reload                         — reload instructions.txt\n\n"
            "Menu → Config for model picker, file attach, instructions."
        )

    def cmd_clear(self):
        self.engine.history = [self.engine.history[0]]
        self.chat_frame.clear()
        self._sys_message("History cleared.")

    def cmd_history(self):
        lines = []
        for i, m in enumerate(self.engine.history):
            role    = m["role"].upper()
            content = str(m.get("content", ""))[:200]
            lines.append(f"[{i}] {role}: {content}")
        self._sys_message("\n".join(lines) or "(empty)")

    def cmd_tokens(self):
        est = estimate_tokens(self.engine.history)
        self._sys_message(
            f"Context tokens (est): ~{est:,}\n"
            f"Session total sent:   ~{self.engine.session_tokens:,}")

    def cmd_system(self):
        preview = self.engine.history[0]["content"][:1000]
        suffix  = "…" if len(self.engine.history[0]["content"]) > 1000 else ""
        self._sys_message(f"── System Prompt ──\n{preview}{suffix}")

    def cmd_reload_instructions(self):
        self.engine.reload_instructions()
        self._sys_message(
            f"instructions.txt reloaded ({len(self.engine.system_prompt):,} chars).")

    def cmd_load_instructions(self):
        path = filedialog.askopenfilename(
            title="Load instructions file",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if not path:
            return
        try:
            content = Path(path).read_text(encoding="utf-8").strip()
            if not content:
                messagebox.showwarning("Empty file", "The file was empty.", parent=self.root)
                return
            self.engine.history = [{"role": "system", "content": content}]
            self.engine.system_prompt = content
            self._sys_message(f"Loaded '{os.path.basename(path)}' ({len(content):,} chars). History cleared.")
        except Exception as e:
            self._sys_message(f"✖ Could not load file: {e}")

    def cmd_model_dialog(self):
        LOCAL_MODELS = [
            "qwen2.5:1.5b", "qwen2.5:3b", "qwen2.5:7b", "qwen2.5:14b",
            "qwen2.5:32b", "qwen2.5:72b",
            "llama3.1:8b", "llama3.1:70b",
            "llama3.2:1b", "llama3.2:3b",
            "llama3.3:70b",
            "mistral:7b", "mistral-nemo",
            "gemma2:2b", "gemma2:9b", "gemma2:27b",
            "deepseek-r1:7b", "deepseek-r1:14b", "deepseek-r1:32b", "deepseek-r1:70b",
            "phi4:14b", "phi3.5:3.8b",
        ]
        dlg = tk.Toplevel(self.root)
        dlg.title("Select Model")
        dlg.configure(bg=BG)
        dlg.resizable(False, False)
        dlg.grab_set()

        tk.Label(dlg, text="Choose a local Ollama model:", bg=BG, fg=FG,
                 font=FONT_UI, pady=8).pack(padx=16)

        style = ttk.Style()
        style.theme_use("default")
        style.configure("Dark.TCombobox",
                        fieldbackground=INPUT_BG, background=BG2,
                        foreground=FG, selectbackground=BORDER,
                        selectforeground=FG, arrowcolor=CYAN, bordercolor=BORDER)
        style.map("Dark.TCombobox",
                  fieldbackground=[("readonly", INPUT_BG)],
                  foreground=[("readonly", FG)],
                  selectbackground=[("readonly", BORDER)],
                  selectforeground=[("readonly", FG)])

        var = tk.StringVar(value=self.engine.model)
        combo = ttk.Combobox(dlg, textvariable=var, values=LOCAL_MODELS,
                             width=40, state="readonly", style="Dark.TCombobox",
                             font=FONT_MONO)
        combo.pack(padx=16, pady=4)
        if self.engine.model in LOCAL_MODELS:
            combo.current(LOCAL_MODELS.index(self.engine.model))

        tk.Label(dlg, text="— or type a custom model string —",
                 bg=BG, fg=DIM, font=FONT_SM).pack(pady=(6, 0))
        custom_var = tk.StringVar()
        tk.Entry(dlg, textvariable=custom_var, width=42,
                 bg=INPUT_BG, fg=FG, insertbackground=FG,
                 relief="flat", font=FONT_MONO, bd=6).pack(padx=16, pady=4)

        def confirm():
            m = custom_var.get().strip() or var.get().strip()
            if m:
                self.engine.cfg["custom_model"] = m
                save_config(self.engine.cfg)
                self._sys_message(f"Model set to: {m}")
                self._update_status()
                dlg.destroy()

        tk.Button(dlg, text="Apply", command=confirm,
                  bg=CYAN, fg=BG, font=FONT_UI,
                  relief="flat", padx=12, pady=4, cursor="hand2").pack(pady=10)

    def cmd_complexity_dialog(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("Complexity Tier")
        dlg.configure(bg=BG)
        dlg.resizable(False, False)
        dlg.grab_set()

        tk.Label(dlg, text="Select complexity tier:", bg=BG, fg=FG,
                 font=FONT_UI, pady=8).pack(padx=20)

        tiers = [
            ("low",    "1B–3B   — fast, low VRAM"),
            ("medium", "7B–8B   — balanced"),
            ("high",   "13B–14B — powerful"),
            ("ultra",  "30B–70B — maximum"),
        ]
        var = tk.StringVar(value=self.engine.cfg.get("complexity", "medium"))
        for val, label in tiers:
            tk.Radiobutton(dlg, text=f"{val:8s}  {label}",
                           variable=var, value=val,
                           bg=BG, fg=FG, selectcolor=BG2,
                           activebackground=BG, activeforeground=CYAN,
                           font=FONT_MONO).pack(anchor="w", padx=24, pady=2)

        def confirm():
            self.engine.set_complexity(var.get())
            self._sys_message(f"Complexity → {var.get()}  |  model: {self.engine.model}")
            self._update_status()
            dlg.destroy()

        tk.Button(dlg, text="Apply", command=confirm,
                  bg=CYAN, fg=BG, font=FONT_UI,
                  relief="flat", padx=12, pady=4, cursor="hand2").pack(pady=10)

    # ── File attachment ───────────────────────────────────────────────────────
    def _on_attach(self):
        path = filedialog.askopenfilename(
            title="Attach a file",
            filetypes=[
                ("Text / code",
                 "*.txt *.md *.py *.js *.ts *.cs *.json *.yaml *.yml "
                 "*.csv *.log *.xml *.html *.css"),
                ("All files", "*.*"),
            ])
        if not path:
            return
        try:
            size = os.path.getsize(path)
            if size > 100_000:
                messagebox.showwarning("File too large",
                    f"File is {size//1024} KB. Maximum is 100 KB.", parent=self.root)
                return
            content = Path(path).read_text(encoding="utf-8", errors="replace")
            self.attached_file = (os.path.basename(path), content)
            self._update_attach_label()
            self._sys_message(
                f"📎 Attached: {os.path.basename(path)} ({len(content):,} chars)"
                " — will be sent with your next message.")
        except Exception as e:
            self._sys_message(f"✖ Could not read file: {e}")

    def _update_attach_label(self):
        if self.attached_file:
            name, content = self.attached_file
            self.attach_label_var.set(
                f"📎 {name}  ({len(content):,} chars)  [× click to remove]")
            self.attach_label.config(cursor="hand2")
            self.attach_label.bind("<Button-1>", self._clear_attachment)
        else:
            self.attach_label_var.set("")
            self.attach_label.config(cursor="")
            self.attach_label.unbind("<Button-1>")

    def _clear_attachment(self, _=None):
        self.attached_file = None
        self._update_attach_label()
        self._sys_message("Attachment removed.")


# ── Entry point ───────────────────────────────────────────────────────────────
def main():
    root = tk.Tk()
    root.geometry("900x660")
    ModMasterGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
