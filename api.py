"""FastAPI backend for ResearchGraph AI V2."""

from __future__ import annotations

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from config import API_AUTH_TOKEN, LLM_PROVIDER
from jobs import read_job, start_research_job
from llm_factory import get_model_name
from search_factory import resolve_search_provider
from pipeline import PipelineConfig, ResearchPipeline
from storage import get_run, list_runs

app = FastAPI(title="ResearchGraph AI V2", version="2.0.0")


def require_api_auth(
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> None:
    """Require a simple token when API_AUTH_TOKEN is configured."""
    if not API_AUTH_TOKEN:
        return
    bearer = f"Bearer {API_AUTH_TOKEN}"
    if authorization == bearer or x_api_key == API_AUTH_TOKEN:
        return
    raise HTTPException(status_code=401, detail="Missing or invalid API token")


class ResearchRequest(BaseModel):
    topic: str = Field(..., min_length=3)
    max_sources: int = Field(6, ge=2, le=10)
    async_job: bool = False


@app.get("/health")
def health():
    try:
        search_provider = resolve_search_provider()
    except Exception as exc:  # noqa: BLE001
        search_provider = f"misconfigured: {exc}"
    return {
        "status": "ok",
        "service": "ResearchGraph AI V2",
        "llm_provider": LLM_PROVIDER,
        "llm_model": get_model_name(),
        "search_provider": search_provider,
    }


@app.post("/research", dependencies=[Depends(require_api_auth)])
def research(request: ResearchRequest):
    if request.async_job:
        job_id = start_research_job(request.topic, request.max_sources)
        return {"job_id": job_id, "status": "queued"}
    return ResearchPipeline(PipelineConfig(max_sources=request.max_sources)).run(request.topic)


@app.get("/jobs/{job_id}", dependencies=[Depends(require_api_auth)])
def job_status(job_id: int):
    job = read_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.get("/runs", dependencies=[Depends(require_api_auth)])
def runs(limit: int = 20):
    return list_runs(limit=limit)


@app.get("/runs/{run_id}", dependencies=[Depends(require_api_auth)])
def run_detail(run_id: int):
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run
