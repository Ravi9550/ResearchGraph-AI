"""Provider-agnostic web search layer for ResearchGraph AI V2.

Users switch search providers from `.env` only:

    SEARCH_PROVIDER=auto   # default; picks first configured key
    SEARCH_PROVIDER=tavily
    SEARCH_PROVIDER=serpapi
    SEARCH_PROVIDER=brave
    SEARCH_PROVIDER=serper
    SEARCH_PROVIDER=bing
    SEARCH_PROVIDER=duckduckgo
    SEARCH_PROVIDER=custom
    SEARCH_PROVIDER=none

All providers return the same stable schema so the agent pipeline does not care
which search API is being used.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, List
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from config import (
    ALLOW_DUCKDUCKGO_FALLBACK,
    BING_SEARCH_API_KEY,
    BING_SEARCH_ENDPOINT,
    BRAVE_SEARCH_API_KEY,
    DATABASE_PATH,
    SEARCH_API_KEY,
    SEARCH_API_URL,
    SEARCH_PROVIDER,
    SEARCH_TIMEOUT_SECONDS,
    SERPAPI_API_KEY,
    SERPER_API_KEY,
    TAVILY_API_KEY,
)

SEARCH_CACHE_TTL_SECONDS = 60 * 60 * 24


@dataclass
class SearchResult:
    source_id: str
    title: str
    url: str
    snippet: str = ""
    domain: str = ""
    content: str = ""
    published_at: str = "unknown"
    scrape_status: str = "pending"
    search_provider: str = "unknown"


def _domain(url: str) -> str:
    try:
        return urlparse(url).netloc.replace("www.", "") or "unknown"
    except Exception:
        return "unknown"


def _clean(text: Any) -> str:
    if text is None:
        return ""
    return re.sub(r"\s+", " ", str(text)).strip()


def _cache_key(provider: str, query: str, max_results: int) -> str:
    raw = f"{provider}|{query.strip().lower()}|{max_results}"
    return "search:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _ensure_search_cache() -> None:
    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS search_cache (
                cache_key TEXT PRIMARY KEY,
                created_at REAL NOT NULL,
                payload TEXT NOT NULL
            )
            """
        )
        conn.commit()


def _get_cached_search(provider: str, query: str, max_results: int) -> List[Dict[str, str]] | None:
    _ensure_search_cache()
    cutoff = time.time() - SEARCH_CACHE_TTL_SECONDS
    with sqlite3.connect(DATABASE_PATH) as conn:
        row = conn.execute(
            "SELECT payload FROM search_cache WHERE cache_key = ? AND created_at > ?",
            (_cache_key(provider, query, max_results), cutoff),
        ).fetchone()
    if not row:
        return None
    try:
        data = json.loads(row[0])
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, list) else None


def _set_cached_search(provider: str, query: str, max_results: int, results: List[Dict[str, str]]) -> None:
    _ensure_search_cache()
    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO search_cache(cache_key, created_at, payload) VALUES (?, ?, ?)",
            (_cache_key(provider, query, max_results), time.time(), json.dumps(results)),
        )
        conn.commit()


def extract_date_hint(text: str) -> str:
    """Best-effort date extraction for freshness scoring."""
    if not text:
        return "unknown"
    patterns = [
        r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},\s+\d{4}",
        r"\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}",
        r"\b20\d{2}-\d{2}-\d{2}\b",
        r"\b20\d{2}\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(0)
    return "unknown"


def _standardize(items: Iterable[Dict[str, Any]], provider: str, max_results: int) -> List[Dict[str, str]]:
    """Convert provider-specific items into the pipeline's stable schema."""
    results: List[SearchResult] = []
    seen: set[str] = set()

    for item in items:
        title = _clean(item.get("title") or item.get("name") or item.get("heading") or "Untitled")
        url = _clean(item.get("url") or item.get("link") or item.get("href") or item.get("displayLink"))
        snippet = _clean(
            item.get("snippet")
            or item.get("content")
            or item.get("description")
            or item.get("body")
            or item.get("summary")
        )
        published_at = _clean(item.get("published_at") or item.get("date") or item.get("age") or "")

        if not url or url in seen:
            continue
        seen.add(url)

        results.append(
            SearchResult(
                source_id=f"S{len(results) + 1}",
                title=title,
                url=url,
                snippet=snippet,
                domain=_domain(url),
                published_at=published_at or extract_date_hint(" ".join([title, snippet])),
                search_provider=provider,
            )
        )
        if len(results) >= max_results:
            break

    return [asdict(result) for result in results]


def available_search_providers() -> Dict[str, bool]:
    """Return providers that are currently usable based on env keys/settings."""
    return {
        "tavily": bool(TAVILY_API_KEY),
        "serpapi": bool(SERPAPI_API_KEY),
        "brave": bool(BRAVE_SEARCH_API_KEY),
        "serper": bool(SERPER_API_KEY),
        "bing": bool(BING_SEARCH_API_KEY),
        "duckduckgo": bool(ALLOW_DUCKDUCKGO_FALLBACK),
        "custom": bool(SEARCH_API_URL),
        "none": True,
    }


def resolve_search_provider() -> str:
    """Resolve SEARCH_PROVIDER, including automatic fallback order."""
    provider = (SEARCH_PROVIDER or "auto").lower().strip()
    available = available_search_providers()

    if provider == "auto":
        for candidate in ["tavily", "serpapi", "brave", "serper", "bing", "duckduckgo"]:
            if available.get(candidate):
                return candidate
        return "none"

    aliases = {
        "serapi": "serpapi",  # common typo
        "serp": "serpapi",
        "brave_search": "brave",
        "ddg": "duckduckgo",
        "duck": "duckduckgo",
        "disabled": "none",
        "off": "none",
    }
    provider = aliases.get(provider, provider)

    if provider not in available:
        raise RuntimeError(
            f"Unsupported SEARCH_PROVIDER='{SEARCH_PROVIDER}'. Use auto, tavily, serpapi, brave, serper, bing, duckduckgo, custom, or none."
        )
    if not available[provider]:
        raise RuntimeError(_missing_key_message(provider))
    return provider


