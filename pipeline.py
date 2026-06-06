"""Main orchestration pipeline.

Uses LangGraph when installed. Falls back to an explicit sequential workflow so
Streamlit deployments stay simple and robust.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List

from agents import EvidenceAgent, PlannerAgent, RevisionAgent, VerifierAgent, WriterAgent
from config import DEFAULT_MAX_SOURCES, MAX_REVISIONS
from graph_workflow import ResearchGraphWorkflow
from memory import ResearchMemory
from scoring import overall_quality_scores
from storage import save_run
from tools import search_and_scrape


@dataclass
class PipelineConfig:
    max_sources: int = DEFAULT_MAX_SOURCES
    save_history: bool = True
    use_langgraph: bool = True
    auto_revise: bool = True
    user_id: int | None = None


ProgressCallback = Callable[[str, str, int, str], None]


class ResearchPipeline:
    def __init__(self, config: PipelineConfig | None = None, progress_callback: ProgressCallback | None = None) -> None:
        self.config = config or PipelineConfig()
        self.progress_callback = progress_callback
        self.planner = PlannerAgent()
        self.evidence_agent = EvidenceAgent()
        self.writer = WriterAgent()
        self.verifier = VerifierAgent()
        self.reviser = RevisionAgent()
        try:
            self.memory = ResearchMemory(user_id=self.config.user_id)
        except TypeError:
            self.memory = ResearchMemory()
            self.memory.user_id = self.config.user_id

    def _emit_progress(self, step: str, status: str, items: int = 0, note: str = "") -> None:
        if self.progress_callback:
            self.progress_callback(step, status, items, note)

    def _trace(self, trace: List[Dict[str, Any]], step: str, status: str, items: int = 0, note: str = "") -> None:
        trace.append({"step": step, "status": status, "items": items, "note": note, "timestamp": round(time.time(), 2)})
        self._emit_progress(step, status, items, note)

    def run(self, topic: str) -> Dict[str, Any]:
        if not topic or not topic.strip():
            raise ValueError("Topic cannot be empty.")

        # Prefer real LangGraph architecture, but don't break simple deployments.
        if self.config.use_langgraph:
            try:
                workflow = ResearchGraphWorkflow(
                    progress_callback=self.progress_callback,
                    user_id=self.config.user_id,
                )
                result = dict(workflow.run_with_langgraph(topic.strip(), max_sources=self.config.max_sources))
                result["orchestration"] = "langgraph"
                return result
            except Exception as exc:  # noqa: BLE001
                # Fall through to sequential mode and record the fallback.
                fallback_note = f"LangGraph fallback used: {exc}"
            else:
                fallback_note = ""
        else:
            fallback_note = "Sequential mode selected."

        started = time.time()
        trace: List[Dict[str, Any]] = []
        self._trace(trace, "orchestration", "fallback", note=fallback_note)

        self._emit_progress("memory_retrieval", "running", note="Checking previous research memory.")
        memory_context = self.memory.search(topic.strip(), limit=4)
        self._trace(trace, "memory_retrieval", "done", len(memory_context), f"mode={self.memory.mode}")

        self._emit_progress("planner", "running", note="Planning research questions and search queries.")
        plan = self.planner.run(topic.strip())
        self._trace(trace, "planner", "done", len(plan.get("search_queries", [])))

        self._emit_progress("search_and_scrape", "running", note="Searching and reading source pages.")
        sources = search_and_scrape(plan.get("search_queries", [topic]), max_sources=self.config.max_sources)
        self._trace(trace, "search_and_scrape", "done", len(sources))

        evidence = []
        for index, source in enumerate(sources, start=1):
            self._emit_progress(
                "evidence_extraction",
                "running",
                index - 1,
                f"Reading {source.get('source_id', index)} of {len(sources)}.",
            )
            evidence.append(self.evidence_agent.run(topic, source))
            self._emit_progress(
                "evidence_extraction",
                "running",
                index,
                f"Completed {index} of {len(sources)} sources.",
            )
        self._trace(trace, "evidence_extraction", "done", len(evidence))

        self._emit_progress("writer", "running", note="Writing the cited research report.")
        report = self.writer.run(topic, plan, evidence, memory_context)
        self._trace(trace, "writer", "done", 1)

        self._emit_progress("verifier", "running", note="Checking citations, evidence quality, and freshness.")
        verifier = self.verifier.run(topic, report, evidence)
        scores = overall_quality_scores(report, evidence, verifier)
        self._trace(trace, "verifier", "done", len(verifier.get("recommended_fixes", []) or []), verifier.get("verdict", ""))

        revisions = 0
        while self.config.auto_revise and revisions < MAX_REVISIONS and (
            verifier.get("verdict") in {"fail", "needs_review"} or scores.get("overall_score", 0) < 70
        ):
            revisions += 1
            self._emit_progress("revision", "running", revisions, f"Revision pass {revisions}.")
            report = self.reviser.run(topic, report, verifier, evidence)
            self._trace(trace, "revision", "done", revisions)
            self._emit_progress("verifier", "running", note=f"Re-checking revised report, pass {revisions}.")
            verifier = self.verifier.run(topic, report, evidence)
            scores = overall_quality_scores(report, evidence, verifier)
            self._trace(trace, "verifier_after_revision", "done", len(verifier.get("recommended_fixes", []) or []), verifier.get("verdict", ""))

        if revisions == 0:
            self._emit_progress("revision", "skipped", note="No revision needed.")

        payload: Dict[str, Any] = {
            "topic": topic,
            "plan": plan,
            "memory_context": memory_context,
            "memory_mode": self.memory.mode,
            "sources": sources,
            "evidence": evidence,
            "report": report,
            "scores": scores,
            "verifier": verifier,
            "trace": trace,
            "revision_count": revisions,
            "runtime_seconds": round(time.time() - started, 2),
            "orchestration": "sequential_fallback",
        }

        if self.config.save_history:
            self._emit_progress("save_history_and_memory", "running", note="Saving run and memory.")
            payload["run_id"] = save_run(topic, payload, user_id=self.config.user_id)
            self.memory.add_run(topic, payload)
            self._trace(trace, "save_history_and_memory", "done", 1, f"run_id={payload['run_id']}")

        return payload


def run_research_pipeline(topic: str, max_sources: int = DEFAULT_MAX_SOURCES) -> Dict[str, Any]:
    return ResearchPipeline(PipelineConfig(max_sources=max_sources)).run(topic)


if __name__ == "__main__":
    topic_input = input("Enter research topic: ").strip()
    result = run_research_pipeline(topic_input)
    print(result["report"])
    print(result["scores"])
