"""Streamlit UI for ResearchGraph AI V2."""

from __future__ import annotations

import importlib
import json
import logging
import os
import re
import sys
import traceback
from html import escape
from pathlib import Path
from urllib.parse import urlparse
import streamlit as st
from dotenv import load_dotenv

PROJECT_ENV_PATH = Path(__file__).with_name(".env")
LOG_DIR = Path(__file__).with_name("logs")
LOG_DIR.mkdir(exist_ok=True)
ERROR_LOG_PATH = LOG_DIR / "research_errors.log"
load_dotenv(PROJECT_ENV_PATH, override=True)

for proxy_name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
    proxy_value = os.getenv(proxy_name, "").strip().rstrip("/")
    if proxy_value in {"http://127.0.0.1:9", "https://127.0.0.1:9"}:
        os.environ.pop(proxy_name, None)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stderr), logging.FileHandler(ERROR_LOG_PATH, encoding="utf-8")],
    force=True,
)
logger = logging.getLogger("researchgraph")

import agents as agents_module
import config as app_config
import exporters as exporters_module
import graph_workflow as graph_workflow_module
import llm_factory as llm_factory_module
import memory as memory_module
import pipeline as pipeline_module
import search_factory as search_factory_module
import storage as storage_module
import tools as tools_module

app_config = importlib.reload(app_config)
llm_factory_module = importlib.reload(llm_factory_module)
search_factory_module = importlib.reload(search_factory_module)
storage_module = importlib.reload(storage_module)
memory_module = importlib.reload(memory_module)
agents_module = importlib.reload(agents_module)
tools_module = importlib.reload(tools_module)
graph_workflow_module = importlib.reload(graph_workflow_module)
exporters_module = importlib.reload(exporters_module)
pipeline_module = importlib.reload(pipeline_module)

PipelineConfig = pipeline_module.PipelineConfig
ResearchPipeline = pipeline_module.ResearchPipeline
authenticate_user = storage_module.authenticate_user
create_user = storage_module.create_user
delete_run = storage_module.delete_run
get_run = storage_module.get_run
list_runs = storage_module.list_runs
available_search_providers = search_factory_module.available_search_providers
resolve_search_provider = search_factory_module.resolve_search_provider
get_model_name = llm_factory_module.get_model_name
export_pdf_bytes = exporters_module.export_pdf_bytes

st.set_page_config(page_title="ResearchGraph AI V2", layout="wide")