def _missing_key_message(provider: str) -> str:
    mapping = {
        "tavily": "TAVILY_API_KEY is missing.",
        "serpapi": "SERPAPI_API_KEY is missing.",
        "brave": "BRAVE_SEARCH_API_KEY is missing.",
        "serper": "SERPER_API_KEY is missing.",
        "bing": "BING_SEARCH_API_KEY is missing.",
        "custom": "SEARCH_API_URL is missing. SEARCH_API_KEY is optional depending on your custom endpoint.",
    }
    return mapping.get(provider, f"Search provider '{provider}' is not configured.")


@retry(
    wait=wait_exponential(multiplier=1, min=1, max=10),
    stop=stop_after_attempt(3),
    retry=retry_if_exception_type((requests.RequestException, RuntimeError)),
)
def search_web(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """Search the web through the configured provider and return stable result schema."""
    provider = resolve_search_provider()

    cached = _get_cached_search(provider, query, max_results)
    if cached is not None:
        return cached

    if provider == "tavily":
        results = _search_tavily(query, max_results)
    elif provider == "serpapi":
        results = _search_serpapi(query, max_results)
    elif provider == "brave":
        results = _search_brave(query, max_results)
    elif provider == "serper":
        results = _search_serper(query, max_results)
    elif provider == "bing":
        results = _search_bing(query, max_results)
    elif provider == "duckduckgo":
        results = _search_duckduckgo(query, max_results)
    elif provider == "custom":
        results = _search_custom(query, max_results)
    elif provider == "none":
        results = []
    else:
        raise RuntimeError(f"Unhandled search provider: {provider}")

    _set_cached_search(provider, query, max_results, results)
    return results


def _search_tavily(query: str, max_results: int) -> List[Dict[str, str]]:
    from tavily import TavilyClient

    client = TavilyClient(api_key=TAVILY_API_KEY)
    response = client.search(query=query, max_results=max_results, search_depth="advanced")
    items = response.get("results", [])
    return _standardize(items, "tavily", max_results)


def _search_serpapi(query: str, max_results: int) -> List[Dict[str, str]]:
    response = requests.get(
        "https://serpapi.com/search.json",
        params={"engine": "google", "q": query, "api_key": SERPAPI_API_KEY, "num": max_results},
        timeout=SEARCH_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    data = response.json()
    items = data.get("organic_results", [])
    return _standardize(items, "serpapi", max_results)


def _search_brave(query: str, max_results: int) -> List[Dict[str, str]]:
    response = requests.get(
        "https://api.search.brave.com/res/v1/web/search",
        params={"q": query, "count": max_results},
        headers={"X-Subscription-Token": BRAVE_SEARCH_API_KEY, "Accept": "application/json"},
        timeout=SEARCH_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    data = response.json()
    items = data.get("web", {}).get("results", [])
    return _standardize(items, "brave", max_results)


def _search_serper(query: str, max_results: int) -> List[Dict[str, str]]:
    response = requests.post(
        "https://google.serper.dev/search",
        json={"q": query, "num": max_results},
        headers={"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"},
        timeout=SEARCH_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    data = response.json()
    items = data.get("organic", [])
    return _standardize(items, "serper", max_results)


def _search_bing(query: str, max_results: int) -> List[Dict[str, str]]:
    response = requests.get(
        BING_SEARCH_ENDPOINT,
        params={"q": query, "count": max_results, "textFormat": "Raw"},
        headers={"Ocp-Apim-Subscription-Key": BING_SEARCH_API_KEY},
        timeout=SEARCH_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    data = response.json()
    items = data.get("webPages", {}).get("value", [])
    return _standardize(items, "bing", max_results)


def _search_duckduckgo(query: str, max_results: int) -> List[Dict[str, str]]:
    """No-key fallback for demos. Use Tavily/SerpAPI/Brave/Serper/Bing for reliable production search."""
    response = requests.post(
        "https://html.duckduckgo.com/html/",
        data={"q": query},
        headers={"User-Agent": "Mozilla/5.0 ResearchGraphAI/2.0"},
        timeout=SEARCH_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    items: List[Dict[str, str]] = []
    for result in soup.select(".result"):
        link = result.select_one(".result__a")
        snippet = result.select_one(".result__snippet")
        if not link:
            continue
        href = link.get("href") or ""
        items.append({"title": link.get_text(" ", strip=True), "url": href, "snippet": snippet.get_text(" ", strip=True) if snippet else ""})
        if len(items) >= max_results:
            break
    return _standardize(items, "duckduckgo", max_results)


def _search_custom(query: str, max_results: int) -> List[Dict[str, str]]:
    """Call a custom search endpoint.

    Expected flexible response formats:
      {"results": [{"title": ..., "url": ..., "snippet": ...}]}
      {"organic": [...]} or a raw list of result objects.
    """
    headers = {"Accept": "application/json"}
    if SEARCH_API_KEY:
        headers["Authorization"] = f"Bearer {SEARCH_API_KEY}"

    response = requests.get(
        SEARCH_API_URL,
        params={"q": query, "query": query, "num": max_results, "max_results": max_results},
        headers=headers,
        timeout=SEARCH_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    data = response.json()
    if isinstance(data, list):
        items = data
    else:
        items = data.get("results") or data.get("organic") or data.get("items") or []
    return _standardize(items, "custom", max_results)
