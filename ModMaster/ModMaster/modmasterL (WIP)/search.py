"""
search.py — Tavily web-search fallback for ModMaster.
"""

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

try:
    from tavily import TavilyClient
    _tavily_available = True
except ImportError:
    _tavily_available = False


def _get_client():
    api_key = os.getenv("TAVILY_API_KEY", "").strip()
    if not api_key or api_key.startswith("tvly-your-key"):
        return None, "TAVILY_API_KEY is not configured in .env."
    if not _tavily_available:
        return None, "tavily-python package is not installed (pip install tavily-python)."
    try:
        return TavilyClient(api_key=api_key), None
    except Exception as e:
        return None, str(e)


def web_search(query: str, max_results: int = 5) -> str:
    """
    Search the web via Tavily. Returns a formatted string ready to inject
    into the model context, or an error message the model can relay to the user.
    """
    client, err = _get_client()
    if err:
        return f"[Search unavailable: {err}]"

    try:
        response = client.search(
            query=query,
            search_depth="basic",
            max_results=max_results,
            include_answer=True,
        )
    except Exception as e:
        return f"[Search failed: {e}]"

    parts = []

    answer = response.get("answer", "").strip()
    if answer:
        parts.append(f"Search summary: {answer}")

    results = response.get("results", [])
    if results:
        parts.append("\nSources:")
        for r in results:
            title   = r.get("title", "").strip()
            url     = r.get("url", "").strip()
            content = r.get("content", "").strip()
            snippet = content[:300] + ("…" if len(content) > 300 else "")
            parts.append(f"- {title}\n  {url}\n  {snippet}")

    return "\n".join(parts) if parts else "[No results found.]"


def search_needed(text: str) -> bool:
    """
    Heuristic: does this query look like it needs current/live information?
    The LLM decides ultimately; this is a lightweight pre-filter.
    """
    keywords = [
        "today", "latest", "current", "news", "right now",
        "this week", "this month", "this year", "2024", "2025", "2026",
        "price of", "stock", "weather", "score", "who won",
    ]
    lower = text.lower()
    return any(kw in lower for kw in keywords)
