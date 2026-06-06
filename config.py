"""Central configuration for ResearchGraph AI V2.

Most user customization is controlled from `.env` only. The code reads a single
LLM_PROVIDER value and routes model creation through `llm_factory.py`.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"), override=True)

for proxy_name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
    proxy_value = os.getenv(proxy_name, "").strip().rstrip("/")
    if proxy_value in {"http://127.0.0.1:9", "https://127.0.0.1:9"}:
        os.environ.pop(proxy_name, None)

APP_NAME = "ResearchGraph AI V2"

# -----------------------------------------------------------------------------
# LLM provider settings
# -----------------------------------------------------------------------------
# Supported providers:
#   openai, gemini, anthropic, groq, openrouter, together, ollama, custom
#
# For OpenAI-compatible providers, use:
#   LLM_PROVIDER=custom
#   LLM_API_KEY=...
#   LLM_BASE_URL=https://provider.example.com/v1
#   LLM_MODEL=provider-model-name
# -----------------------------------------------------------------------------
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini").lower().strip()
LLM_MODEL = os.getenv("LLM_MODEL", "").strip()
LLM_API_KEY = os.getenv("LLM_API_KEY", "").strip()
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "").strip()
LLM_TIMEOUT_SECONDS = int(os.getenv("LLM_TIMEOUT_SECONDS", "60"))
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "2"))

# Provider-specific API keys. Users normally fill only the one they need.
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", os.getenv("GEMINI_API_KEY", "")).strip()
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY", "").strip()

# Default model names. Override with LLM_MODEL for one-place model switching.
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-5-haiku-latest")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
TOGETHER_MODEL = os.getenv("TOGETHER_MODEL", "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# -----------------------------------------------------------------------------
# Search provider settings
# -----------------------------------------------------------------------------
# Supported SEARCH_PROVIDER values:
#   auto, tavily, serpapi, brave, serper, bing, duckduckgo, custom, none
# auto chooses the first available key in this priority:
#   Tavily -> SerpAPI -> Brave -> Serper -> Bing -> DuckDuckGo fallback
SEARCH_PROVIDER = os.getenv("SEARCH_PROVIDER", "auto").lower().strip()
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "").strip()
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY", "").strip()
BRAVE_SEARCH_API_KEY = os.getenv("BRAVE_SEARCH_API_KEY", "").strip()
SERPER_API_KEY = os.getenv("SERPER_API_KEY", "").strip()
BING_SEARCH_API_KEY = os.getenv("BING_SEARCH_API_KEY", "").strip()
BING_SEARCH_ENDPOINT = os.getenv("BING_SEARCH_ENDPOINT", "https://api.bing.microsoft.com/v7.0/search").strip()
SEARCH_API_URL = os.getenv("SEARCH_API_URL", "").strip()
SEARCH_API_KEY = os.getenv("SEARCH_API_KEY", "").strip()
ALLOW_DUCKDUCKGO_FALLBACK = os.getenv("ALLOW_DUCKDUCKGO_FALLBACK", "true").lower().strip() in {"1", "true", "yes", "y"}
SEARCH_TIMEOUT_SECONDS = int(os.getenv("SEARCH_TIMEOUT_SECONDS", "20"))

DATABASE_PATH = Path(os.getenv("DATABASE_PATH", "researchgraph_v2.db"))
EXPORT_DIR = Path(os.getenv("EXPORT_DIR", "exports"))
EXPORT_DIR.mkdir(exist_ok=True)

# Optional FastAPI protection
API_AUTH_TOKEN = os.getenv("API_AUTH_TOKEN", "").strip()

DEFAULT_MAX_SOURCES = int(os.getenv("DEFAULT_MAX_SOURCES", "6"))
MAX_REVISIONS = int(os.getenv("MAX_REVISIONS", "1"))
