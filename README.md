# ResearchGraph AI

ResearchGraph AI is a multi-agent research assistant that turns a topic into a cited research report. It plans the research, searches public sources, extracts evidence, writes a structured report, verifies claims, scores quality, and saves the result to user history.

The app is built for a simple live deployment with Streamlit, SQLite, and provider-based LLM/search configuration through environment variables.

## Features

- User login and registration
- Recent research history per user
- Live agent status while a research run is executing
- Web search with multiple provider options
- Source scraping with snippet fallback
- Evidence extraction from each source
- Citation-backed report writing
- Verifier pass for unsupported claims, citation issues, contradictions, and freshness risks
- Optional automatic revision when quality is weak
- Deterministic quality scoring
- SQLite-backed research memory
- PDF and JSON export
- Optional FastAPI backend

## How It Works

```text
User topic
  -> Planner Agent
  -> Memory Reader
  -> Search and Source Reader
  -> Evidence Reader
  -> Writer Agent
  -> Verifier Agent
  -> Revision Agent, when needed
  -> Quality Scoring
  -> Save to History and Memory
```

The Streamlit interface uses the sequential pipeline by default for easier deployment and debugging. The codebase also contains a LangGraph workflow implementation, but the deployed app does not depend on it being enabled.

## Tech Stack

- Python
- Streamlit
- FastAPI
- SQLite
- LangChain
- LangGraph-compatible workflow
- ReportLab for PDF export
- Provider adapters for Gemini, OpenAI, Anthropic, Groq, OpenRouter, Together, Ollama, and custom OpenAI-compatible APIs

## Project Structure

```text
app.py              Streamlit UI
api.py              Optional FastAPI endpoints
pipeline.py         Main research orchestration
graph_workflow.py   LangGraph-compatible workflow
agents.py           Planner, evidence, writer, verifier, revision agents
search_factory.py   Search provider routing
tools.py            Search, scraping, cache, and source utilities
memory.py           SQLite-backed research memory
storage.py          Users, history, jobs, and memory persistence
scoring.py          Deterministic report quality scoring
exporters.py        PDF and JSON export helpers
llm_factory.py      LLM provider selection
config.py           Environment-based configuration
```

## Local Setup

Create and activate a virtual environment:

```bash
python -m venv venv
```

Windows:

```bash
venv\Scripts\activate
```

macOS/Linux:

```bash
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create a local `.env` file. Do not commit this file to GitHub.

```env
LLM_PROVIDER=groq
GROQ_API_KEY=your_groq_key
GROQ_MODEL=llama-3.1-8b-instant

SEARCH_PROVIDER=auto
TAVILY_API_KEY=your_tavily_key

DEFAULT_MAX_SOURCES=6
MAX_REVISIONS=1
```

Run the Streamlit app:

```bash
streamlit run app.py
```

Open the local URL shown in the terminal, usually:

```text
http://localhost:8501
```

## FastAPI Backend

The Streamlit app is the main interface. FastAPI is included for API access and integration experiments.

Run it with:

```bash
uvicorn api:app --reload
```

Open:

```text
http://127.0.0.1:8000/docs
```

For public API deployment, set:

```env
API_AUTH_TOKEN=your_long_random_token
```

Protected API routes accept either:

```text
Authorization: Bearer your_long_random_token
```

or:

```text
X-API-Key: your_long_random_token
```

## LLM Configuration

All model switching is controlled through environment variables. The app reads `LLM_PROVIDER` and routes model creation through `llm_factory.py`.

Supported providers:

```env
LLM_PROVIDER=gemini
LLM_PROVIDER=openai
LLM_PROVIDER=anthropic
LLM_PROVIDER=groq
LLM_PROVIDER=openrouter
LLM_PROVIDER=together
LLM_PROVIDER=ollama
LLM_PROVIDER=custom
```

Examples:

```env
# Groq
LLM_PROVIDER=groq
GROQ_API_KEY=your_groq_key
LLM_MODEL=llama-3.1-8b-instant
```

```env
# OpenRouter
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=your_openrouter_key
LLM_MODEL=openai/gpt-4o-mini
```

```env
# Gemini
LLM_PROVIDER=gemini
GOOGLE_API_KEY=your_gemini_key
LLM_MODEL=gemini-2.0-flash
```

```env
# Custom OpenAI-compatible provider
LLM_PROVIDER=custom
LLM_BASE_URL=https://api.provider.com/v1
LLM_API_KEY=your_provider_key
LLM_MODEL=provider-model-name
```

If `LLM_MODEL` is blank, the provider-specific default from `config.py` is used.

## Search Configuration

Search provider selection is controlled by `SEARCH_PROVIDER`.

```env
SEARCH_PROVIDER=auto
```

`auto` picks the first configured provider in this order:

```text
Tavily -> SerpAPI -> Brave -> Serper -> Bing -> DuckDuckGo fallback
```

Examples:

```env
SEARCH_PROVIDER=tavily
TAVILY_API_KEY=your_tavily_key
```

```env
SEARCH_PROVIDER=serpapi
SERPAPI_API_KEY=your_serpapi_key
```

```env
SEARCH_PROVIDER=brave
BRAVE_SEARCH_API_KEY=your_brave_key
```

```env
SEARCH_PROVIDER=duckduckgo
ALLOW_DUCKDUCKGO_FALLBACK=true
```

DuckDuckGo is useful for quick testing, but a dedicated search API is more reliable for live demos.

## Deployment

The simplest deployment target is Streamlit Community Cloud.

1. Push the repository to GitHub.
2. Create a new Streamlit app.
3. Select the repository and branch.
4. Set the main file path to:

```text
app.py
```

5. Add secrets in Streamlit's TOML secrets editor:

```toml
LLM_PROVIDER = "groq"
GROQ_API_KEY = "your_groq_key"
GROQ_MODEL = "llama-3.1-8b-instant"

SEARCH_PROVIDER = "auto"
TAVILY_API_KEY = "your_tavily_key"

DEFAULT_MAX_SOURCES = "6"
MAX_REVISIONS = "1"
```

Do not upload `.env`, local databases, logs, exports, or virtual environments.

## Data Storage

The app uses SQLite for:

- Users
- Research history
- Saved run payloads
- Memory snippets
- Search cache

This keeps local setup simple. On platforms with ephemeral storage, such as some free hosting environments, user accounts and history may reset after redeploys or restarts. For long-term production use, move storage to a managed database such as Postgres or Supabase.

## Limitations

- Generated reports depend on the quality of retrieved sources and model output.
- The verifier reduces unsupported claims but cannot guarantee perfect factual accuracy.
- Some websites block scraping; the pipeline falls back to search snippets when needed.
- Free or low-cost LLM/search providers may rate-limit requests.
- SQLite is not ideal for large multi-user production deployments.
- Local Streamlit deployments are not a replacement for a full production auth and database stack.

## Development Check

Run the offline smoke test:

```bash
python tests_dummy.py
```

This test does not call external LLM or search APIs.

## Security Notes

- Never commit `.env`.
- Rotate API keys if they were exposed in logs, screenshots, commits, or chat.
- Use Streamlit Secrets or hosting environment variables for live deployment.
- Set `API_AUTH_TOKEN` before exposing the FastAPI backend publicly.
