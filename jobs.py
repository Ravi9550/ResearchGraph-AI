"""Simple job runner for FastAPI demos without requiring Celery.

This gives production-style job status endpoints while still being easy to deploy.
For real distributed workers, use tasks.py with Celery + Redis.
"""

from __future__ import annotations

import threading

from pipeline import PipelineConfig, ResearchPipeline
from storage import create_job, get_job, update_job


def _run_job(job_id: int, topic: str, max_sources: int) -> None:
    update_job(job_id, "running")
    try:
        result = ResearchPipeline(PipelineConfig(max_sources=max_sources)).run(topic)
        update_job(job_id, "completed", result=result)
    except Exception as exc:  # noqa: BLE001
        update_job(job_id, "failed", error=str(exc))


def start_research_job(topic: str, max_sources: int = 6) -> int:
    job_id = create_job(topic)
    thread = threading.Thread(target=_run_job, args=(job_id, topic, max_sources), daemon=True)
    thread.start()
    return job_id


def read_job(job_id: int):
    return get_job(job_id)
