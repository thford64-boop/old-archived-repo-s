"""
MODMASTER v2 — Unified GUI Edition
Self-contained: runs as a Tkinter GUI OR as a pipe-mode backend for ModMasterForm.exe.

Usage:
    python MODMASTER_GUI.py              # opens Tkinter window
    python MODMASTER_GUI.py --pipe-mode  # stdin/stdout JSON pipe (used by ModMasterForm.exe)

Dependencies:
    pip install litellm python-dotenv
"""

import os
import sys
import json
import time
import threading
import re
import warnings
from tavily import TavilyClient
warnings.filterwarnings("ignore")

# ── dotenv ──────────────────────────────────────────────────────────────────
from dotenv import load_dotenv
load_dotenv()

from tavily import TavilyClient
client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

# ─── CONFIG ─────────────────────────────────────────────────────────────────
MODEL             = "groq/llama-3.3-70b-versatile"
INSTRUCTIONS_FILE = "instructions.txt"
MAX_HISTORY_TURNS = 12
MAX_RETRIES       = 3
RETRY_BASE_DELAY  = 5

# ─── GROQ MODEL CATALOGUE ────────────────────────────────────────────────────
GROQ_MODELS = [
    # ── Llama 3.3 ──────────────────────────────────────────────────────────
    "groq/llama-3.3-70b-versatile",
    "groq/llama-3.3-70b-specdec",
    # ── Llama 3.1 ──────────────────────────────────────────────────────────
    "groq/llama-3.1-8b-instant",
    "groq/llama-3.1-70b-versatile",
    # ── Llama 3.2 (vision) ─────────────────────────────────────────────────
    "groq/llama-3.2-1b-preview",
    "groq/llama-3.2-3b-preview",
    "groq/llama-3.2-11b-vision-preview",
    "groq/llama-3.2-90b-vision-preview",
    # ── Llama 3 ────────────────────────────────────────────────────────────
    "groq/llama3-8b-8192",
    "groq/llama3-70b-8192",
    # ── Mixtral ────────────────────────────────────────────────────────────
    "groq/mixtral-8x7b-32768",
    # ── Gemma ──────────────────────────────────────────────────────────────
    "groq/gemma2-9b-it",
    "groq/gemma-7b-it",
    # ── DeepSeek ───────────────────────────────────────────────────────────
    "groq/deepseek-r1-distill-llama-70b",
    "groq/deepseek-r1-distill-qwen-32b",
    # ── Qwen ───────────────────────────────────────────────────────────────
    "groq/qwen-qwq-32b",
    "groq/qwen-2.5-coder-32b",
    # ── Whisper (audio — listed for reference) ─────────────────────────────
    "groq/whisper-large-v3",
    "groq/whisper-large-v3-turbo",
]

TOOL_TRIGGER_WORDS = {
    "time", "date", "clock", "calculate", "add", "sum", "plus",
    "search", "look up", "find", "what is", "latest", "current",
    "read", "open", "file", "list", "directory", "folder",
    "skibidi", "news", "who is", "how much", "price", "when did",
}

def should_use_tools(text: str) -> bool:
    lower = text.lower()
    return any(word in lower for word in TOOL_TRIGGER_WORDS)

# ── Direct web search (bypasses tool-call entirely) ──────────────────────────
SEARCH_TRIGGER = re.compile(
    r"\b(search|look up|find|google|what is|who is|latest|current|news about"
    r"|tell me about|skibidi|how much|price of|when did)\b",
    re.IGNORECASE,
)

def try_direct_search(text: str):
    """
    If the user message looks like a search request, run Tavily directly
    and return the result string — bypassing LLM tool-calling entirely.
    Returns None if not a search request or Tavily fails.
    """
    if not SEARCH_TRIGGER.search(text):
        return None
    # Extract a search query: strip leading command verbs
    query = re.sub(
        r'^(search\s+(online\s+)?(for\s+)?|look\s+up\s+|google\s+|find\s+)',
        '', text, flags=re.IGNORECASE
    ).strip().strip('"\'')
    if not query:
        query = text
    try:
        result = client.search(query=query, max_results=5)
        snippets = []
        for r in result.get("results", [])[:5]:
            title   = r.get("title", "")
            content = r.get("content", "")[:300]
            url     = r.get("url", "")
            snippets.append(f"• {title}\n  {content}\n  {url}")
        return "\n\n".join(snippets) if snippets else "No results found."
    except Exception as e:
        return None   # fall through to normal LLM path

