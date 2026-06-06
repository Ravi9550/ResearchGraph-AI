# ResearchGraph AI V2

A resume-ready multi-agent research intelligence system.

It takes a topic, plans research, searches public sources, extracts evidence, writes a citation-backed report, verifies the report for unsupported claims, revises weak reports, scores quality, stores research history, and reuses previous research memory.

## Why this is stronger than a tutorial project

Most tutorials stop at: search web -> scrape -> write report.

ResearchGraph AI V2 adds:

- Planner Agent
- Provider-agnostic Search/Scrape Tool with retry and fallback
- Evidence Extractor Agent
- Citation-aware Writer Agent
- Verifier Agent
- Revision Agent
- LangGraph-ready conditional workflow
- SQLite history
- SQLite-backed research memory
- Citation coverage scoring
- Citation validity scoring
- Source diversity scoring
- Freshness scoring
- Readability scoring
- Unsupported-claim penalty
- Markdown / JSON / PDF export
- Streamlit production-friendly dashboard
- FastAPI backend

## Architecture

```text
User Topic
   ↓
Planner Agent
   ↓
Memory Retrieval
   ↓
Search + Scrape Tool
   ↓
Evidence Extractor Agent
   ↓
Citation-aware Writer Agent
   ↓
Verifier Agent
   ↓
Conditional Revision if score is weak
   ↓
Quality Scoring + History + Memory Save
```

When LangGraph is installed, the project uses a graph workflow with a conditional edge from verifier to revision. If LangGraph fails in a simple deployment environment, the project automatically falls back to a sequential pipeline so your demo does not break.

## Frontend choice

This project uses **Streamlit** as the main frontend because it is easiest to deploy live and still gives a strong portfolio demo. For your resume, the backend and architecture matter more than using React. FastAPI is included separately for production-style API demos.

## Setup

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt
```

Create a local `.env` file. Do not commit it to GitHub.

```env
LLM_PROVIDER=gemini
GOOGLE_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-2.5-flash
SEARCH_PROVIDER=auto
TAVILY_API_KEY=your_tavily_key   # optional; SerpAPI/Brave/Serper/Bing also supported
API_AUTH_TOKEN=choose_a_long_random_token_for_fastapi
```

## Run Streamlit UI

```bash
streamlit run app.py
```

Open the URL shown in terminal, usually:

```text
http://localhost:8501
```

## Run FastAPI backend

```bash
uvicorn api:app --reload
```

Open:

```text
http://127.0.0.1:8000/docs
```

## Offline smoke test

```bash
python tests_dummy.py
```

This does not call any paid LLM provider or external search API.

## Resume bullets

**ResearchGraph AI V2 — Multi-Agent Research Intelligence System**  
`LangGraph, LangChain, FastAPI, Streamlit, SQLite, Gemini/OpenAI/Claude/Groq/Ollama/OpenRouter, Tavily/SerpAPI/Brave/Serper/Bing/DuckDuckGo`

- Built a multi-agent research platform that plans research tasks, searches public sources, extracts evidence, writes citation-backed reports, verifies claims, and revises weak outputs automatically.
- Implemented a LangGraph-ready workflow with planner, evidence extractor, writer, verifier, and revision agents, including conditional routing from verification failure back to report revision.
- Designed a quality evaluation engine to score citation coverage, citation validity, source diversity, evidence depth, freshness, readability, and unsupported-claim penalties.
- Added reusable research memory using SQLite for simple production deployment.
- Built a Streamlit dashboard to inspect report output, source evidence, verifier feedback, evaluation scores, memory matches, live agent status, and exports.
- Exposed the pipeline through FastAPI with synchronous and async-style thread-backed job endpoints.

## What to explain in interviews

### How do you prevent hallucination?

The writer is restricted to the extracted evidence pack, every factual claim must cite a source ID, and the verifier flags unsupported claims before saving.

### How do you verify sources?

The verifier checks citation issues, source quality, contradictions, freshness risks, and unsupported claims. Deterministic scoring also checks whether citations are valid source IDs.

### How do agents share state?

The pipeline passes a shared state dictionary containing topic, plan, sources, evidence, report, verifier output, scores, trace, and memory context. In LangGraph mode this state moves between graph nodes.

### Why multiple agents?

The tasks have different objectives: planning, evidence extraction, writing, and verification. Splitting them makes prompts simpler, outputs more inspectable, and failures easier to debug.

### What happens if scraping fails?

Each URL scrape has retry logic. If scraping fails, the pipeline falls back to the search snippet instead of failing the whole run.

### How do you evaluate report quality?

The system computes citation coverage, citation validity, source diversity, evidence depth, freshness, readability, and verifier penalties.


## Switching LLM providers from `.env` only

This V2 build is provider-agnostic. You do **not** edit Python files to change models. Change only `LLM_PROVIDER`, `LLM_MODEL`, and the matching API key in `.env`.

Supported values:

```env
LLM_PROVIDER=gemini      # Google Gemini
LLM_PROVIDER=openai      # OpenAI
LLM_PROVIDER=anthropic   # Claude
LLM_PROVIDER=groq        # Groq-hosted open models
LLM_PROVIDER=openrouter  # Many models via OpenRouter
LLM_PROVIDER=together    # Together AI
LLM_PROVIDER=ollama      # Local Ollama model
LLM_PROVIDER=custom      # Any OpenAI-compatible provider
```

### Example: Gemini

```env
LLM_PROVIDER=gemini
GOOGLE_API_KEY=your_gemini_api_key
LLM_MODEL=gemini-2.5-flash
SEARCH_PROVIDER=auto
TAVILY_API_KEY=your_tavily_key   # optional; SerpAPI/Brave/Serper/Bing also supported
```

### Example: OpenAI

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=your_openai_api_key
LLM_MODEL=gpt-4o-mini
SEARCH_PROVIDER=auto
TAVILY_API_KEY=your_tavily_key   # optional; SerpAPI/Brave/Serper/Bing also supported
```

