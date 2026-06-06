"""Search, scraping, deduplication, and rate-limit-safe utilities."""

from __future__ import annotations

import hashlib
import os
import re
import sqlite3
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Dict, List
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from config import DATABASE_PATH
from search_factory import resolve_search_provider, search_web


@dataclass
class SourceResult:
    source_id: str
    title: str
    url: str
    snippet: str = ""
    domain: str = ""
    content: str = ""
    published_at: str = "unknown"
    scrape_status: str = "pending"


def _domain(url: str) -> str:
    try:
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return "unknown"


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def init_cache() -> None:
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


def _cache_key(prefix: str, value: str) -> str:
    return prefix + ":" + hashlib.sha256(value.encode("utf-8")).hexdigest()


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



# search_web() is now provider-agnostic and lives in search_factory.py.
# This keeps Tavily/SerpAPI/Brave/Serper/Bing/DuckDuckGo/custom logic out of
# the scraping pipeline, so users switch search providers from `.env` only.

@retry(
    wait=wait_exponential(multiplier=1, min=1, max=8),
    stop=stop_after_attempt(3),
    retry=retry_if_exception_type(requests.RequestException),
)
def scrape_url(url: str, max_chars: int = 10000) -> str:
    """Scrape readable page text with retry and cleanup."""
    headers = {
        "User-Agent": "Mozilla/5.0 ResearchGraphAI/2.0 (+educational portfolio project)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    response = requests.get(url, timeout=14, headers=headers)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "noscript", "nav", "footer", "header", "form", "aside"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    return _normalize_whitespace(text)[:max_chars]


def enrich_sources_with_content(sources: List[Dict[str, str]], max_chars: int = 10000) -> List[Dict[str, str]]:
    enriched: List[Dict[str, str]] = []
    for source in sources:
        source = dict(source)
        try:
            source["content"] = scrape_url(source["url"], max_chars=max_chars)
            source["scrape_status"] = "success"
            if source.get("published_at") == "unknown":
                source["published_at"] = extract_date_hint(source["content"][:1500])
        except Exception as exc:  # noqa: BLE001 - full pipeline should not fail for one URL
            source["content"] = source.get("snippet", "")
            source["scrape_status"] = f"failed: {exc}"
        enriched.append(source)
    return enriched


def search_and_scrape(queries: List[str], max_sources: int = 6) -> List[Dict[str, str]]:
    """Run multiple searches through configured provider, deduplicate URLs, and scrape top sources."""
    combined: List[Dict[str, str]] = []
    seen = set()
    per_query = max(2, max_sources // max(1, len(queries)))
    provider = "unknown"
    try:
        provider = resolve_search_provider()
    except Exception:
        # Let search_web produce the detailed error inside each query path.
        pass

    for query in queries:
        try:
            results = search_web(query, max_results=per_query)
        except Exception as exc:  # noqa: BLE001
            results = [
                {
                    "source_id": "S1",
                    "title": f"Search failed for query: {query}",
                    "url": "about:blank",
                    "snippet": str(exc),
                    "domain": "local-error",
                    "content": str(exc),
                    "published_at": "unknown",
                    "scrape_status": "search_failed",
                    "search_provider": provider,
                }
            ]
        for source in results:
            if source["url"] in seen:
                continue
            seen.add(source["url"])
            source["source_id"] = f"S{len(combined) + 1}"
            combined.append(source)
            if len(combined) >= max_sources:
                break
        if len(combined) >= max_sources:
            break

    return enrich_sources_with_content(combined)
