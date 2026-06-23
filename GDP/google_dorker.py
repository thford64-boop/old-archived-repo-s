"""
Google Dorking GUI Tool
-----------------------
A full-featured Google dorking search tool with GUI.
Build with: pyinstaller --onefile --windowed google_dorker.py

Requirements:
  pip install requests beautifulsoup4 selenium webdriver-manager

HOW SEARCH WORKS:
  - "Selenium (Chrome)" mode opens a real Chrome browser, logs in as you,
    and scrapes results — Google cannot tell it apart from a human.
  - "Requests" mode is fast but Google will CAPTCHA-block it quickly.
  - "Open in Browser" always works — it just opens your default browser.
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import threading
import os
import time
import json
import webbrowser
import urllib.parse
import urllib.request
import re
import sys
from datetime import datetime
try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False

# ── Load .env if present ─────────────────────
def _load_env_file():
    """Load a .env file from the same directory as the script/exe."""
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(base, ".env")
    env_vars = {}
    if os.path.isfile(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                env_vars[key.strip()] = val.strip().strip('"').strip("'")
    return env_vars

_ENV = _load_env_file()
_GROQ_KEY_FROM_ENV = _ENV.get("GROQ_API_KEY", "")

# ── Optional deps ────────────────────────────
try:
    import requests
    from bs4 import BeautifulSoup
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options  import Options  as ChromeOptions
    from selenium.webdriver.chrome.service  import Service  as ChromeService
    from selenium.webdriver.firefox.options import Options  as FirefoxOptions
    from selenium.webdriver.firefox.service import Service  as FirefoxService
    from selenium.webdriver.edge.options    import Options  as EdgeOptions
    from selenium.webdriver.edge.service    import Service  as EdgeService
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

try:
    from webdriver_manager.chrome import ChromeDriverManager
    WDM_CHROME = True
except ImportError:
    WDM_CHROME = False

try:
    from webdriver_manager.firefox import GeckoDriverManager
    WDM_FIREFOX = True
except ImportError:
    WDM_FIREFOX = False

try:
    from webdriver_manager.microsoft import EdgeChromiumDriverManager
    WDM_EDGE = True
except ImportError:
    WDM_EDGE = False

WDM_AVAILABLE = WDM_CHROME or WDM_FIREFOX or WDM_EDGE

# ─────────────────────────────────────────────
#  DORK CATEGORIES & OPTIONS
# ─────────────────────────────────────────────

DORK_CATEGORIES = {
    "File Type (filetype:)": {
        "desc": "Search for specific file types",
        "operator": "filetype",
        "options": [
            "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx",
            "txt", "csv", "xml", "json", "sql", "db", "mdb",
            "log", "bak", "cfg", "conf", "ini", "env",
            "zip", "tar", "gz", "rar", "7z",
            "php", "asp", "aspx", "jsp", "py", "rb", "sh",
            "key", "pem", "ppk", "crt", "cer",
        ],
    },
    "Site Restrict (site:)": {
        "desc": "Limit search to a specific site or domain",
        "operator": "site",
        "options": [
            ".gov", ".edu", ".mil", ".org", ".net", ".com",
            ".co.uk", ".de", ".fr", ".ru", ".cn",
            "pastebin.com", "github.com", "gitlab.com",
            "trello.com", "jira.atlassian.com",
            "s3.amazonaws.com", "blob.core.windows.net",
        ],
    },
    "In URL (inurl:)": {
        "desc": "Find URLs containing specific text",
        "operator": "inurl",
        "options": [
            "admin", "login", "wp-admin", "dashboard",
            "panel", "cpanel", "phpmyadmin", "manager",
            "config", "setup", "install", "backup",
            "upload", "files", "shell", "cmd",
            "passwd", "password", "secret", "token",
            "api", "swagger", "graphql", "debug",
            "test", "dev", "staging", "beta",
            "reset", "forgot", "register", "signup",
        ],
    },
    "In Title (intitle:)": {
        "desc": "Search page titles",
        "operator": "intitle",
        "options": [
            "index of", "parent directory", "admin",
            "login", "dashboard", "control panel",
            "error", "warning", "exception", "debug",
            "welcome to nginx", "apache2 ubuntu default",
            "phpinfo()", "test page",
            "webcam", "camera", "live view",
            "router", "firewall", "network",
        ],
    },
    "In Text (intext:)": {
        "desc": "Search within page body text",
        "operator": "intext",
        "options": [
            "username password", "login credentials",
            "api_key", "api key", "secret_key",
            "access_token", "authorization token",
            "connectionstring", "database password",
            "smtp password", "ftp password",
            "private key", "-----BEGIN RSA",
            "aws_access_key", "aws_secret_key",
            "index of /etc", "index of /var",
        ],
    },
    "Cache (cache:)": {"desc": "View Google's cached version of a page",
                        "operator": "cache", "options": []},
    "Link (link:)": {"desc": "Find pages linking to a URL",
                     "operator": "link", "options": []},
    "Related (related:)": {"desc": "Find sites related to a URL",
                            "operator": "related", "options": []},
    "Anchor Text (allinanchor:)": {
        "desc": "Search anchor text of links",
        "operator": "allinanchor",
        "options": ["click here", "login", "admin", "download",
                    "free", "crack", "keygen", "serial"],
    },
    "Date After (after:)": {
        "desc": "Results published after this date (YYYY-MM-DD)",
        "operator": "after",
        "options": ["2024-01-01", "2023-01-01", "2022-01-01",
                    "2021-01-01", "2020-01-01"],
    },
    "Date Before (before:)": {
        "desc": "Results published before this date (YYYY-MM-DD)",
        "operator": "before",
        "options": ["2025-01-01", "2024-01-01", "2023-01-01"],
    },
    "Numeric Range (numrange:)": {
        "desc": "Search within a numeric range (e.g. 1..100)",
        "operator": "numrange",
        "options": ["1..100", "100..1000", "1000..9999",
                    "80..8080", "3000..9000"],
    },
    "Ext Variations (ext:)": {
        "desc": "Alternative to filetype: for some engines",
        "operator": "ext",
        "options": ["php", "asp", "aspx", "cgi", "cfm",
                    "env", "bak", "old", "orig", "swp", "git", "svn"],
    },
    "All In URL (allinurl:)": {
        "desc": "All terms must be in URL",
        "operator": "allinurl",
        "options": ["admin login", "wp-admin wp-login",
                    "phpmyadmin index", "config backup",
                    "upload shell", "etc passwd"],
    },
    "All In Title (allintitle:)": {
        "desc": "All terms must be in page title",
        "operator": "allintitle",
        "options": ["index of backup", "index of password",
                    "index of secret", "admin login panel",
                    "error stack trace", "sql syntax error"],
    },
    "All In Text (allintext:)": {
        "desc": "All terms must be in page body",
        "operator": "allintext",
        "options": ["username password email", "api key secret",
                    "private key certificate", "ssn social security"],
    },
    "Define (define:)": {"desc": "Get definitions",
                          "operator": "define", "options": []},
    "Info (info:)": {"desc": "Get info about a URL",
                     "operator": "info", "options": []},
    "Stocks (stocks:)": {"desc": "Get stock info", "operator": "stocks",
                          "options": ["AAPL", "GOOG", "MSFT", "AMZN", "META"]},
    "Map (map:)": {"desc": "Show a map", "operator": "map", "options": []},
    "Movie (movie:)": {"desc": "Search movie information",
                       "operator": "movie", "options": []},
    "Weather (weather:)": {"desc": "Get weather info",
                            "operator": "weather", "options": []},
}

DORK_TEMPLATES = {
    "🔑 Exposed Passwords":      'intext:"password" intext:"username" filetype:txt',
    "🔑 DB Credentials":         'intext:"DB_PASSWORD" OR intext:"database_password" filetype:env',
    "📁 Open Directories":       'intitle:"index of" "parent directory"',
    "🔐 SSH Keys":               'filetype:pem intext:"PRIVATE KEY"',
    "🔐 AWS Keys":               'intext:"aws_access_key_id" intext:"aws_secret_access_key"',
    "📋 Config Files":           'filetype:cfg OR filetype:conf intext:"password"',
    "💾 SQL Dumps":              'filetype:sql intext:"INSERT INTO" intext:"password"',
    "🌐 Admin Panels":           'inurl:admin intitle:"admin panel" OR intitle:"login"',
    "📷 Exposed Cameras":        'inurl:"/view/index.shtml" OR intitle:"live view"',
    "📱 API Keys":               'intext:"api_key" OR intext:"apikey" filetype:json',
    "🏥 Medical Records":        'filetype:xls intext:"patient" site:.gov OR site:.org',
    "💳 Credit Cards":           'intext:"card number" intext:"expiration" filetype:xls',
    "🗃️ Backup Files":           'filetype:bak OR filetype:old OR filetype:backup inurl:backup',
    "📧 Email Lists":            'filetype:xls OR filetype:csv intext:"email" intext:"phone"',
    "🖥️ phpMyAdmin":             'inurl:phpmyadmin intitle:"phpMyAdmin"',
    "🐞 Error Pages":            'intitle:"error" intext:"sql syntax" OR intext:"mysql"',
    "🔓 Login Pages":            'inurl:login OR inurl:signin intitle:"login"',
    "📄 PDF Reports":            'filetype:pdf intitle:"confidential" OR intitle:"internal"',
    "🗝️ .env Files":             'filetype:env intext:"DB_" OR intext:"SECRET"',
    "🔧 Debug Pages":            'inurl:debug OR inurl:test intitle:"debug" OR intitle:"phpinfo"',
    "📡 FTP Servers":            'intitle:"index of" inurl:ftp',
    "🗄️ Database Files":         'filetype:sql OR filetype:db OR filetype:mdb',
    "🔒 SSL Private Keys":       'filetype:key OR filetype:ppk intext:"PRIVATE"',
    "📞 Phone Numbers":          'filetype:xls OR filetype:csv intext:"phone" intext:"address"',
    "🌍 Subdomains Exposed":     'site:*.target.com -www',
    "☁️ S3 Buckets":             'site:s3.amazonaws.com intext:"Access Denied"',
    "🐙 GitHub Secrets":         'site:github.com intext:"password" OR intext:"secret"',
    "📰 Pastebin Leaks":         'site:pastebin.com intext:"password" OR intext:"apikey"',
    "🏢 Corp Documents":         'filetype:pdf OR filetype:docx intitle:"confidential" site:.com',
    "🔍 Shodan-style IoT":       'intitle:"router" OR intitle:"modem" inurl:setup.cgi',
}

SEARCH_ENGINES = {
    "Google":      "https://www.google.com/search?q={query}&num={num}",
    "Bing":        "https://www.bing.com/search?q={query}&count={num}",
    "DuckDuckGo":  "https://duckduckgo.com/?q={query}",
    "Yahoo":       "https://search.yahoo.com/search?p={query}&n={num}",
    "Brave":       "https://search.brave.com/search?q={query}&count={num}",
    "Startpage":   "https://www.startpage.com/sp/search?q={query}",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.google.com/",
}

# ─────────────────────────────────────────────
#  MAIN APPLICATION
# ─────────────────────────────────────────────

class GoogleDorkerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("🔍 Google Dorker Pro")
        self.root.geometry("1280x820")
        self.root.minsize(900, 600)
        self.root.configure(bg="#0d1117")

        self.results       = []
        self.search_thread = None
        self.stop_flag     = False
        self.driver        = None
        self.download_dir  = os.path.expanduser("~/Downloads/DorkResults")
        self.groq_key_var  = tk.StringVar(value=_GROQ_KEY_FROM_ENV)

        self._setup_styles()
        self._build_ui()
        self._check_deps()

    # ── STYLES ──────────────────────────────
    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        BG, CARD, FG, MUTED, BLUE = "#0d1117","#161b22","#c9d1d9","#8b949e","#58a6ff"
        RED = "#da3633"

        style.configure("TFrame",           background=BG)
        style.configure("Card.TFrame",      background=CARD, relief="flat")
        style.configure("TLabel",           background=BG, foreground=FG,
                        font=("Consolas", 10))
        style.configure("TButton",          background="#21262d", foreground=FG,
                        font=("Consolas", 10), relief="flat", borderwidth=0)
        style.map("TButton",
                  background=[("active","#30363d"),("pressed","#161b22")])
        style.configure("Accent.TButton",   background="#1f6feb", foreground="white",
                        font=("Consolas", 10, "bold"), relief="flat")
        style.map("Accent.TButton",
                  background=[("active","#388bfd"),("pressed","#1158c7")])
        style.configure("Danger.TButton",   background=RED, foreground="white",
                        font=("Consolas", 10), relief="flat")
        style.map("Danger.TButton",
                  background=[("active","#f85149"),("pressed","#b22a27")])
        style.configure("TEntry",           fieldbackground="#21262d", foreground=FG,
                        insertcolor=FG, font=("Consolas", 11))
        style.configure("TCombobox",        fieldbackground="#21262d", foreground=FG,
                        selectbackground="#21262d", font=("Consolas", 10))
        style.configure("TCheckbutton",     background=BG, foreground=FG,
                        font=("Consolas", 10))
        style.configure("TNotebook",        background=BG, tabmargins=[2,5,2,0])
        style.configure("TNotebook.Tab",    background="#21262d", foreground=MUTED,
                        font=("Consolas", 10), padding=[12,6])
        style.map("TNotebook.Tab",
                  background=[("selected",CARD)],
                  foreground=[("selected",BLUE)])
        style.configure("Treeview",         background=CARD, foreground=FG,
                        fieldbackground=CARD, font=("Consolas", 10), rowheight=28)
        style.configure("Treeview.Heading", background="#21262d", foreground=BLUE,
                        font=("Consolas", 10, "bold"), relief="flat")
        style.map("Treeview",               background=[("selected","#1f6feb")])
        style.configure("TScrollbar",       background="#21262d",
                        troughcolor=BG, arrowcolor=MUTED, bordercolor=BG)
        style.configure("TProgressbar",     background=BLUE,
                        troughcolor="#21262d", thickness=6)

    # ── UI BUILD ────────────────────────────
    def _build_ui(self):
        topbar = tk.Frame(self.root, bg="#161b22", height=50)
        topbar.pack(fill="x")
        topbar.pack_propagate(False)
        tk.Label(topbar, text="🔍  GOOGLE DORKER PRO",
                 bg="#161b22", fg="#58a6ff",
                 font=("Consolas", 15, "bold")).pack(side="left", padx=20, pady=10)
        tk.Label(topbar, text="⚠  For authorized security research only",
                 bg="#161b22", fg="#f0883e",
                 font=("Consolas", 9)).pack(side="right", padx=20, pady=10)

        paned = ttk.PanedWindow(self.root, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=8, pady=8)
        left  = ttk.Frame(paned, style="Card.TFrame")
        right = ttk.Frame(paned, style="Card.TFrame")
        paned.add(left,  weight=1)
        paned.add(right, weight=2)
        self._build_left(left)
        self._build_right(right)
        self._build_statusbar()

    def _lbl(self, parent, text):
        tk.Label(parent, text=text, bg="#0d1117",
                 fg="#8b949e", font=("Consolas", 9)).pack(anchor="w")

    def _build_left(self, parent):
        nb = ttk.Notebook(parent)
        nb.pack(fill="both", expand=True, padx=4, pady=4)
        b = ttk.Frame(nb); nb.add(b, text="⚙ Query Builder")
        t = ttk.Frame(nb); nb.add(t, text="📋 Templates")
        s = ttk.Frame(nb); nb.add(s, text="🛠 Settings")
        self._build_query_builder(b)
        self._build_templates(t)
        self._build_settings(s)

    def _build_query_builder(self, parent):
        f = ttk.Frame(parent)
        f.pack(fill="both", expand=True, padx=8, pady=8)

        self._lbl(f, "Base Query / Keywords:")
        self.base_query_var = tk.StringVar()
        ttk.Entry(f, textvariable=self.base_query_var,
                  font=("Consolas", 11)).pack(fill="x", pady=(2,10))

        self._lbl(f, "Dork Operator:")
        self.category_var = tk.StringVar()
        cat_combo = ttk.Combobox(f, textvariable=self.category_var,
                                  values=list(DORK_CATEGORIES.keys()),
                                  state="readonly", font=("Consolas", 10))
        cat_combo.pack(fill="x", pady=(2,4))
        cat_combo.bind("<<ComboboxSelected>>", self._on_category_change)

        self.cat_desc_lbl = tk.Label(f, text="", bg="#0d1117", fg="#3fb950",
                                      font=("Consolas", 9), wraplength=280, justify="left")
        self.cat_desc_lbl.pack(anchor="w", pady=(0,6))

        self._lbl(f, "Operator Value / Custom:")
        self.op_value_var = tk.StringVar()
        self.op_combo = ttk.Combobox(f, textvariable=self.op_value_var,
                                      font=("Consolas", 10))
        self.op_combo.pack(fill="x", pady=(2,4))

        self._lbl(f, "Add More Operators:")
        add_ops_frame = tk.Frame(f, bg="#0d1117")
        add_ops_frame.pack(fill="x")

        self.extra_ops = {}
        quick_ops = [
            ("site:","site_val"),     ("inurl:","inurl_val"),
            ("intitle:","intitle_val"),("filetype:","filetype_val"),
            ("intext:","intext_val"),  ("after:","after_val"),
            ("before:","before_val"), ("ext:","ext_val"),
        ]
        for i,(label,key) in enumerate(quick_ops):
            row=i//2; col=i%2
            cell=tk.Frame(add_ops_frame,bg="#0d1117")
            cell.grid(row=row,column=col,sticky="ew",padx=2,pady=2)
            add_ops_frame.columnconfigure(col,weight=1)
            tk.Label(cell,text=label,bg="#0d1117",fg="#8b949e",
                     font=("Consolas",8)).pack(anchor="w")
            var=tk.StringVar()
            self.extra_ops[key]=var
            ttk.Entry(cell,textvariable=var,font=("Consolas",9)).pack(fill="x")

        self._lbl(f, "Exclude (- prefix, space sep):")
        self.exclude_var = tk.StringVar()
        ttk.Entry(f, textvariable=self.exclude_var,
                  font=("Consolas", 10)).pack(fill="x")

        self.exact_var = tk.BooleanVar()
        ttk.Checkbutton(f, text='Wrap base query in "exact phrase" quotes',
                        variable=self.exact_var).pack(anchor="w", pady=4)
        self.or_var = tk.BooleanVar()
        ttk.Checkbutton(f, text="Use OR between operator values",
                        variable=self.or_var).pack(anchor="w")

        self._lbl(f, "Generated Query:")
        preview_frame = tk.Frame(f, bg="#21262d", relief="flat", bd=1)
        preview_frame.pack(fill="x")
        self.query_preview = tk.Label(preview_frame, text="", bg="#21262d",
                                       fg="#58a6ff", font=("Consolas", 10),
                                       wraplength=300, justify="left",
                                       anchor="w", padx=6, pady=6)
        self.query_preview.pack(fill="x")

        for var in [self.base_query_var, self.op_value_var, self.exclude_var,
                    *self.extra_ops.values()]:
            var.trace_add("write", lambda *a: self._update_preview())
        self.exact_var.trace_add("write", lambda *a: self._update_preview())
        self.or_var.trace_add("write", lambda *a: self._update_preview())

        btn_row = tk.Frame(f, bg="#0d1117")
        btn_row.pack(fill="x", pady=(12,0))
        ttk.Button(btn_row, text="📋 Copy Query",
                   command=self._copy_query).pack(side="left", padx=(0,4))
        ttk.Button(btn_row, text="🌐 Open in Browser",
                   command=self._open_browser).pack(side="left", padx=(0,4))
        ttk.Button(btn_row, text="✨ AI Generate",
                   style="Accent.TButton",
                   command=self._ai_generate_dork).pack(side="left")

        # ── AI prompt input ─────────────────────────────
        tk.Label(f, text="AI Prompt (describe what you want to find):",
                 bg="#0d1117", fg="#8b949e",
                 font=("Consolas", 9)).pack(anchor="w", pady=(10,0))
        self.ai_prompt_var = tk.StringVar()
        ai_row = tk.Frame(f, bg="#0d1117")
        ai_row.pack(fill="x", pady=(2,0))
        ttk.Entry(ai_row, textvariable=self.ai_prompt_var,
                  font=("Consolas", 10)).pack(side="left", fill="x", expand=True, padx=(0,4))
        self.ai_status_lbl = tk.Label(ai_row, text="", bg="#0d1117",
                                       fg="#3fb950", font=("Consolas", 9))
        self.ai_status_lbl.pack(side="left")

    def _build_templates(self, parent):
        f = ttk.Frame(parent)
        f.pack(fill="both", expand=True, padx=8, pady=8)
        tk.Label(f, text="Click a template to load it:", bg="#0d1117",
                 fg="#8b949e", font=("Consolas", 9)).pack(anchor="w", pady=(0,6))

        canvas = tk.Canvas(f, bg="#0d1117", highlightthickness=0)
        scroll = ttk.Scrollbar(f, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        inner = tk.Frame(canvas, bg="#0d1117")
        canvas.create_window((0,0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(
            scrollregion=canvas.bbox("all")))

        for name, query in DORK_TEMPLATES.items():
            row = tk.Frame(inner, bg="#161b22", relief="flat", bd=1)
            row.pack(fill="x", pady=2, padx=2)
            tk.Label(row, text=name, bg="#161b22", fg="#c9d1d9",
                     font=("Consolas", 10, "bold"), anchor="w").pack(
                side="left", padx=8, pady=4, fill="x", expand=True)
            ttk.Button(row, text="Load",
                       command=lambda q=query: self._load_template(q)).pack(
                side="right", padx=4, pady=4)

        canvas.bind_all("<MouseWheel>",
                        lambda e: canvas.yview_scroll(int(-1*(e.delta/120)),"units"))

    def _build_settings(self, parent):
        f = ttk.Frame(parent)
        f.pack(fill="both", expand=True, padx=12, pady=12)

        # ── BROWSER PICKER (pill buttons) ──────────────────
        tk.Label(f, text="BROWSER", bg="#0d1117", fg="#8b949e",
                 font=("Consolas", 8, "bold")).pack(anchor="w", pady=(0,4))

        self.browser_var = tk.StringVar(value="Auto-detect")
        browser_grid = tk.Frame(f, bg="#0d1117")
        browser_grid.pack(fill="x", pady=(0,10))

        browsers = [
            ("🌀 Auto",    "Auto-detect"),
            ("🟠 Firefox", "Firefox"),
            ("🔵 Chrome",  "Chrome"),
            ("🌊 Edge",    "Edge"),
            ("🦊 Zen",     "Zen"),
        ]
        self._browser_btns = {}
        for i, (label, val) in enumerate(browsers):
            col = i % 3
            row = i // 3
            btn = tk.Button(
                browser_grid, text=label, font=("Consolas", 9, "bold"),
                bg="#21262d", fg="#c9d1d9", relief="flat", bd=0,
                padx=6, pady=5, cursor="hand2",
                command=lambda v=val: self._pick_browser(v)
            )
            btn.grid(row=row, column=col, padx=3, pady=3, sticky="ew")
            browser_grid.columnconfigure(col, weight=1)
            self._browser_btns[val] = btn
        self._pick_browser("Auto-detect")  # set initial highlight

        # ── MODE (pill buttons) ────────────────────────────
        tk.Label(f, text="MODE", bg="#0d1117", fg="#8b949e",
                 font=("Consolas", 8, "bold")).pack(anchor="w", pady=(0,4))

        self.mode_var = tk.StringVar(value="Selenium (Chrome)")
        mode_frame = tk.Frame(f, bg="#0d1117")
        mode_frame.pack(fill="x", pady=(0,4))

        modes = [
            ("🖥 Visible",  "Selenium (Chrome)"),
            ("👻 Headless", "Selenium (Chrome Headless)"),
            ("⚡ Requests", "Requests (may get CAPTCHAed)"),
            ("🌐 Browser",  "Browser Only"),
        ]
        self._mode_btns = {}
        for i, (label, val) in enumerate(modes):
            col = i % 2
            row = i // 2
            btn = tk.Button(
                mode_frame, text=label, font=("Consolas", 9, "bold"),
                bg="#21262d", fg="#c9d1d9", relief="flat", bd=0,
                padx=6, pady=5, cursor="hand2",
                command=lambda v=val: self._pick_mode(v)
            )
            btn.grid(row=row, column=col, padx=3, pady=3, sticky="ew")
            mode_frame.columnconfigure(col, weight=1)
            self._mode_btns[val] = btn

        self.mode_help = tk.Label(f, text="", bg="#0d1117", fg="#3fb950",
                                   font=("Consolas", 8), wraplength=280, justify="left")
        self.mode_help.pack(anchor="w", pady=(0,6))
        self._pick_mode("Selenium (Chrome)")

        self.keep_driver_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(f, text="Keep browser open between searches",
                        variable=self.keep_driver_var).pack(anchor="w", pady=(0,10))

        # ── SEARCH ENGINE (pill row) ───────────────────────
        tk.Label(f, text="SEARCH ENGINE", bg="#0d1117", fg="#8b949e",
                 font=("Consolas", 8, "bold")).pack(anchor="w", pady=(0,4))

        self.engine_var = tk.StringVar(value="Google")
        eng_frame = tk.Frame(f, bg="#0d1117")
        eng_frame.pack(fill="x", pady=(0,10))
        self._engine_btns = {}
        for i, eng in enumerate(SEARCH_ENGINES.keys()):
            col = i % 3
            row = i // 3
            btn = tk.Button(
                eng_frame, text=eng, font=("Consolas", 9),
                bg="#21262d", fg="#c9d1d9", relief="flat", bd=0,
                padx=4, pady=4, cursor="hand2",
                command=lambda v=eng: self._pick_engine(v)
            )
            btn.grid(row=row, column=col, padx=2, pady=2, sticky="ew")
            eng_frame.columnconfigure(col, weight=1)
            self._engine_btns[eng] = btn
        self._pick_engine("Google")

        # ── RESULTS COUNT ──────────────────────────────────
        tk.Label(f, text="RESULTS PER PAGE", bg="#0d1117", fg="#8b949e",
                 font=("Consolas", 8, "bold")).pack(anchor="w", pady=(0,4))

        self.num_results_var = tk.IntVar(value=20)
        num_frame = tk.Frame(f, bg="#0d1117")
        num_frame.pack(fill="x", pady=(0,10))
        self._num_btns = {}
        for i, n in enumerate([10, 20, 50, 100]):
            btn = tk.Button(
                num_frame, text=str(n), font=("Consolas", 10, "bold"),
                bg="#21262d", fg="#c9d1d9", relief="flat", bd=0,
                padx=8, pady=5, cursor="hand2",
                command=lambda v=n: self._pick_num(v)
            )
            btn.grid(row=0, column=i, padx=2, pady=2, sticky="ew")
            num_frame.columnconfigure(i, weight=1)
            self._num_btns[n] = btn
        self._pick_num(20)

        # ── DELAY ─────────────────────────────────────────
        tk.Label(f, text="DELAY (SEC)", bg="#0d1117", fg="#8b949e",
                 font=("Consolas", 8, "bold")).pack(anchor="w", pady=(0,4))

        self.delay_var = tk.DoubleVar(value=2.0)
        delay_frame = tk.Frame(f, bg="#0d1117")
        delay_frame.pack(fill="x", pady=(0,10))
        self._delay_btns = {}
        for i, d in enumerate([0.5, 1.0, 2.0, 3.0, 5.0]):
            btn = tk.Button(
                delay_frame, text=str(d), font=("Consolas", 10),
                bg="#21262d", fg="#c9d1d9", relief="flat", bd=0,
                padx=6, pady=5, cursor="hand2",
                command=lambda v=d: self._pick_delay(v)
            )
            btn.grid(row=0, column=i, padx=2, pady=2, sticky="ew")
            delay_frame.columnconfigure(i, weight=1)
            self._delay_btns[d] = btn
        self._pick_delay(2.0)

        # ── SAVE FORMAT ────────────────────────────────────
        tk.Label(f, text="SAVE FORMAT", bg="#0d1117", fg="#8b949e",
                 font=("Consolas", 8, "bold")).pack(anchor="w", pady=(0,4))

        self.save_format_var = tk.StringVar(value="TXT")
        fmt_frame = tk.Frame(f, bg="#0d1117")
        fmt_frame.pack(fill="x", pady=(0,10))
        self._fmt_btns = {}
        for i, fmt in enumerate(["TXT", "JSON", "CSV"]):
            btn = tk.Button(
                fmt_frame, text=fmt, font=("Consolas", 10, "bold"),
                bg="#21262d", fg="#c9d1d9", relief="flat", bd=0,
                padx=8, pady=5, cursor="hand2",
                command=lambda v=fmt: self._pick_fmt(v)
            )
            btn.grid(row=0, column=i, padx=2, pady=2, sticky="ew")
            fmt_frame.columnconfigure(i, weight=1)
            self._fmt_btns[fmt] = btn
        self._pick_fmt("TXT")

        # ── DOWNLOAD FOLDER ────────────────────────────────
        tk.Label(f, text="DOWNLOAD FOLDER", bg="#0d1117", fg="#8b949e",
                 font=("Consolas", 8, "bold")).pack(anchor="w", pady=(0,4))
        dir_row = tk.Frame(f, bg="#0d1117")
        dir_row.pack(fill="x", pady=(0,10))
        self.dir_var = tk.StringVar(value=self.download_dir)
        ttk.Entry(dir_row, textvariable=self.dir_var,
                  font=("Consolas", 9)).pack(side="left", fill="x", expand=True)
        ttk.Button(dir_row, text="Browse",
                   command=self._browse_dir).pack(side="right", padx=(4,0))

        self.skip_pdf_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(f, text="Skip PDF results in tree",
                        variable=self.skip_pdf_var).pack(anchor="w", pady=2)

        ttk.Button(f, text="📁 Open Download Folder",
                   command=self._open_download_folder).pack(fill="x", pady=(10,0))
        ttk.Button(f, text="🔴 Close Browser Driver",
                   style="Danger.TButton",
                   command=self._close_driver).pack(fill="x", pady=(6,0))

        # ── GROQ SETTINGS ──────────────────────────────────
        tk.Label(f, text="GROQ API KEY", bg="#0d1117", fg="#8b949e",
                 font=("Consolas", 8, "bold")).pack(anchor="w", pady=(14,4))

        key_row = tk.Frame(f, bg="#0d1117")
        key_row.pack(fill="x", pady=(0,4))
        self.groq_key_entry = ttk.Entry(key_row, textvariable=self.groq_key_var,
                                         font=("Consolas", 9), show="*")
        self.groq_key_entry.pack(side="left", fill="x", expand=True, padx=(0,4))
        self._groq_show = tk.BooleanVar(value=False)
        def _toggle_show():
            self.groq_key_entry.configure(show="" if self._groq_show.get() else "*")
        ttk.Checkbutton(key_row, text="Show", variable=self._groq_show,
                        command=_toggle_show).pack(side="left")

        tk.Label(f, text="GROQ MODEL", bg="#0d1117", fg="#8b949e",
                 font=("Consolas", 8, "bold")).pack(anchor="w", pady=(6,4))
        self.groq_model_var = tk.StringVar(value="llama-3.3-70b-versatile")
        groq_models = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant",
                       "openai/gpt-oss-120b", "qwen/qwen3-32b",
                       "meta-llama/llama-4-scout-17b-16e-instruct"]
        ttk.Combobox(f, textvariable=self.groq_model_var,
                     values=groq_models, state="readonly",
                     font=("Consolas", 9)).pack(fill="x", pady=(0,4))

        groq_status = "✅ groq installed" if GROQ_AVAILABLE else "❌ pip install groq"
        key_hint = "  (loaded from .env)" if _GROQ_KEY_FROM_ENV else "  (enter key above or add to .env)"
        tk.Label(f, text=groq_status + key_hint, bg="#0d1117",
                 fg="#3fb950" if GROQ_AVAILABLE else "#f85149",
                 font=("Consolas", 8)).pack(anchor="w")
        ttk.Button(f, text="💾 Save Key to .env",
                   command=self._save_key_to_env).pack(fill="x", pady=(6,0))

    # ── PILL BUTTON HELPERS ─────────────────────────────
    def _pill_select(self, btn_dict, value, active_bg="#1f6feb", active_fg="white"):
        for v, b in btn_dict.items():
            if v == value:
                b.configure(bg=active_bg, fg=active_fg)
            else:
                b.configure(bg="#21262d", fg="#c9d1d9")

    def _pick_browser(self, val):
        self.browser_var.set(val)
        self._pill_select(self._browser_btns, val, "#0d419d", "#79c0ff")

    def _pick_mode(self, val):
        self.mode_var.set(val)
        self._pill_select(self._mode_btns, val)
        self._on_mode_change()

    def _pick_engine(self, val):
        self.engine_var.set(val)
        self._pill_select(self._engine_btns, val, "#1a7f37", "#56d364")

    def _pick_num(self, val):
        self.num_results_var.set(val)
        self._pill_select(self._num_btns, val, "#6e40c9", "#d2a8ff")

    def _pick_delay(self, val):
        self.delay_var.set(val)
        self._pill_select(self._delay_btns, val, "#b08800", "#f0c040")

    def _pick_fmt(self, val):
        self.save_format_var.set(val)
        self._pill_select(self._fmt_btns, val, "#842029", "#f85149")

    def _on_mode_change(self, *_):
        m = self.mode_var.get()
        msgs = {
            "Selenium (Chrome)":
                "✅ Opens real browser. Google sees a human. Best results.",
            "Selenium (Chrome Headless)":
                "✅ Browser runs invisibly. May occasionally be detected.",
            "Requests (may get CAPTCHAed)":
                "⚠ Fast but Google often blocks this. Use for Bing/DDG.",
            "Browser Only":
                "ℹ Opens your default browser. No scraping performed.",
        }
        self.mode_help.configure(text=msgs.get(m, ""))

    def _build_right(self, parent):
        search_row = tk.Frame(parent, bg="#161b22")
        search_row.pack(fill="x", padx=8, pady=8)
        tk.Label(search_row, text="Query:", bg="#161b22",
                 fg="#8b949e", font=("Consolas", 10)).pack(side="left", padx=(0,6))
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(search_row, textvariable=self.search_var,
                                       font=("Consolas", 12))
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(0,8))
        self.search_entry.bind("<Return>", lambda e: self._start_search())

        self.search_btn = ttk.Button(search_row, text="🔍  SEARCH",
                                      style="Accent.TButton",
                                      command=self._start_search)
        self.search_btn.pack(side="left", padx=(0,4))
        self.stop_btn = ttk.Button(search_row, text="⏹ Stop",
                                    style="Danger.TButton",
                                    command=self._stop_search, state="disabled")
        self.stop_btn.pack(side="left")

        self.progress = ttk.Progressbar(parent, mode="indeterminate")
        self.progress.pack(fill="x", padx=8, pady=(0,4))

        results_nb = ttk.Notebook(parent)
        results_nb.pack(fill="both", expand=True, padx=8, pady=(0,4))
        res_tab = ttk.Frame(results_nb); results_nb.add(res_tab, text="📄 Results")
        log_tab = ttk.Frame(results_nb); results_nb.add(log_tab, text="📜 Log")
        self._build_results_tree(res_tab)
        self._build_log(log_tab)

        action_bar = tk.Frame(parent, bg="#161b22")
        action_bar.pack(fill="x", padx=8, pady=(0,8))
        ttk.Button(action_bar, text="💾 Save Results",
                   command=self._save_results).pack(side="left", padx=(0,4))
        ttk.Button(action_bar, text="📥 Download All PDFs",
                   command=self._download_all_pdfs).pack(side="left", padx=(0,4))
        ttk.Button(action_bar, text="🗑 Clear",
                   command=self._clear_results).pack(side="left", padx=(0,4))
        self.result_count_lbl = tk.Label(action_bar, text="0 results",
                                          bg="#161b22", fg="#8b949e",
                                          font=("Consolas", 10))
        self.result_count_lbl.pack(side="right")

    def _build_results_tree(self, parent):
        frame = tk.Frame(parent, bg="#161b22")
        frame.pack(fill="both", expand=True)
        cols = ("title","url","type","actions")
        self.tree = ttk.Treeview(frame, columns=cols, show="headings",
                                  selectmode="browse")
        self.tree.heading("title",   text="Title")
        self.tree.heading("url",     text="URL")
        self.tree.heading("type",    text="Type")
        self.tree.heading("actions", text="Actions")
        self.tree.column("title",   width=280, minwidth=150)
        self.tree.column("url",     width=320, minwidth=200)
        self.tree.column("type",    width=60,  minwidth=50, anchor="center")
        self.tree.column("actions", width=100, minwidth=80, anchor="center")
        vsb = ttk.Scrollbar(frame, orient="vertical",   command=self.tree.yview)
        hsb = ttk.Scrollbar(frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side="right", fill="y")
        hsb.pack(side="bottom", fill="x")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", self._on_tree_double_click)
        self.tree.bind("<Button-1>", self._on_tree_click)

        self.snippet_text = scrolledtext.ScrolledText(
            parent, height=5, bg="#161b22", fg="#8b949e",
            font=("Consolas", 9), relief="flat", state="disabled", wrap="word")
        self.snippet_text.pack(fill="x", pady=(4,0))

    def _build_log(self, parent):
        self.log_text = scrolledtext.ScrolledText(
            parent, bg="#0d1117", fg="#3fb950",
            font=("Consolas", 9), relief="flat", state="disabled", wrap="word")
        self.log_text.pack(fill="both", expand=True)

    def _build_statusbar(self):
        bar = tk.Frame(self.root, bg="#161b22", height=24)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)
        self.status_var = tk.StringVar(value="Ready.")
        tk.Label(bar, textvariable=self.status_var, bg="#161b22",
                 fg="#8b949e", font=("Consolas", 9),
                 anchor="w").pack(side="left", padx=10)
        deps = []
        if not REQUESTS_AVAILABLE:  deps.append("requests/bs4 missing")
        if not SELENIUM_AVAILABLE:  deps.append("selenium missing")
        if not WDM_AVAILABLE:       deps.append("webdriver-manager missing")
        if deps:
            tk.Label(bar, text="⚠ " + " | ".join(deps),
                     bg="#161b22", fg="#f0883e",
                     font=("Consolas", 9)).pack(side="right", padx=10)

    # ── HELPERS ─────────────────────────────
    def _check_deps(self):
        self._log("── Dependency Check ──────────────────────────────")
        self._log(f"  requests + bs4    : {'✅ installed' if REQUESTS_AVAILABLE else '❌  pip install requests beautifulsoup4'}")
        self._log(f"  selenium          : {'✅ installed' if SELENIUM_AVAILABLE else '❌  pip install selenium'}")
        self._log(f"  wdm (chrome)      : {'✅' if WDM_CHROME  else '❌'}")
        self._log(f"  wdm (firefox)     : {'✅' if WDM_FIREFOX else '❌  pip install webdriver-manager'}")
        self._log(f"  wdm (edge)        : {'✅' if WDM_EDGE   else '❌'}")
        if WDM_AVAILABLE:
            try:
                import webdriver_manager as _wdm
                wdm_ver = tuple(int(x) for x in _wdm.__version__.split(".")[:2])
                if wdm_ver < (4, 0):
                    self._log(f"  ⚠ webdriver-manager {_wdm.__version__} is outdated — run:")
                    self._log("    pip install --upgrade webdriver-manager selenium")
                else:
                    self._log(f"  webdriver-manager v{_wdm.__version__}  ✅")
            except Exception:
                pass
        self._log("──────────────────────────────────────────────────")
        if not SELENIUM_AVAILABLE:
            self._log("  Run:  pip install selenium webdriver-manager requests beautifulsoup4")
        else:
            self._log("✅ Ready! Pick your browser in Settings → BROWSER.")
        self._log("")

    def _log(self, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"[{ts}] {msg}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _status(self, msg):
        self.status_var.set(msg)

    def _on_category_change(self, *_):
        cat = self.category_var.get()
        if cat in DORK_CATEGORIES:
            info = DORK_CATEGORIES[cat]
            self.cat_desc_lbl.configure(text=info["desc"])
            self.op_combo.configure(values=info["options"])
            if info["options"]:
                self.op_combo.current(0)
        self._update_preview()

    def _build_final_query(self):
        parts = []
        base = self.base_query_var.get().strip()
        if base:
            parts.append(f'"{base}"' if self.exact_var.get() else base)

        cat    = self.category_var.get()
        op_val = self.op_value_var.get().strip()
        if cat and op_val and cat in DORK_CATEGORIES:
            op = DORK_CATEGORIES[cat]["operator"]
            if self.or_var.get() and " " in op_val:
                vals   = op_val.split()
                or_str = " OR ".join(f"{op}:{v}" for v in vals)
                parts.append(f"({or_str})")
            else:
                parts.append(f"{op}:{op_val}")

        op_map = {
            "site_val":"site","inurl_val":"inurl","intitle_val":"intitle",
            "filetype_val":"filetype","intext_val":"intext","after_val":"after",
            "before_val":"before","ext_val":"ext",
        }
        for key, op in op_map.items():
            val = self.extra_ops[key].get().strip()
            if val:
                parts.append(f"{op}:{val}")

        for w in self.exclude_var.get().split():
            parts.append(w if w.startswith("-") else f"-{w}")

        return " ".join(parts)

    def _update_preview(self):
        q = self._build_final_query()
        self.query_preview.configure(text=q or "(empty)")
        self.search_var.set(q)

    def _load_template(self, query):
        self.search_var.set(query)
        self.query_preview.configure(text=query)
        self._log(f"📋 Template loaded: {query}")

    def _copy_query(self):
        q = self._build_final_query()
        self.root.clipboard_clear()
        self.root.clipboard_append(q)
        self._status("Query copied to clipboard.")

    def _open_browser(self):
        q = self.search_var.get().strip() or self._build_final_query()
        if not q:
            messagebox.showwarning("Empty", "Enter a query first.")
            return
        engine_tpl = SEARCH_ENGINES.get(self.engine_var.get(), SEARCH_ENGINES["Google"])
        url = engine_tpl.format(query=urllib.parse.quote_plus(q),
                                num=self.num_results_var.get())
        webbrowser.open(url)
        self._log(f"🌐 Opened browser: {url}")

    def _browse_dir(self):
        d = filedialog.askdirectory(initialdir=self.dir_var.get())
        if d:
            self.dir_var.set(d)
            self.download_dir = d

    def _open_download_folder(self):
        d = self.dir_var.get()
        os.makedirs(d, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(d)
        elif sys.platform == "darwin":
            os.system(f"open '{d}'")
        else:
            os.system(f"xdg-open '{d}'")

    def _close_driver(self):
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None
            self._log("🔴 Chrome driver closed.")

    # ── SEARCH ──────────────────────────────
    def _start_search(self):
        q = self.search_var.get().strip()
        if not q:
            messagebox.showwarning("Empty", "Enter or build a query first.")
            return

        mode = self.mode_var.get()

        if mode == "Browser Only":
            self._open_browser()
            return

        if "Selenium" in mode and not SELENIUM_AVAILABLE:
            messagebox.showerror("Selenium not installed",
                "Run in your terminal:\n\n"
                "  pip install selenium webdriver-manager\n\n"
                "Then restart the app.")
            return

        if "Requests" in mode and not REQUESTS_AVAILABLE:
            messagebox.showerror("requests not installed",
                "Run:\n  pip install requests beautifulsoup4\nThen restart.")
            return

        self.stop_flag = False
        self.search_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.progress.start(12)
        self._status(f"Searching: {q}")
        self._log(f"🔍 Query : {q}")
        self._log(f"   Mode  : {mode}")

        self.search_thread = threading.Thread(
            target=self._search_worker, args=(q, mode), daemon=True)
        self.search_thread.start()

    def _stop_search(self):
        self.stop_flag = True
        self._log("⏹ Stop requested.")
        self.root.after(0, self._search_done)

    def _search_done(self):
        self.progress.stop()
        self.search_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self._status(f"Done. {len(self.results)} results.")
        self._update_count()

    # ── WORKER ──────────────────────────────
    def _search_worker(self, query, mode):
        try:
            if "Selenium" in mode:
                new_results = self._search_selenium(query, mode)
            else:
                new_results = self._search_requests(query)

            skip_pdf = self.skip_pdf_var.get()
            for r in new_results:
                if self.stop_flag:
                    break
                if skip_pdf and r.get("type") == "PDF":
                    continue
                self.results.append(r)
                self.root.after(0, self._add_tree_row, r)

            self._log(f"✅ {len(new_results)} result(s) found.")
        except Exception as e:
            self._log(f"❌ Error: {e}")
        finally:
            self.root.after(0, self._search_done)

    # ── SELENIUM ────────────────────────────
    def _get_driver(self, headless):
        # Return existing live driver if available
        if self.driver:
            try:
                _ = self.driver.current_url
                return self.driver
            except Exception:
                self.driver = None

        browser = self.browser_var.get()  # "Auto-detect", "Chrome", "Firefox", "Edge", "Zen"
        driver  = None
        last_error = None

        # ── Determine launch order based on browser selection ──────────────
        if browser == "Auto-detect":
            order = ["firefox", "chrome", "edge"]
        elif browser in ("Firefox", "Zen"):
            order = ["firefox"]
        elif browser == "Chrome":
            order = ["chrome"]
        elif browser == "Edge":
            order = ["edge"]
        else:
            order = ["firefox", "chrome", "edge"]

        # ── Firefox / Zen (geckodriver) ─────────────────────────────────────
        def try_firefox():
            nonlocal last_error
            opts = FirefoxOptions()
            if headless:
                opts.add_argument("--headless")
            opts.set_preference("dom.webdriver.enabled",       False)
            opts.set_preference("useAutomationExtension",      False)
            opts.set_preference("general.useragent.override",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) "
                "Gecko/20100101 Firefox/124.0")

            # Zen-specific binary paths
            zen_paths = [
                r"C:\Users\frito\AppData\Local\zen\zen.exe",
                r"C:\Program Files\Zen Browser\zen.exe",
                r"C:\Program Files (x86)\Zen Browser\zen.exe",
                os.path.expandvars(r"%LOCALAPPDATA%\zen\zen.exe"),
                os.path.expandvars(r"%PROGRAMFILES%\Zen Browser\zen.exe"),
            ]
            if browser == "Zen":
                for zp in zen_paths:
                    if os.path.isfile(zp):
                        opts.binary_location = zp
                        self._log(f"   → Zen binary: {zp}")
                        break

            # Try geckodriver via wdm
            if WDM_FIREFOX:
                try:
                    self._log("   → Firefox/Zen via webdriver-manager…")
                    svc = FirefoxService(GeckoDriverManager().install())
                    d = webdriver.Firefox(service=svc, options=opts)
                    self._log("   ✅ Firefox/Zen (wdm) OK")
                    return d
                except Exception as e:
                    last_error = e
                    self._log(f"   ⚠ Firefox wdm failed: {e}")

            # Try system geckodriver
            try:
                self._log("   → Firefox/Zen via system geckodriver…")
                d = webdriver.Firefox(options=opts)
                self._log("   ✅ Firefox/Zen (system) OK")
                return d
            except Exception as e:
                last_error = e
                self._log(f"   ⚠ Firefox system failed: {e}")

            return None

        # ── Chrome ─────────────────────────────────────────────────────────
        def try_chrome():
            nonlocal last_error
            opts = ChromeOptions()
            if headless:
                opts.add_argument("--headless=new")
            opts.add_argument("--disable-blink-features=AutomationControlled")
            opts.add_experimental_option("excludeSwitches", ["enable-automation"])
            opts.add_experimental_option("useAutomationExtension", False)
            opts.add_argument("--start-maximized")
            opts.add_argument("--no-sandbox")
            opts.add_argument("--disable-dev-shm-usage")
            opts.add_argument("--disable-gpu")
            opts.add_argument(
                "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")

            if WDM_CHROME:
                try:
                    self._log("   → Chrome via webdriver-manager…")
                    svc = ChromeService(ChromeDriverManager().install())
                    d = webdriver.Chrome(service=svc, options=opts)
                    self._log("   ✅ Chrome (wdm) OK")
                    return d
                except Exception as e:
                    last_error = e
                    self._log(f"   ⚠ Chrome wdm failed: {e}")

            try:
                self._log("   → Chrome via system chromedriver…")
                d = webdriver.Chrome(options=opts)
                self._log("   ✅ Chrome (system) OK")
                return d
            except Exception as e:
                last_error = e
                self._log(f"   ⚠ Chrome system failed: {e}")

            return None

        # ── Edge ────────────────────────────────────────────────────────────
        def try_edge():
            nonlocal last_error
            opts = EdgeOptions()
            if headless:
                opts.add_argument("--headless=new")
            opts.add_argument("--no-sandbox")
            opts.add_argument("--disable-dev-shm-usage")

            if WDM_EDGE:
                try:
                    self._log("   → Edge via webdriver-manager…")
                    svc = EdgeService(EdgeChromiumDriverManager().install())
                    d = webdriver.Edge(service=svc, options=opts)
                    self._log("   ✅ Edge (wdm) OK")
                    return d
                except Exception as e:
                    last_error = e
                    self._log(f"   ⚠ Edge wdm failed: {e}")

            try:
                self._log("   → Edge via system msedgedriver…")
                d = webdriver.Edge(options=opts)
                self._log("   ✅ Edge (system) OK")
                return d
            except Exception as e:
                last_error = e
                self._log(f"   ⚠ Edge system failed: {e}")

            return None

        dispatch = {"firefox": try_firefox, "chrome": try_chrome, "edge": try_edge}
        for b in order:
            driver = dispatch[b]()
            if driver:
                break

        if driver is None:
            msg = (
                "No browser could be launched.\n\n"
                "Try:\n"
                "  pip install --upgrade selenium webdriver-manager\n"
                "  pip install geckodriver-autoinstaller\n\n"
                "Or install Firefox / Chrome / Edge and try again.\n"
                f"Last error: {last_error}"
            )
            self._log(f"❌ All browser methods failed. Last error: {last_error}")
            raise RuntimeError(msg)

        # Mask webdriver flag (Chrome/Edge only — Firefox ignores this)
        try:
            driver.execute_script(
                "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
        except Exception:
            pass

        if self.keep_driver_var.get():
            self.driver = driver
        return driver

    def _search_selenium(self, query, mode):
        headless = "Headless" in mode
        browser  = self.browser_var.get()
        self._log(f"🚀 Launching {browser}" + (" (headless)…" if headless else "…"))
        driver = self._get_driver(headless)

        engine     = self.engine_var.get()
        num        = self.num_results_var.get()
        engine_tpl = SEARCH_ENGINES.get(engine, SEARCH_ENGINES["Google"])
        url        = engine_tpl.format(query=urllib.parse.quote_plus(query), num=num)

        self._log(f"📡 Navigating to: {url}")
        driver.get(url)
        time.sleep(self.delay_var.get())

        page_src = driver.page_source.lower()
        if "captcha" in page_src or "unusual traffic" in page_src:
            if headless:
                self._log("⚠ CAPTCHA detected in headless mode.")
                self._log("  → Switch to 'Selenium (Chrome)' so you can solve it manually.")
            else:
                self._log("⚠ CAPTCHA appeared in Chrome window.")
                self._log("  → Solve it there, then click SEARCH again.")
            if not self.keep_driver_var.get():
                driver.quit(); self.driver = None
            return []

        soup = BeautifulSoup(driver.page_source, "html.parser")
        if engine == "Google":
            results = self._parse_google(soup)
        elif engine == "Bing":
            results = self._parse_bing(soup)
        elif engine == "DuckDuckGo":
            results = self._parse_ddg(soup)
        else:
            results = self._parse_generic(soup)

        if not results:
            self._log("⚠ 0 results parsed — page structure may differ or no results.")

        if not self.keep_driver_var.get():
            driver.quit(); self.driver = None

        return results

    # ── REQUESTS ────────────────────────────
    def _search_requests(self, query):
        if not REQUESTS_AVAILABLE:
            raise RuntimeError("requests/bs4 not installed")

        engine     = self.engine_var.get()
        num        = self.num_results_var.get()
        engine_tpl = SEARCH_ENGINES.get(engine, SEARCH_ENGINES["Google"])
        url        = engine_tpl.format(query=urllib.parse.quote_plus(query), num=num)

        self._log(f"📡 GET {url}")
        resp = requests.Session().get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        self._log(f"   HTTP {resp.status_code}")

        if "captcha" in resp.text.lower() or "unusual traffic" in resp.text.lower():
            self._log("🚫 Google returned a CAPTCHA page.")
            self._log("  → Switch to 'Selenium (Chrome)' in Settings tab.")
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        if engine == "Google":   return self._parse_google(soup)
        if engine == "Bing":     return self._parse_bing(soup)
        if engine == "DuckDuckGo": return self._parse_ddg(soup)
        return self._parse_generic(soup)

    # ── PARSERS ─────────────────────────────
    def _parse_google(self, soup):
        results = []
        for g in soup.select("div.g, div.tF2Cxc, div[data-hveid]"):
            a = g.select_one("a[href]")
            if not a: continue
            href = a.get("href","")
            if not href.startswith("http"): continue
            title_el   = g.select_one("h3")
            title      = title_el.get_text(strip=True) if title_el else href
            snippet_el = g.select_one("div.VwiC3b, div.IsZvec, span.st")
            snippet    = snippet_el.get_text(strip=True) if snippet_el else ""
            rtype      = "PDF" if href.lower().endswith(".pdf") else "WEB"
            results.append({"title":title,"url":href,"snippet":snippet,"type":rtype})

        # Fallback: grab any external links
        if not results:
            seen = set()
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if (href.startswith("http")
                        and "google" not in href
                        and href not in seen
                        and len(href) > 25):
                    seen.add(href)
                    title = a.get_text(strip=True) or href
                    rtype = "PDF" if href.lower().endswith(".pdf") else "WEB"
                    results.append({"title":title[:120],"url":href,
                                    "snippet":"","type":rtype})
        return results

    def _parse_bing(self, soup):
        results = []
        for li in soup.select("li.b_algo"):
            a = li.select_one("h2 a")
            if not a: continue
            href  = a.get("href","")
            title = a.get_text(strip=True)
            snip  = li.select_one("p, .b_caption p")
            snippet = snip.get_text(strip=True) if snip else ""
            rtype = "PDF" if href.lower().endswith(".pdf") else "WEB"
            results.append({"title":title,"url":href,"snippet":snippet,"type":rtype})
        return results

    def _parse_ddg(self, soup):
        results = []
        for res in soup.select(".result, .web-result"):
            a = res.select_one("a.result__a, a[href]")
            if not a: continue
            href = a.get("href","")
            if "duckduckgo.com" in href: continue
            title   = a.get_text(strip=True)
            snip_el = res.select_one(".result__snippet")
            snippet = snip_el.get_text(strip=True) if snip_el else ""
            rtype   = "PDF" if href.lower().endswith(".pdf") else "WEB"
            results.append({"title":title,"url":href,"snippet":snippet,"type":rtype})
        return results

    def _parse_generic(self, soup):
        results = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith("http") and len(href) > 20:
                title = a.get_text(strip=True) or href
                rtype = "PDF" if href.lower().endswith(".pdf") else "WEB"
                results.append({"title":title,"url":href,"snippet":"","type":rtype})
        return results[:40]

    # ── TREE ────────────────────────────────
    def _add_tree_row(self, r):
        icon = "📄" if r["type"] == "PDF" else "🌐"
        tag  = "pdf" if r["type"] == "PDF" else "web"
        self.tree.insert("","end",
                          values=(r["title"][:90], r["url"], icon, "⬇ Download"),
                          tags=(tag,))
        self.tree.tag_configure("pdf", foreground="#f0883e")
        self.tree.tag_configure("web", foreground="#c9d1d9")
        self._update_count()

    def _update_count(self):
        n = len(self.results)
        self.result_count_lbl.configure(text=f"{n} result{'s' if n!=1 else ''}")

    def _on_tree_double_click(self, _):
        sel = self.tree.selection()
        if not sel: return
        idx = self.tree.index(sel[0])
        if idx < len(self.results):
            webbrowser.open(self.results[idx]["url"])

    def _on_tree_click(self, event):
        col = self.tree.identify_column(event.x)
        row = self.tree.identify_row(event.y)
        if not row: return
        idx = self.tree.index(row)
        if idx < len(self.results):
            r = self.results[idx]
            self.snippet_text.configure(state="normal")
            self.snippet_text.delete("1.0","end")
            self.snippet_text.insert("end",
                f"URL: {r['url']}\n\n{r.get('snippet','(no snippet)')}")
            self.snippet_text.configure(state="disabled")
            if col == "#4":
                self._download_single(r)

    def _download_single(self, r):
        url = r["url"]
        self._log(f"📥 Downloading: {url}")
        d = self.dir_var.get()
        os.makedirs(d, exist_ok=True)

        def worker():
            try:
                fname = url.split("/")[-1].split("?")[0] or "result"
                if not os.path.splitext(fname)[1]:
                    fname += ".html"
                fpath = os.path.join(d, fname)
                if REQUESTS_AVAILABLE:
                    resp = requests.get(url, headers=HEADERS, timeout=20)
                    with open(fpath,"wb") as f: f.write(resp.content)
                else:
                    req = urllib.request.Request(url, headers=HEADERS)
                    with urllib.request.urlopen(req, timeout=20) as resp:
                        with open(fpath,"wb") as f: f.write(resp.read())
                self._log(f"✅ Saved: {fpath}")
                self._status(f"Downloaded: {fname}")
            except Exception as e:
                self._log(f"❌ Download failed: {e}")

        threading.Thread(target=worker, daemon=True).start()

    def _download_all_pdfs(self):
        pdfs = [r for r in self.results if r.get("type") == "PDF"]
        if not pdfs:
            messagebox.showinfo("No PDFs", "No PDF results to download.")
            return
        self._log(f"📥 Downloading {len(pdfs)} PDF(s)…")
        for r in pdfs: self._download_single(r)

    # ── SAVE ────────────────────────────────
    def _save_results(self):
        if not self.results:
            messagebox.showwarning("Empty", "No results to save.")
            return
        fmt  = self.save_format_var.get()
        d    = self.dir_var.get()
        os.makedirs(d, exist_ok=True)
        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        slug = re.sub(r"[^a-zA-Z0-9_]","_",self.search_var.get()[:40])

        if fmt == "TXT":
            fpath = os.path.join(d, f"dork_{slug}_{ts}.txt")
            with open(fpath,"w",encoding="utf-8") as f:
                f.write(f"Google Dorker Pro – Results\n")
                f.write(f"Query: {self.search_var.get()}\n")
                f.write(f"Date:  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Count: {len(self.results)}\n")
                f.write("="*70+"\n\n")
                for i,r in enumerate(self.results,1):
                    f.write(f"[{i}] {r['title']}\n")
                    f.write(f"     URL:  {r['url']}\n")
                    f.write(f"     Type: {r['type']}\n")
                    if r.get("snippet"):
                        f.write(f"     Desc: {r['snippet']}\n")
                    f.write("\n")

        elif fmt == "JSON":
            fpath = os.path.join(d, f"dork_{slug}_{ts}.json")
            with open(fpath,"w",encoding="utf-8") as f:
                json.dump({"query":self.search_var.get(),
                           "date":datetime.now().isoformat(),
                           "results":self.results},
                          f, indent=2, ensure_ascii=False)

        elif fmt == "CSV":
            fpath = os.path.join(d, f"dork_{slug}_{ts}.csv")
            with open(fpath,"w",encoding="utf-8") as f:
                f.write("title,url,type,snippet\n")
                for r in self.results:
                    t = r["title"].replace('"','""')
                    u = r["url"].replace('"','""')
                    s = r.get("snippet","").replace('"','""')
                    f.write(f'"{t}","{u}","{r["type"]}","{s}"\n')

        self._log(f"💾 Saved {fmt}: {fpath}")
        self._status(f"Saved: {os.path.basename(fpath)}")
        messagebox.showinfo("Saved", f"Results saved to:\n{fpath}")

    def _clear_results(self):
        self.results.clear()
        for item in self.tree.get_children(): self.tree.delete(item)
        self.snippet_text.configure(state="normal")
        self.snippet_text.delete("1.0","end")
        self.snippet_text.configure(state="disabled")
        self._update_count()
        self._log("🗑 Results cleared.")

    # ── GROQ AI ─────────────────────────────
    def _ai_generate_dork(self):
        if not GROQ_AVAILABLE:
            messagebox.showwarning("Groq Missing",
                "Install groq first:\n  pip install groq")
            return
        key = self.groq_key_var.get().strip()
        if not key:
            messagebox.showwarning("No API Key",
                "Enter your Groq API key in Settings → GROQ API KEY\n"
                "or add GROQ_API_KEY=... to your .env file.")
            return
        prompt = self.ai_prompt_var.get().strip()
        if not prompt:
            messagebox.showwarning("No Prompt",
                "Enter a description in the AI Prompt field first.\n"
                'Example: "find exposed nginx config files on .gov sites"')
            return

        self.ai_status_lbl.configure(text="⏳ thinking…", fg="#f0883e")
        self.root.update_idletasks()

        def worker():
            try:
                client = Groq(api_key=key)
                resp = client.chat.completions.create(
                    model=self.groq_model_var.get(),
                    max_tokens=256,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are a Google dorking expert. "
                                "When the user describes what they want to find, "
                                "respond with ONLY a single raw Google dork query string. "
                                "No explanation, no markdown, no quotes around the whole thing. "
                                "Just the query itself."
                            ),
                        },
                        {
                            "role": "user",
                            "content": prompt,
                        },
                    ],
                )
                dork = resp.choices[0].message.content.strip().strip('"').strip("'")
                self.root.after(0, lambda: self._ai_apply(dork))
            except Exception as e:
                self.root.after(0, lambda err=e: self._ai_error(err))

        threading.Thread(target=worker, daemon=True).start()

    def _ai_apply(self, dork):
        self.search_var.set(dork)
        self.query_preview.configure(text=dork)
        self.ai_status_lbl.configure(text="✅ done", fg="#3fb950")
        self._log(f"✨ AI generated dork: {dork}")
        self._status("AI dork generated.")

    def _ai_error(self, err):
        self.ai_status_lbl.configure(text="❌ error", fg="#f85149")
        self._log(f"❌ Groq error: {err}")
        messagebox.showerror("Groq Error", str(err))

    def _save_key_to_env(self):
        key = self.groq_key_var.get().strip()
        if not key:
            messagebox.showwarning("Empty", "No key to save.")
            return
        if getattr(sys, "frozen", False):
            base = os.path.dirname(sys.executable)
        else:
            base = os.path.dirname(os.path.abspath(__file__))
        env_path = os.path.join(base, ".env")
        # Read existing lines, replace or append
        lines = []
        found = False
        if os.path.isfile(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            for i, line in enumerate(lines):
                if line.startswith("GROQ_API_KEY"):
                    lines[i] = f"GROQ_API_KEY={key}\n"
                    found = True
                    break
        if not found:
            lines.append(f"GROQ_API_KEY={key}\n")
        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(lines)
        self._log(f"💾 Groq key saved to {env_path}")
        messagebox.showinfo("Saved", f"Key saved to:\n{env_path}")

    def on_close(self):
        self._close_driver()
        self.root.destroy()


# ─────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────

def main():
    root = tk.Tk()
    app  = GoogleDorkerApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)

    root.update_idletasks()
    w,h   = root.winfo_width(), root.winfo_height()
    sw,sh = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

    root.mainloop()


if __name__ == "__main__":
    main()