# ─── TOOLS ──────────────────────────────────────────────────────────────────
def get_time() -> str:
    from datetime import datetime
    return datetime.now().strftime("%A, %B %d %Y — %H:%M:%S")

def add_numbers(a: float, b: float) -> float:
    return a + b

def search_web_stub(query: str) -> str:
    try:
        result = client.search(query=query, max_results=5)
        return str(result)
    except Exception as e:
        return f"Web search error: {e}"

def read_file(path: str) -> str:
    path = os.path.expanduser(path)
    if not os.path.exists(path):
        return f"File not found: {path}"
    if os.path.getsize(path) > 50_000:
        return "File too large (>50KB). Refusing to read."
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()

def list_directory(path: str = ".") -> str:
    path = os.path.expanduser(path)
    try:
        entries = os.listdir(path)
        return "\n".join(sorted(entries)) or "(empty directory)"
    except Exception as e:
        return str(e)

TOOL_REGISTRY = {
    "get_time":       get_time,
    "add_numbers":    add_numbers,
    "search_web":     search_web_stub,
    "read_file":      read_file,
    "list_directory": list_directory,
}

TOOLS = [
    {"type": "function", "function": {
        "name": "get_time",
        "description": "Returns the current date and time.",
        "parameters": {"type": "object", "properties": {}, "required": []}
    }},
    {"type": "function", "function": {
        "name": "add_numbers",
        "description": "Adds two numbers.",
        "parameters": {"type": "object", "properties": {
            "a": {"type": "number"}, "b": {"type": "number"}
        }, "required": ["a", "b"]}
    }},
    {"type": "function", "function": {
        "name": "search_web",
        "description": "Search the web for current information.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "Search query"}
        }, "required": ["query"]}
    }},
    {"type": "function", "function": {
        "name": "read_file",
        "description": "Read the contents of a local file by path.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string", "description": "File path to read"}
        }, "required": ["path"]}
    }},
    {"type": "function", "function": {
        "name": "list_directory",
        "description": "List files in a directory.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string", "description": "Directory path"}
        }, "required": []}
    }},
]

def handle_tool_call(name: str, arguments) -> str:
    args = json.loads(arguments) if isinstance(arguments, str) else arguments
    fn = TOOL_REGISTRY.get(name)
    if not fn:
        return f"Unknown tool: {name}"
    try:
        return str(fn(**args))
    except Exception as e:
        return f"Tool error: {e}"

def estimate_tokens(messages: list) -> int:
    total = sum(len(str(m.get("content", ""))) for m in messages)
    return total // 4

def trim_history(history: list, max_turns: int) -> list:
    system = [m for m in history if m["role"] == "system"]
    convo  = [m for m in history if m["role"] != "system"]
    if len(convo) > max_turns * 2:
        convo = convo[-(max_turns * 2):]
    return system + convo

def load_system_prompt(filepath: str) -> str:
    if not os.path.exists(filepath):
        return "You are a helpful, concise assistant."
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read().strip()
    return content if content else "You are a helpful, concise assistant."

