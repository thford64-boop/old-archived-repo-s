"""
model_manager.py — Handles Ollama model selection per complexity tier.
"""

import json
import subprocess
import sys
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "config.json"

DEFAULT_MODELS = {
    "low":    "qwen2.5:1.5b",
    "medium": "llama3.1:8b",
    "high":   "llama3.1:14b",
    "ultra":  "llama3.3:70b",
}

DEFAULT_CONFIG = {
    "complexity": "medium",
    "models": DEFAULT_MODELS,
}


def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r") as f:
                cfg = json.load(f)
            # Back-fill any missing keys
            for k, v in DEFAULT_CONFIG.items():
                cfg.setdefault(k, v)
            if "models" in cfg:
                for tier, model in DEFAULT_MODELS.items():
                    cfg["models"].setdefault(tier, model)
            return cfg
        except json.JSONDecodeError:
            pass
    return dict(DEFAULT_CONFIG)


def save_config(cfg: dict) -> None:
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)


def get_active_model(cfg: dict | None = None) -> str:
    cfg = cfg or load_config()
    # /model command stores a direct override here
    if cfg.get("custom_model"):
        return cfg["custom_model"]
    tier = cfg.get("complexity", "medium")
    return cfg["models"].get(tier, DEFAULT_MODELS["medium"])


def set_complexity(tier: str, cfg: dict | None = None) -> dict:
    tier = tier.lower()
    valid = list(DEFAULT_MODELS.keys())
    if tier not in valid:
        raise ValueError(f"Complexity must be one of: {', '.join(valid)}")
    cfg = cfg or load_config()
    cfg["complexity"] = tier
    save_config(cfg)
    return cfg


def list_local_models() -> list[str]:
    """Return names of models already pulled in Ollama."""
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True, text=True, timeout=10
        )
        lines = result.stdout.strip().splitlines()
        models = []
        for line in lines[1:]:          # skip header
            parts = line.split()
            if parts:
                models.append(parts[0])
        return models
    except Exception:
        return []


def ensure_model(model_name: str) -> bool:
    """
    Check whether a model is available locally. If not, attempt to pull it.
    Returns True on success, False on failure.
    """
    available = list_local_models()
    if any(model_name in m for m in available):
        return True
    print(f"[ModMaster] Model '{model_name}' not found locally. Pulling…")
    try:
        result = subprocess.run(
            ["ollama", "pull", model_name],
            timeout=600
        )
        return result.returncode == 0
    except Exception as e:
        print(f"[ModMaster] Failed to pull model: {e}", file=sys.stderr)
        return False