st.markdown(
    """
<style>
    .main-header {
        max-width: 560px;
        margin: 0 auto 1.15rem auto;
        padding: 1.25rem 1rem 0.65rem;
        background: transparent;
        border: 0;
        text-align: center;
    }
    .main-header h1 {
        margin: 0;
        color: #0f172a;
        font-size: 2rem;
        font-weight: 850;
        letter-spacing: 0;
        line-height: 1.12;
    }
    .main-header p {
        margin: 0.45rem 0 0;
        color: #64748b;
        font-size: 0.98rem;
        line-height: 1.42;
    }
    .source-card {
        padding: 0.9rem 1rem;
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        margin-bottom: 0.75rem;
        background: #ffffff;
    }
    .small-muted { color: #6b7280; font-size: 0.88rem; }
    .agent-status-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
        gap: 0.7rem;
        margin: 0.75rem 0 1rem;
    }
    .agent-card {
        min-height: 118px;
        padding: 0.8rem;
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        background: #ffffff;
    }
    .agent-card-top {
        display: flex;
        justify-content: space-between;
        gap: 0.5rem;
        margin-bottom: 0.55rem;
    }
    .agent-name { color: #111827; font-weight: 700; line-height: 1.2; }
    .agent-note { color: #4b5563; font-size: 0.86rem; line-height: 1.32; min-height: 2.2rem; }
    .agent-items { color: #6b7280; font-size: 0.82rem; margin-top: 0.55rem; }
    .agent-status {
        display: inline-block;
        min-width: 5.2rem;
        padding: 0.16rem 0.42rem;
        border-radius: 6px;
        font-weight: 700;
        text-align: center;
        font-size: 0.78rem;
    }
    .agent-waiting { color: #6b7280; background: #f3f4f6; }
    .agent-running { color: #075985; background: #e0f2fe; }
    .agent-completed { color: #166534; background: #dcfce7; }
    .agent-skipped { color: #854d0e; background: #fef3c7; }
    .agent-failed { color: #991b1b; background: #fee2e2; }
    div[data-testid="stForm"] { border: 0; padding: 0; background: transparent; }
    div[data-testid="stForm"] label { color: #374151; font-size: 0.9rem; font-weight: 650; }
    .auth-brand {
        color: #111827;
        font-size: 1.55rem;
        font-weight: 800;
        line-height: 1.15;
        margin-bottom: 0.2rem;
        text-align: center;
    }
    .auth-subtitle {
        color: #6b7280;
        font-size: 0.92rem;
        line-height: 1.35;
        margin-bottom: 1rem;
        text-align: center;
    }
    .auth-switch { color: #6b7280; font-size: 0.9rem; line-height: 2.35rem; text-align: right; }
    div[data-testid="stButton"] button[kind="tertiary"] {
        color: #2563eb !important;
        font-weight: 800 !important;
    }
    div[data-testid="stButton"] button[kind="tertiary"]:hover {
        color: #1d4ed8 !important;
        text-decoration: underline;
    }
    /* Force sidebar history items to stay on one line */
    section[data-testid="stSidebar"] div[data-testid="column"] {
        flex-wrap: nowrap !important;
    }
    section[data-testid="stSidebar"] div[data-testid="column"]:last-child {
        flex-shrink: 0;
        width: auto !important;
    }
    div[data-testid="stHorizontalBlock"] {
        flex-wrap: nowrap !important;
    }
    /* Ensure the popover button does not wrap and stays compact */
    button[data-testid="baseButton-secondary"] {
        white-space: nowrap !important;
    }
</style>
""",
    unsafe_allow_html=True,
)

st.markdown(
    """
<div class="main-header">
  <h1>ResearchGraph AI V2</h1>
  <p>Multi-agent research with citations, verifier scoring, memory, history, and exports.</p>
</div>
""",
    unsafe_allow_html=True,
)


def make_history_title(text: str, max_words: int = 7) -> str:
    cleaned = re.sub(r"\s+", " ", str(text or "")).strip()
    cleaned = re.sub(r"^(research|analyze|analyse|explain|write|create|compare)\s+", "", cleaned, flags=re.I)
    if not cleaned:
        return "Untitled research"
    return " ".join(cleaned.split()[:max_words]).strip(" .,:;!?-")[:48] or "Untitled research"


def render_auth() -> dict:
    if st.session_state.get("user"):
        return st.session_state["user"]

    st.session_state.setdefault("auth_mode", "login")
    _, center, _ = st.columns([1, 0.95, 1])
    with center:
        with st.container(border=True):
            if st.session_state["auth_mode"] == "login":
                st.markdown(
                    '<div class="auth-brand">Welcome back</div>'
                    '<div class="auth-subtitle">Login to continue your research workspace.</div>',
                    unsafe_allow_html=True,
                )
                with st.form("login_form", enter_to_submit=False):
                    username = st.text_input("Username", key="login_username")
                    password = st.text_input("Password", type="password", key="login_password")
                    submitted = st.form_submit_button("Login", type="primary", use_container_width=True)
                if submitted:
                    user = authenticate_user(username, password)
                    if user:
                        st.session_state["user"] = user
                        st.rerun()
                    st.error("Invalid username or password.")

                prompt_col, action_col = st.columns([1.55, 1])
                with prompt_col:
                    st.markdown('<div class="auth-switch">New user?</div>', unsafe_allow_html=True)
                with action_col:
                    if st.button("Register", key="switch_to_register", type="tertiary"):
                        st.session_state["auth_mode"] = "register"
                        st.rerun()
            else:
                st.markdown(
                    '<div class="auth-brand">Create account</div>'
                    '<div class="auth-subtitle">Register to keep your research history separate.</div>',
                    unsafe_allow_html=True,
                )
                with st.form("register_form", enter_to_submit=False):
                    username = st.text_input("Username", key="register_username")
                    password = st.text_input("Password", type="password", key="register_password")
                    confirm = st.text_input("Confirm password", type="password", key="register_confirm")
                    submitted = st.form_submit_button("Create account", type="primary", use_container_width=True)
                if submitted:
                    if password != confirm:
                        st.error("Passwords do not match.")
                    else:
                        try:
                            user_id = create_user(username, password)
                            st.session_state["user"] = {"id": user_id, "username": username.strip().lower()}
                            st.rerun()
                        except ValueError as exc:
                            st.error(str(exc))

                prompt_col, action_col = st.columns([1.8, 1])
                with prompt_col:
                    st.markdown('<div class="auth-switch">Already have an account?</div>', unsafe_allow_html=True)
                with action_col:
                    if st.button("Login", key="switch_to_login", type="tertiary"):
                        st.session_state["auth_mode"] = "login"
                        st.rerun()

    st.stop()