# ─── SHARED CHAT ENGINE ──────────────────────────────────────────────────────
class ChatEngine:
    """Shared LLM logic used by both GUI and pipe modes."""

    def __init__(self, model: str, system_prompt: str):
        self.model   = model
        self.history = [{"role": "system", "content": system_prompt}]
        self.session_tokens = 0

    def send(self, user_input: str,
             on_tool=None, on_reply=None, on_warn=None, on_error=None):
        """
        Synchronous chat round.  Callbacks fired during processing:
          on_tool(name, result)
          on_reply(text)
          on_warn(text)
          on_error(text)
        Returns reply text or None on failure.
        """
        self.history = trim_history(self.history, MAX_HISTORY_TURNS)

        # ── Direct search shortcut (avoids flaky tool-calling on Groq) ──────
        search_result = try_direct_search(user_input)
        if search_result is not None:
            if on_tool:
                on_tool("search_web", search_result[:200])
            # Inject search results as context in the user message
            augmented = (
                f"{user_input}\n\n"
                f"[Web search results for context:]\n{search_result}"
            )
            self.history.append({"role": "user", "content": augmented})
        else:
            self.history.append({"role": "user", "content": user_input})

        # Only use LLM tool-calling for non-search tools (time, math, files)
        use_tools = should_use_tools(user_input) and search_result is None

        from litellm import completion
        from litellm.exceptions import RateLimitError

        for attempt in range(MAX_RETRIES):
            try:
                kwargs = {"model": self.model, "messages": self.history}
                if use_tools:
                    # Groq works better without tool_choice="auto" on some models
                    kwargs["tools"] = TOOLS
                    # Only add tool_choice if not a Groq model to avoid errors
                    if not self.model.startswith("groq/"):
                        kwargs["tool_choice"] = "auto"
                response = completion(**kwargs)

            except RateLimitError as e:
                msg       = str(e)
                wait_hint = ""
                if "Please try again in" in msg:
                    try:
                        s = msg.index("Please try again in") + len("Please try again in ")
                        e2 = msg.index(".", s) if "." in msg[s:] else len(msg)
                        wait_hint = msg[s:e2]
                    except Exception:
                        pass
                if attempt < MAX_RETRIES - 1:
                    delay = RETRY_BASE_DELAY * (2 ** attempt)
                    if on_warn:
                        on_warn(f"Rate limit — retrying in {delay}s… ({attempt+1}/{MAX_RETRIES})")
                    time.sleep(delay)
                    continue
                else:
                    extra = f" Try again in {wait_hint}." if wait_hint else ""
                    if on_error:
                        on_error(f"Rate limit — giving up.{extra}")
                    self.history.pop()
                    return None

            except Exception as e:
                err = str(e)
                if use_tools:
                    # Tool-calling failed — retry without tools instead of crashing
                    if on_warn:
                        on_warn("Tool call failed — retrying without tools…")
                    use_tools = False
                    kwargs.pop("tools", None)
                    kwargs.pop("tool_choice", None)
                    continue
                if on_error:
                    on_error(f"Error: {e}")
                self.history.pop()
                return None

            try:
                self.session_tokens += response.usage.total_tokens
            except Exception:
                self.session_tokens += estimate_tokens(self.history)

            message = response.choices[0].message

            if message.tool_calls:
                self.history.append({
                    "role": "assistant",
                    "content": message.content or "",
                    "tool_calls": [
                        {"id": tc.id, "type": "function",
                         "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                        for tc in message.tool_calls
                    ]
                })
                for tc in message.tool_calls:
                    result = handle_tool_call(tc.function.name, tc.function.arguments)
                    if on_tool:
                        on_tool(tc.function.name, result)
                    self.history.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result
                    })
                continue  # loop for final reply

            else:
                reply = message.content or ""
                self.history.append({"role": "assistant", "content": reply})
                if on_reply:
                    on_reply(reply)
                return reply

        return None