### Example: Claude / Anthropic

```env
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=your_anthropic_api_key
LLM_MODEL=claude-3-5-haiku-latest
SEARCH_PROVIDER=auto
TAVILY_API_KEY=your_tavily_key   # optional; SerpAPI/Brave/Serper/Bing also supported
```

### Example: Groq

```env
LLM_PROVIDER=groq
GROQ_API_KEY=your_groq_api_key
LLM_MODEL=llama-3.1-8b-instant
SEARCH_PROVIDER=auto
TAVILY_API_KEY=your_tavily_key   # optional; SerpAPI/Brave/Serper/Bing also supported
```

### Example: OpenRouter

```env
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=your_openrouter_key
LLM_MODEL=openai/gpt-4o-mini
SEARCH_PROVIDER=auto
TAVILY_API_KEY=your_tavily_key   # optional; SerpAPI/Brave/Serper/Bing also supported
```

### Example: Local Ollama

```env
LLM_PROVIDER=ollama
LLM_MODEL=llama3.1
OLLAMA_BASE_URL=http://localhost:11434
SEARCH_PROVIDER=auto
TAVILY_API_KEY=your_tavily_key   # optional; SerpAPI/Brave/Serper/Bing also supported
```

### Example: any OpenAI-compatible provider

```env
LLM_PROVIDER=custom
LLM_BASE_URL=https://api.provider.com/v1
LLM_API_KEY=your_provider_key
LLM_MODEL=provider-model-name
SEARCH_PROVIDER=auto
TAVILY_API_KEY=your_tavily_key   # optional; SerpAPI/Brave/Serper/Bing also supported
```

All provider logic is centralized in `llm_factory.py`. Agents call only `get_llm()`, so future providers can be added in one file.

## Switching search providers from `.env` only

Tavily is no longer mandatory. Search logic is centralized in `search_factory.py`, and the rest of the pipeline calls only `search_web()`.

Default mode:

```env
SEARCH_PROVIDER=auto
```

`auto` picks the first available provider in this order:

```text
Tavily -> SerpAPI -> Brave -> Serper -> Bing -> DuckDuckGo fallback
```

Examples:

```env
# Tavily
SEARCH_PROVIDER=tavily
TAVILY_API_KEY=your_tavily_key

# SerpAPI
SEARCH_PROVIDER=serpapi
SERPAPI_API_KEY=your_serpapi_key

# Brave Search API
SEARCH_PROVIDER=brave
BRAVE_SEARCH_API_KEY=your_brave_key

# Serper
SEARCH_PROVIDER=serper
SERPER_API_KEY=your_serper_key

# Bing Web Search
SEARCH_PROVIDER=bing
BING_SEARCH_API_KEY=your_bing_key

# No-key demo fallback. Less reliable than paid/official APIs.
SEARCH_PROVIDER=duckduckgo
ALLOW_DUCKDUCKGO_FALLBACK=true

# Disable web search
SEARCH_PROVIDER=none
```

For custom search APIs, set:

```env
SEARCH_PROVIDER=custom
SEARCH_API_URL=https://your-search-api.example.com/search
SEARCH_API_KEY=your_optional_key
```

The custom endpoint should return JSON with `results`, `organic`, or `items` where each item has fields like `title`, `url`/`link`, and `snippet`/`description`.