current_user = render_auth()


def _safe_external_url(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(url)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return url
    return None


def _source_url_map(result: dict) -> dict[str, str]:
    source_map = {}
    for source in result.get("sources", []):
        source_id = str(source.get("source_id", "")).strip()
        url = _safe_external_url(source.get("url"))
        if source_id and url:
            source_map[source_id] = url
    return source_map


def _repair_collapsed_tables(markdown: str) -> str:
    def repair_line(raw_line: str) -> list[str]:
        stripped = raw_line.strip()
        heading = ""
        table_text = stripped
        if not stripped.startswith("|") and "|" in stripped:
            prefix, rest = stripped.split("|", 1)
            if prefix.strip().lower() in {"evidence table", "source list"}:
                heading = f"### {prefix.strip()}"
                table_text = "|" + rest

        pieces = [piece.strip() for piece in table_text.strip("|").split("|")]
        pieces = [piece for piece in pieces if piece]
        lower_pieces = [piece.lower() for piece in pieces]
        if {"finding", "evidence", "source"}.issubset(set(lower_pieces[:3])):
            width = 3
        elif {"source", "summary"}.issubset(set(lower_pieces[:2])):
            width = 2
        elif pieces and set(pieces[0].replace(" ", "")) <= {"-"}:
            width = 0
            for piece in pieces:
                if set(piece.replace(" ", "")) <= {"-"}:
                    width += 1
                else:
                    break
            if width not in {2, 3}:
                return [raw_line]
        else:
            return [raw_line]

        repaired = []
        if heading:
            repaired.extend([heading, ""])
        chunks = [pieces[index : index + width] for index in range(0, len(pieces), width)]
        first_is_separator = bool(chunks) and all(set(cell.replace(" ", "")) <= {"-"} for cell in chunks[0])
        start_index = 0
        if first_is_separator:
            repaired.append("| " + " | ".join(["---"] * width) + " |")
            start_index = 1
        for index, chunk in enumerate(chunks[start_index:], start=start_index):
            if len(chunk) != width:
                continue
            repaired.append("| " + " | ".join(chunk) + " |")
            if index == 0 and not first_is_separator and (not heading or len(chunks) > 1):
                next_chunk = chunks[1] if len(chunks) > 1 else []
                has_separator = bool(next_chunk) and all(set(cell.replace(" ", "")) <= {"-"} for cell in next_chunk)
                if not has_separator:
                    repaired.append("| " + " | ".join(["---"] * width) + " |")
        return repaired

    lines = []
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if line.count("|") >= 4 and ("| |" in line or line.lower().startswith(("evidence table|", "source list|"))):
            lines.extend(repair_line(raw_line))
        else:
            lines.append(raw_line)
    return "\n".join(lines)


def _link_report_sources(markdown: str, result: dict) -> str:
    source_map = _source_url_map(result)
    if not source_map:
        return markdown

    def replace_citation(match: re.Match[str]) -> str:
        source_id = match.group(1)
        url = source_map.get(source_id)
        return f"[[{source_id}]]({url})" if url else match.group(0)

    markdown = re.sub(r"\[(S\d+)\]", replace_citation, markdown)

    def replace_table_source(match: re.Match[str]) -> str:
        prefix, source_id, suffix = match.groups()
        url = source_map.get(source_id)
        return f"{prefix}[{source_id}]({url}){suffix}" if url else match.group(0)

    return re.sub(r"(\|\s*)(S\d+)(\s*\|)", replace_table_source, markdown)


def format_report_markdown(result: dict) -> str:
    markdown = result.get("report", "No report generated.")
    markdown = _repair_collapsed_tables(markdown)
    return _link_report_sources(markdown, result)


def friendly_pipeline_error(exc: Exception) -> tuple[str, str]:
    text = str(exc) or exc.__class__.__name__
    lowered = text.lower()
    if any(term in lowered for term in ("rate limit", "ratelimit", "429", "too many requests", "quota")):
        return (
            "Provider limit reached",
            "Your AI provider rate limit or quota was reached. Please wait, add credits, or switch provider/model in `.env`.",
        )
    if any(term in lowered for term in ("401", "403", "unauthorized", "forbidden", "invalid api key", "api key")):
        return (
            "Provider authentication failed",
            "The API key is missing, invalid, or not allowed for this provider. Check the relevant key in `.env`.",
        )
    if any(term in lowered for term in ("model", "not found", "does not exist", "unsupported")):
        return (
            "Model configuration issue",
            "The selected model may be unavailable for your provider. Update the provider model name in `.env`.",
        )
    if any(term in lowered for term in ("connection", "connecterror", "timeout", "timed out", "winerror 10061", "proxy")):
        return (
            "Connection problem",
            "The app could not reach the configured provider. Check internet access, proxy settings, or the provider status.",
        )
    if any(term in lowered for term in ("json", "parse", "schema")):
        return (
            "Response format issue",
            "The provider returned an unexpected response format. Try running again or switch to a stronger model in `.env`.",
        )
    return (
        "Research failed",
        "Something went wrong while running the research pipeline. The full technical details were saved in the server logs.",
    )


AGENT_STEPS = [
    ("planner", "Planner Agent"),
    ("memory_retrieval", "Memory Reader"),
    ("search_and_scrape", "Source Reader"),
    ("evidence_extraction", "Evidence Reader"),
    ("writer", "Writer Agent"),
    ("verifier", "Verifier Agent"),
    ("revision", "Revision Agent"),
    ("save_history_and_memory", "Save Agent"),
]


def build_live_progress_ui():
    step_order = [step for step, _ in AGENT_STEPS]
    labels = dict(AGENT_STEPS)
    states = {step: {"status": "waiting", "items": 0, "note": "Waiting"} for step in step_order}
    table_slot = st.empty()
    progress_slot = st.empty()
    caption_slot = st.empty()
    current_step_ref = {"step": None}

    def normalize_step(step: str) -> str:
        return "verifier" if step == "verifier_after_revision" else step

    def display_status(status: str) -> str:
        return {
            "done": "Completed",
            "running": "Running",
            "waiting": "Waiting",
            "skipped": "Skipped",
            "failed": "Failed",
            "fallback": "Completed",
        }.get(status, status.title())

    def redraw(current_step: str | None = None) -> None:
        completed = sum(1 for state in states.values() if state["status"] in {"done", "skipped", "fallback"})
        progress_slot.progress(completed / len(step_order), text=f"{completed} of {len(step_order)} tasks completed")
        cards = []
        for step in step_order:
            state = states[step]
            status = state["status"]
            css_status = "completed" if status in {"done", "fallback"} else status
            cards.append(
                '<div class="agent-card">'
                '<div class="agent-card-top">'
                f'<div class="agent-name">{escape(labels[step])}</div>'
                f'<span class="agent-status agent-{css_status}">{display_status(status)}</span>'
                "</div>"
                f'<div class="agent-note">{escape(str(state.get("note") or ""))}</div>'
                f'<div class="agent-items">Items: {escape(str(state.get("items", 0)))}</div>'
                "</div>"
            )
        table_slot.markdown('<div class="agent-status-grid">' + "\n".join(cards) + "</div>", unsafe_allow_html=True)
        if current_step:
            caption_slot.caption(f"Currently running: {labels.get(current_step, current_step)}")

    def update(step: str, status: str, items: int = 0, note: str = "") -> None:
        step = normalize_step(step)
        if step not in states:
            return
        if status == "running":
            current_step_ref["step"] = step
        elif current_step_ref["step"] == step and status in {"done", "skipped", "fallback"}:
            current_step_ref["step"] = None
        states[step] = {"status": status, "items": items, "note": note or display_status(status)}
        update.current_step = current_step_ref["step"]
        redraw(step if status == "running" else None)

    redraw()
    update.current_step = None
    return update


with st.sidebar:
    st.session_state.setdefault("active_run_id", None)
    selected_run = None

    st.subheader("Research")
    if st.button("New research", type="primary", use_container_width=True):
        st.session_state["active_run_id"] = None
        st.rerun()

    history = list_runs(limit=20, user_id=current_user["id"])
    if history:
        st.caption("Recent")
        for run in history:
            label = make_history_title(run.get("title") or run.get("topic", ""))
            # Use columns with a wider second column (0.15 ratio) to ensure the menu button fits
            col1, col2 = st.columns([0.85, 0.15], gap="small")
            with col1:
                if st.button(label, key=f"history_run_{run['id']}", use_container_width=True):
                    st.session_state["active_run_id"] = run["id"]
                    st.rerun()
            with col2:
                # Popover menu for delete option
                with st.popover("⋮", use_container_width=False):
                    if st.button("Delete", key=f"delete_run_{run['id']}", use_container_width=True):
                        delete_run(run["id"], user_id=current_user["id"])
                        if st.session_state.get("active_run_id") == run["id"]:
                            st.session_state["active_run_id"] = None
                        st.rerun()
    else:
        st.caption("No saved runs yet.")

    if st.session_state.get("active_run_id"):
        selected_run = get_run(st.session_state["active_run_id"], user_id=current_user["id"])

    st.markdown("---")
    st.header("Configuration")
    max_sources = st.slider("Max sources", min_value=2, max_value=10, value=6)
    auto_revise = st.toggle("Auto-revise weak reports", value=True)

    st.markdown("---")
    st.subheader("LLM Provider")
    st.caption(f"Provider: `{app_config.LLM_PROVIDER}`")
    st.caption(f"Model: `{app_config.LLM_MODEL or get_model_name()}`")

    st.markdown("---")
    st.subheader("Search Provider")
    try:
        st.caption(f"Active: `{resolve_search_provider()}`")
        available = [name for name, ok in available_search_providers().items() if ok and name != "none"]
        st.caption("Available: " + (", ".join(available) if available else "none"))
    except Exception as exc:
        st.caption(f"Search config issue: {exc}")

    st.markdown("---")
    st.subheader("Account")
    st.caption(f"Signed in as `{current_user['username']}`")
    if st.button("Logout", use_container_width=True):
        st.session_state.pop("user", None)
        st.rerun()


def render_result(result: dict) -> None:
    scores = result.get("scores", {})
    verifier = result.get("verifier", {})

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Quality", scores.get("overall_score", 0))
    c2.metric("Verifier", verifier.get("verdict", "unknown"))
    c3.metric("Sources", len(result.get("sources", [])))
    c4.metric("Memory", result.get("memory_mode", "none"))
    c5.metric("Runtime", f"{result.get('runtime_seconds', 0)}s")
    st.caption(f"Orchestration: {result.get('orchestration', 'unknown')} | Revisions: {result.get('revision_count', 0)}")

    tabs = st.tabs(["Report", "Evidence", "Verifier", "Evaluation", "Memory", "Export", "Raw"])

    with tabs[0]:
        st.markdown(format_report_markdown(result))

    with tabs[1]:
        st.subheader("Sources")
        for source in result.get("sources", []):
            url = _safe_external_url(source.get("url"))
            link_html = f'<a href="{escape(url, quote=True)}" target="_blank" rel="noopener noreferrer">Open source</a>' if url else ""
            st.markdown(
                f"""
<div class="source-card">
<b>{escape(str(source.get('source_id', '')))} - {escape(str(source.get('title', 'Untitled')))}</b><br/>
<span class="small-muted">{escape(str(source.get('url', '')))}</span><br/>
<span class="small-muted">Domain: {escape(str(source.get('domain', '')))} | Date: {escape(str(source.get('published_at', '')))} | Scrape: {escape(str(source.get('scrape_status', '')))}</span><br/>
{link_html}
</div>
""",
                unsafe_allow_html=True,
            )

        st.subheader("Extracted Evidence")
        for item in result.get("evidence", []):
            title = f"{item.get('source_id')} | {item.get('title', 'Untitled')} | confidence {item.get('confidence', 'n/a')}"
            with st.expander(title):
                url = _safe_external_url(item.get("url"))
                if url:
                    st.link_button("Open evidence source", url)
                st.write(item.get("summary", ""))
                st.markdown("**Key points**")
                for point in item.get("key_points", []):
                    st.markdown(f"- {point}")
                if item.get("numbers_or_dates"):
                    st.markdown("**Numbers / dates**")
                    for value in item.get("numbers_or_dates", []):
                        st.markdown(f"- {value}")
                st.markdown("**Limitations**")
                for limitation in item.get("limitations", []):
                    st.markdown(f"- {limitation}")

    with tabs[2]:
        st.json(verifier)

    with tabs[3]:
        st.json(scores)

    with tabs[4]:
        context = result.get("memory_context", [])
        if context:
            for item in context:
                with st.expander(f"score {item.get('score')} | {item.get('topic', 'memory')}"):
                    st.write(item.get("text", "")[:1200])
                    st.json(item.get("metadata", {}))
        else:
            st.info("No related memory found yet.")

    with tabs[5]:
        try:
            st.download_button(
                "Download PDF",
                data=export_pdf_bytes(result),
                file_name="research_report.pdf",
                mime="application/pdf",
            )
        except Exception as exc:
            st.warning(f"PDF generation failed: {exc}")
        st.download_button(
            "Download JSON",
            data=json.dumps(result, indent=2),
            file_name="research_result.json",
            mime="application/json",
        )

    with tabs[6]:
        st.code(json.dumps(result, indent=2), language="json")


if selected_run:
    render_result(selected_run)
else:
    st.subheader("New research")
    topic = st.text_area(
        "Research topic",
        placeholder="Example: Risks of using AI-generated medical advice",
        height=110,
    )

    run = st.button("Run verified multi-agent research", type="primary", use_container_width=True)
    if run:
        if not topic.strip():
            st.warning("Please enter a research topic.")
        else:
            status = st.status("Running research pipeline...", expanded=True)
            progress_callback = build_live_progress_ui()
            try:
                status.write("Preparing live agent status...")
                pipeline = ResearchPipeline(
                    PipelineConfig(
                        max_sources=max_sources,
                        use_langgraph=False,
                        auto_revise=auto_revise,
                        user_id=current_user["id"],
                    )
                )
                pipeline.progress_callback = progress_callback
                status.write("Agents are running. Watch the live status cards below.")
                result = pipeline.run(topic.strip())
                if result.get("run_id"):
                    st.session_state["active_run_id"] = result["run_id"]
                status.update(label="Research completed", state="complete", expanded=False)
                st.rerun()
            except Exception as exc:
                detailed_error = traceback.format_exc()
                failed_step = getattr(progress_callback, "current_step", None) or "planner"
                logger.error(
                    "Research pipeline failed (provider=%s, model=%s, failed_step=%s)\n%s",
                    app_config.LLM_PROVIDER,
                    app_config.LLM_MODEL or get_model_name(),
                    failed_step,
                    detailed_error,
                )
                error_title, error_message = friendly_pipeline_error(exc)
                progress_callback(failed_step, "failed", note=error_title)
                status.update(label="Research failed", state="error")
                st.error(error_title)
                st.info(error_message)