# ─── PIPE MODE (for ModMasterForm.exe) ─────────────────────────────────────────
def run_pipe_mode():
    """
    JSON-over-stdin/stdout protocol used by ModMasterForm.exe.

    Every line from the C# shell is a JSON object:
        {"type": "chat", "text": "hello"}
        {"type": "command", "cmd": "/clear"}
        {"type": "set_model", "model": "groq/..."}

    Replies are JSON lines:
        {"type": "reply",  "text": "..."}
        {"type": "tool",   "name": "get_time", "result": "..."}
        {"type": "warn",   "text": "..."}
        {"type": "error",  "text": "..."}
        {"type": "status", "text": "..."}
        {"type": "ready"}
    """
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)
    sys.stdin  = io.TextIOWrapper(sys.stdin.buffer,  encoding='utf-8')

    def emit(obj):
        print(json.dumps(obj, ensure_ascii=False), flush=True)

    system_prompt = load_system_prompt(INSTRUCTIONS_FILE)
    engine = ChatEngine(MODEL, system_prompt)

    emit({"type": "status", "text": f"MODMASTER v2  |  model: {engine.model}"})
    emit({"type": "ready"})

    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            emit({"type": "error", "text": f"Bad JSON from host: {raw[:80]}"})
            continue

        kind = msg.get("type", "")

        if kind == "chat":
            text = msg.get("text", "").strip()
            if not text:
                continue

            # Built-in slash commands
            if text.startswith("/"):
                cmd = text.split()[0].lower()
                if cmd == "/clear":
                    engine.history = [engine.history[0]]
                    emit({"type": "status", "text": "History cleared."})
                elif cmd == "/history":
                    lines = [f"[{i}] {m['role'].upper()}: {str(m.get('content',''))[:200]}"
                             for i, m in enumerate(engine.history)]
                    emit({"type": "reply", "text": "\n".join(lines) or "(empty)"})
                elif cmd == "/tokens":
                    est = estimate_tokens(engine.history)
                    emit({"type": "reply",
                          "text": f"Context tokens: ~{est:,}\nSession sent: ~{engine.session_tokens:,}"})
                elif cmd == "/system":
                    preview = engine.history[0]["content"][:1000]
                    emit({"type": "reply", "text": f"── System Prompt ──\n{preview}"})
                elif cmd == "/model":
                    parts = text.split(maxsplit=1)
                    if len(parts) >= 2:
                        engine.model = parts[1].strip()
                        emit({"type": "status",
                              "text": f"Switched to model: {engine.model}"})
                    else:
                        emit({"type": "reply", "text": f"Current model: {engine.model}"})
                elif cmd == "/help":
                    emit({"type": "reply", "text": (
                        "Commands:\n"
                        "  /help         — this help\n"
                        "  /clear        — clear history\n"
                        "  /history      — show history\n"
                        "  /tokens       — token usage\n"
                        "  /model <name> — switch model\n"
                        "  /system       — show system prompt"
                    )})
                else:
                    emit({"type": "warn", "text": f"Unknown command: {cmd}"})
                emit({"type": "done"})
                continue

            engine.send(
                text,
                on_tool  = lambda n, r: emit({"type": "tool",  "name": n, "result": r[:200]}),
                on_reply = lambda t:    emit({"type": "reply", "text": t}),
                on_warn  = lambda t:    emit({"type": "warn",  "text": t}),
                on_error = lambda t:    emit({"type": "error", "text": t}),
            )
            emit({"type": "status",
                  "text": f"Model: {engine.model}  |  Session tokens: ~{engine.session_tokens:,}"})
            emit({"type": "done"})

        elif kind == "set_model":
            engine.model = msg.get("model", engine.model)
            emit({"type": "status", "text": f"Model: {engine.model}"})

        elif kind == "set_system":
            sp = msg.get("prompt", "").strip()
            if sp:
                engine.history = [{"role": "system", "content": sp}]
                emit({"type": "status", "text": "System prompt updated, history cleared."})

        elif kind == "ping":
            emit({"type": "pong"})

        else:
            emit({"type": "warn", "text": f"Unknown message type: {kind}"})

# ─── COLOUR PALETTE ─────────────────────────────────────────────────────────
BG        = "#0d1117"
BG2       = "#161b22"
BORDER    = "#30363d"
CYAN      = "#79c0ff"
GREEN     = "#56d364"
YELLOW    = "#e3b341"
RED       = "#f85149"
DIM       = "#8b949e"
FG        = "#e6edf3"
INPUT_BG  = "#1c2128"
FONT_MONO = ("Consolas", 10) if sys.platform == "win32" else ("Menlo", 10)
FONT_UI   = ("Segoe UI",  10) if sys.platform == "win32" else ("Helvetica", 10)

