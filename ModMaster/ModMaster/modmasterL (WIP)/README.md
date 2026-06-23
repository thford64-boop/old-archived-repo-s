# ModMaster

**A private, local AI assistant powered by Ollama.**  
Everything runs on your own machine — no data leaves your device.

---

## Prerequisites

| Requirement | Notes |
|---|---|
| Python 3.11+ | [python.org](https://www.python.org/) |
| Ollama | [ollama.com](https://ollama.com/) — must be running |
| At least one local model | See model tier table below |

---

## Quick Start

```bash
# 1. Clone / download the project
cd modmaster

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Pull a model (medium tier example)
ollama pull llama3.1:8b

# 4. (Optional) Add your Tavily key for web search
#    Edit .env → TAVILY_API_KEY=tvly-your-real-key

# 5. Run
python main.py
```

---

## Project Structure

```
modmaster/
├── .env              ← Tavily API key (optional)
├── instructions.txt  ← ModMaster's system prompt / rules (edit freely)
├── icon.ico          ← App window icon (replace with your own)
├── config.json       ← Active complexity tier + model names
├── main.py           ← Entry point & GUI
├── model_manager.py  ← Model selection logic
├── search.py         ← Tavily web-search fallback
├── requirements.txt
└── README.md
```

---

## Complexity Tiers

ModMaster selects a model based on the complexity setting. You can change
it via the sidebar radio buttons or by typing `/complexity <tier>` in chat.

| Tier | Default Model | VRAM Guideline |
|---|---|---|
| `low`    | qwen2.5:1.5b    | 2 GB  |
| `medium` | llama3.1:8b     | 6 GB  |
| `high`   | llama3.1:14b    | 10 GB |
| `ultra`  | llama3.3:70b    | 40 GB |

To use different models, edit `config.json`:

```json
{
  "complexity": "medium",
  "models": {
    "low":    "qwen2.5:1.5b",
    "medium": "mistral:7b",
    "high":   "mistral:14b",
    "ultra":  "mixtral:8x7b"
  }
}
```

---

## Customising ModMaster

Edit **`instructions.txt`** — this is ModMaster's system prompt.  
You control its personality, rules, response style, and any domain focus.  
Hit **Reload Rules** in the sidebar (or type `/reload`) to apply changes
without restarting.

---

## Chat Commands

| Command | Effect |
|---|---|
| `/complexity low\|medium\|high\|ultra` | Switch model tier |
| `/complexity` | Show current tier & model |
| `/model` | Show active model name |
| `/clear` | Clear conversation history |
| `/reload` | Reload `instructions.txt` |
| `/help` | List all commands |

---

## Web Search (Optional)

ModMaster answers from local model knowledge first.  
For queries that look like they need current information, it can fall back
to Tavily Search.

1. Get a free API key at [tavily.com](https://tavily.com/)
2. Add it to `.env`:
   ```
   TAVILY_API_KEY=tvly-your-real-key-here
   ```

If the key is missing or the call fails, ModMaster will tell you search
isn't available rather than crashing.

---

## Packaging as a Desktop App (optional)

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --icon=icon.ico main.py
```

The executable appears in `dist/main` (macOS/Linux) or `dist/main.exe` (Windows).

---

## Troubleshooting

**"Error communicating with Ollama"**  
→ Make sure Ollama is running (`ollama serve` in a terminal).

**Model not found / slow first response**  
→ ModMaster will try to `ollama pull` the model automatically on first use.
   For large models, pull manually first: `ollama pull <model-name>`.

**Web search not working**  
→ Check that `TAVILY_API_KEY` in `.env` is a real key (not the placeholder).

---

*ModMaster is your AI. Runs locally. Stays private.*