# ─── TKINTER GUI ────────────────────────────────────────────────────────────
class ModmasterGUI:
    def __init__(self, root):
        import tkinter as tk
        from tkinter import ttk, scrolledtext, filedialog, messagebox
        self.tk  = tk
        self.fb  = filedialog
        self.mb  = messagebox
        self.root = root
        self.root.title("MODMASTER v2")
        self.root.configure(bg=BG)
        self.root.minsize(700, 500)

        self.system_prompt  = load_system_prompt(INSTRUCTIONS_FILE)
        self.engine         = ChatEngine(MODEL, self.system_prompt)
        self.busy           = False
        self.attached_file  = None   # (path, content) or None

        self._build_menu()
        self._build_layout()
        self._check_api_key()

        self._append("system",
            f"MODMASTER v2  —  model: {self.engine.model}\n"
            f"System prompt loaded ({len(self.system_prompt):,} chars). "
            "Type /help for commands.")

    def _check_api_key(self):
        if not os.environ.get("GROQ_API_KEY"):
            self._show_api_key_dialog()

    def _show_api_key_dialog(self):
        import tkinter as tk
        from tkinter import messagebox
        dlg = tk.Toplevel(self.root)
        dlg.title("API Key Required")
        dlg.configure(bg=BG)
        dlg.resizable(False, False)
        dlg.grab_set()

        tk.Label(dlg, text="GROQ_API_KEY not set.\nEnter your key to continue:",
                 bg=BG, fg=FG, font=FONT_UI, pady=10).pack(padx=20)

        entry = tk.Entry(dlg, show="*", width=50, bg=INPUT_BG, fg=FG,
                         insertbackground=FG, relief="flat",
                         font=FONT_MONO, bd=6)
        entry.pack(padx=20, pady=4)

        def confirm():
            key = entry.get().strip()
            if key:
                os.environ["GROQ_API_KEY"] = key
                dlg.destroy()
            else:
                messagebox.showerror("Error", "Key cannot be empty.", parent=dlg)

        btn = tk.Button(dlg, text="Set Key", command=confirm,
                        bg=CYAN, fg=BG, font=FONT_UI,
                        relief="flat", padx=12, pady=4, cursor="hand2")
        btn.pack(pady=10)
        entry.bind("<Return>", lambda _: confirm())

    def _build_menu(self):
        import tkinter as tk
        menu = tk.Menu(self.root, bg=BG2, fg=FG, activebackground=BORDER,
                       activeforeground=FG, relief="flat", tearoff=False)
        self.root.config(menu=menu)

        session = tk.Menu(menu, bg=BG2, fg=FG, activebackground=BORDER,
                          activeforeground=FG, tearoff=False)
        menu.add_cascade(label="Session", menu=session)
        session.add_command(label="Clear history",   command=self.cmd_clear)
        session.add_command(label="Show history",    command=self.cmd_history)
        session.add_command(label="Token usage",     command=self.cmd_tokens)
        session.add_separator()
        session.add_command(label="Exit",            command=self.root.quit)

        cfg = tk.Menu(menu, bg=BG2, fg=FG, activebackground=BORDER,
                      activeforeground=FG, tearoff=False)
        menu.add_cascade(label="Config", menu=cfg)
        cfg.add_command(label="Change model…",       command=self.cmd_model_dialog)
        cfg.add_command(label="Attach file…",        command=self._on_attach)
        cfg.add_command(label="Load instructions…",  command=self.cmd_load_instructions)
        cfg.add_command(label="Show system prompt",  command=self.cmd_system)
        cfg.add_command(label="Set API key…",        command=self._show_api_key_dialog)

        menu.add_command(label="Help", command=self.cmd_help)

    def _build_layout(self):
        import tkinter as tk
        from tkinter import scrolledtext

        self.status_var = tk.StringVar(value=f"  Model: {self.engine.model}  |  Tokens: 0")
        status = tk.Label(self.root, textvariable=self.status_var,
                          bg=BG2, fg=DIM, font=FONT_UI, anchor="w",
                          relief="flat", bd=0)
        status.pack(side="top", fill="x")
        tk.Frame(self.root, bg=BORDER, height=1).pack(fill="x")

        chat_frame = tk.Frame(self.root, bg=BG)
        chat_frame.pack(fill="both", expand=True)

        self.chat = scrolledtext.ScrolledText(
            chat_frame, state="disabled", wrap="word",
            bg=BG, fg=FG, insertbackground=FG,
            font=FONT_MONO, bd=0, relief="flat",
            padx=14, pady=10,
            selectbackground=BORDER, selectforeground=FG,
        )
        self.chat.pack(fill="both", expand=True)

        self.chat.tag_config("system",    foreground=DIM)
        self.chat.tag_config("user_name", foreground=GREEN,
                             font=(*FONT_MONO[:1], FONT_MONO[1], "bold"))
        self.chat.tag_config("user_msg",  foreground=FG)
        self.chat.tag_config("bot_name",  foreground=CYAN,
                             font=(*FONT_MONO[:1], FONT_MONO[1], "bold"))
        self.chat.tag_config("bot_msg",   foreground=FG)
        self.chat.tag_config("tool",      foreground=YELLOW)
        self.chat.tag_config("error",     foreground=RED)
        self.chat.tag_config("dim",       foreground=DIM)

        tk.Frame(self.root, bg=BORDER, height=1).pack(fill="x")

        input_frame = tk.Frame(self.root, bg=BG2, pady=8)
        input_frame.pack(fill="x")

        self.input_var = tk.StringVar()
        self.input_box = tk.Entry(
            input_frame, textvariable=self.input_var,
            bg=INPUT_BG, fg=FG, insertbackground=FG,
            font=FONT_MONO, relief="flat", bd=8,
        )
        self.input_box.pack(side="left", fill="x", expand=True, padx=(12, 6))
        self.input_box.bind("<Return>",   self._on_enter)
        self.input_box.bind("<KP_Enter>", self._on_enter)
        self.input_box.focus_set()

        # ── attach file button ────────────────────────────────────────────
        self.attach_btn = tk.Button(
            input_frame, text="📎",
            command=self._on_attach,
            bg=BG2, fg=YELLOW,
            font=(*FONT_UI[:1], FONT_UI[1] + 2),
            relief="flat", padx=6, pady=6,
            cursor="hand2", activebackground=BORDER, activeforeground=YELLOW,
            bd=0,
        )
        self.attach_btn.pack(side="right", padx=(0, 4))

        # label that shows the attached filename (hidden when empty)
        self.attach_label_var = tk.StringVar(value="")
        self.attach_label = tk.Label(
            self.root, textvariable=self.attach_label_var,
            bg=BG, fg=YELLOW, font=(FONT_UI[0], FONT_UI[1] - 1), anchor="w",
        )
        # packed in _update_attach_label

        self.send_btn = tk.Button(
            input_frame, text="Send ▶",
            command=self._on_send,
            bg=CYAN, fg=BG,
            font=(*FONT_UI[:1], FONT_UI[1], "bold"),
            relief="flat", padx=14, pady=6,
            cursor="hand2", activebackground=GREEN, activeforeground=BG,
        )
        self.send_btn.pack(side="right", padx=(0, 12))

        self.spinner_var = tk.StringVar(value="")
        tk.Label(self.root, textvariable=self.spinner_var,
                 bg=BG, fg=YELLOW, font=FONT_UI).pack(pady=(0, 2))

        self.attach_label.pack(side="top", fill="x", padx=14, pady=(0, 4))

    def _append(self, kind: str, text: str):
        self.root.after(0, self._append_main, kind, text)

    def _append_main(self, kind: str, text: str):
        self.chat.config(state="normal")
        if kind == "user":
            self.chat.insert("end", "\nYou\n", "user_name")
            self.chat.insert("end", text + "\n", "user_msg")
        elif kind == "bot":
            self.chat.insert("end", "\nAgent\n", "bot_name")
            self.chat.insert("end", text + "\n", "bot_msg")
        elif kind == "tool":
            self.chat.insert("end", f"  ⚙ {text}\n", "tool")
        elif kind == "error":
            self.chat.insert("end", f"  ✖ {text}\n", "error")
        elif kind == "warn":
            self.chat.insert("end", f"  ⚠ {text}\n", "tool")
        else:
            self.chat.insert("end", f"{text}\n", "system")
        self.chat.config(state="disabled")
        self.chat.see("end")

    def _set_busy(self, busy: bool):
        self.busy = busy
        state = "disabled" if busy else "normal"
        self.send_btn.config(state=state)
        self.input_box.config(state=state)
        self.spinner_var.set("  ● thinking…" if busy else "")

    def _update_status(self):
        self.status_var.set(
            f"  Model: {self.engine.model}  |  Session tokens: ~{self.engine.session_tokens:,}"
        )

    # ── file attachment ───────────────────────────────────────────────────
    def _on_attach(self):
        path = self.fb.askopenfilename(
            title="Attach a file",
            filetypes=[
                ("Text / code", "*.txt *.md *.py *.js *.ts *.cs *.json *.yaml *.yml *.csv *.log *.xml *.html *.css"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return
        try:
            size = os.path.getsize(path)
            if size > 100_000:
                self.mb.showwarning(
                    "File too large",
                    f"File is {size//1024} KB. Maximum is 100 KB.",
                    parent=self.root,
                )
                return
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            self.attached_file = (os.path.basename(path), content)
            self._update_attach_label()
            self._append("system", f"📎 Attached: {os.path.basename(path)} ({len(content):,} chars) — will be sent with your next message.")
        except Exception as e:
            self._append("error", f"Could not read file: {e}")

    def _update_attach_label(self):
        if self.attached_file:
            name, content = self.attached_file
            self.attach_label_var.set(f"📎 {name}  ({len(content):,} chars)  [× click to remove]")
            self.attach_label.config(cursor="hand2")
            self.attach_label.bind("<Button-1>", self._clear_attachment)
        else:
            self.attach_label_var.set("")
            self.attach_label.config(cursor="")
            self.attach_label.unbind("<Button-1>")

    def _clear_attachment(self, event=None):
        self.attached_file = None
        self._update_attach_label()
        self._append("system", "Attachment removed.")

    def _on_enter(self, event=None):
        if not self.busy:
            self._on_send()

    def _on_send(self):
        text = self.input_var.get().strip()
        if not text or self.busy:
            return
        self.input_var.set("")

        # inject attachment if present
        if self.attached_file:
            fname, fcontent = self.attached_file
            text = (
                f"[Attached file: {fname}]\n"
                f"```\n{fcontent}\n```\n\n"
                f"{text}"
            )
            self.attached_file = None
            self._update_attach_label()

        self._handle_input(text)

    def _handle_input(self, text: str):
        if text.startswith("/"):
            cmd = text.split()[0].lower()
            if cmd == "/help":        self.cmd_help()
            elif cmd == "/clear":     self.cmd_clear()
            elif cmd == "/history":   self.cmd_history()
            elif cmd == "/tokens":    self.cmd_tokens()
            elif cmd == "/system":    self.cmd_system()
            elif cmd == "/model":
                parts = text.split(maxsplit=1)
                if len(parts) < 2:
                    self._append("system", f"Current model: {self.engine.model}")
                else:
                    self.engine.model = parts[1].strip()
                    self._append("system", f"Switched to model: {self.engine.model}")
                    self._update_status()
            else:
                self._append("warn", f"Unknown command: {cmd}. Type /help.")
            return

        self._append("user", text)
        self._set_busy(True)
        threading.Thread(target=self._run_chat, args=(text,), daemon=True).start()

    def _run_chat(self, user_input: str):
        self.engine.send(
            user_input,
            on_tool  = lambda n, r: self._append("tool",  f"{n} → {r[:120]}"),
            on_reply = lambda t:    self._append("bot",   t),
            on_warn  = lambda t:    self._append("warn",  t),
            on_error = lambda t:    self._append("error", t),
        )
        self.root.after(0, self._update_status)
        self.root.after(0, self._set_busy, False)

    def cmd_help(self):
        self._append("system", (
            "Commands:\n"
            "  /help          — show this help\n"
            "  /clear         — clear conversation history\n"
            "  /history       — show conversation history\n"
            "  /tokens        — show token usage\n"
            "  /model <name>  — switch model\n"
            "  /system        — show system prompt\n\n"
            "Menu → Config to change model, load instructions, or set API key."
        ))

    def cmd_clear(self):
        self.engine.history = [self.engine.history[0]]
        self._append("system", "History cleared.")

    def cmd_history(self):
        lines = []
        for i, m in enumerate(self.engine.history):
            role    = m["role"].upper()
            content = str(m.get("content", ""))[:200]
            lines.append(f"[{i}] {role}: {content}")
        self._append("system", "\n".join(lines) or "(empty)")

    def cmd_tokens(self):
        est = estimate_tokens(self.engine.history)
        self._append("system",
            f"Estimated tokens in context: ~{est:,}\n"
            f"Session total sent: ~{self.engine.session_tokens:,}")

    def cmd_system(self):
        preview = self.engine.history[0]["content"][:1000] + \
                  ("…" if len(self.engine.history[0]["content"]) > 1000 else "")
        self._append("system", f"── System Prompt ──\n{preview}")

    def cmd_model_dialog(self):
        import tkinter as tk
        from tkinter import ttk
        dlg = tk.Toplevel(self.root)
        dlg.title("Select Model")
        dlg.configure(bg=BG)
        dlg.resizable(False, False)
        dlg.grab_set()

        tk.Label(dlg, text="Choose a Groq model:", bg=BG, fg=FG,
                 font=FONT_UI, pady=8).pack(padx=16)

        # ── style the combobox ────────────────────────────────────────────
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Dark.TCombobox",
                        fieldbackground=INPUT_BG,
                        background=BG2,
                        foreground=FG,
                        selectbackground=BORDER,
                        selectforeground=FG,
                        arrowcolor=CYAN,
                        bordercolor=BORDER)
        style.map("Dark.TCombobox",
                  fieldbackground=[("readonly", INPUT_BG)],
                  foreground=[("readonly", FG)],
                  selectbackground=[("readonly", BORDER)],
                  selectforeground=[("readonly", FG)])

        var = tk.StringVar(value=self.engine.model)
        combo = ttk.Combobox(dlg, textvariable=var, values=GROQ_MODELS,
                             width=46, state="readonly", style="Dark.TCombobox",
                             font=FONT_MONO)
        combo.pack(padx=16, pady=4)
        # select the current model in the list if present
        if self.engine.model in GROQ_MODELS:
            combo.current(GROQ_MODELS.index(self.engine.model))

        # custom entry below the dropdown for unlisted models
        tk.Label(dlg, text="— or type a custom model string —",
                 bg=BG, fg=DIM, font=(FONT_UI[0], FONT_UI[1] - 1)).pack(pady=(6, 0))
        custom_var = tk.StringVar()
        custom_entry = tk.Entry(dlg, textvariable=custom_var, width=48,
                                bg=INPUT_BG, fg=FG, insertbackground=FG,
                                relief="flat", font=FONT_MONO, bd=6)
        custom_entry.pack(padx=16, pady=4)

        def confirm():
            m = custom_var.get().strip() or var.get().strip()
            if m:
                self.engine.model = m
                self._append("system", f"Switched to model: {self.engine.model}")
                self._update_status()
                dlg.destroy()

        tk.Button(dlg, text="Apply", command=confirm,
                  bg=CYAN, fg=BG, font=FONT_UI,
                  relief="flat", padx=12, pady=4, cursor="hand2"
                  ).pack(pady=10)
        custom_entry.bind("<Return>", lambda _: confirm())

    def cmd_load_instructions(self):
        path = self.fb.askopenfilename(
            title="Load instructions file",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read().strip()
            if not content:
                self.mb.showwarning("Empty file", "The file was empty.", parent=self.root)
                return
            self.engine.history = [{"role": "system", "content": content}]
            self._append("system",
                f"Loaded '{os.path.basename(path)}' ({len(content):,} chars). History cleared.")
        except Exception as e:
            self._append("error", f"Could not load file: {e}")


def run_gui():
    import tkinter as tk
    root = tk.Tk()
    root.geometry("860x620")
    try:
        root.iconbitmap("modmaster.ico")
    except Exception:
        pass
    ModmasterGUI(root)
    root.mainloop()


# ─── ENTRY POINT ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if "--pipe-mode" in sys.argv:
        run_pipe_mode()
    else:
        run_gui()
