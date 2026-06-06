"""LangGraph workflow for ResearchGraph AI V2.

The project runs even when LangGraph is not installed by using a sequential fallback
from pipeline.py. When installed, this module gives you the resume-worthy graph:
planner -> search -> evidence -> write -> verify -> revise if needed -> save.
"""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, TypedDict

from agents import EvidenceAgent, PlannerAgent, RevisionAgent, VerifierAgent, WriterAgent
from config import MAX_REVISIONS
from memory import ResearchMemory
from scoring import overall_quality_scores
from storage import save_run
from tools import search_and_scrape


class ResearchState(TypedDict, total=False):
    topic: str
    user_id: int
    max_sources: int
    plan: Dict[str, Any]
    memory_context: List[Dict[str, Any]]
    sources: List[Dict[str, Any]]
    evidence: List[Dict[str, Any]]
    report: str
    verifier: Dict[str, Any]
    scores: Dict[str, Any]
    revision_count: int
    trace: List[Dict[str, Any]]
    runtime_seconds: float
    run_id: int
    memory_mode: str


def add_trace(state: ResearchState, step: str, status: str, items: int = 0, note: str = "") -> None:
    state.setdefault("trace", []).append(
        {"step": step, "status": status, "items": items, "note": note, "timestamp": round(time.time(), 2)}
    )


ProgressCallback = Callable[[str, str, int, str], None]


class ResearchGraphWorkflow:
    def __init__(self, progress_callback: ProgressCallback | None = None, user_id: int | None = None) -> None:
        self.progress_callback = progress_callback
        self.user_id = user_id
        self.planner = PlannerAgent()
        self.evidence_agent = EvidenceAgent()
        self.writer = WriterAgent()
        self.verifier = VerifierAgent()
        self.reviser = RevisionAgent()
        self.memory = ResearchMemory(user_id=user_id)

    def _emit_progress(self, step: str, status: str, items: int = 0, note: str = "") -> None:
        if self.progress_callback:
            self.progress_callback(step, status, items, note)

    def planner_node(self, state: ResearchState) -> ResearchState:
        self._emit_progress("planner", "running", note="Planning research questions and search queries.")
        state["plan"] = self.planner.run(state["topic"])
        add_trace(state, "planner", "done", len(state["plan"].get("search_queries", [])))
        self._emit_progress("planner", "done", len(state["plan"].get("search_queries", [])))
        return state

    def memory_node(self, state: ResearchState) -> ResearchState:
        self._emit_progress("memory_retrieval", "running", note="Checking previous research memory.")
        context = self.memory.search(state["topic"], limit=4)
        state["memory_context"] = context
        state["memory_mode"] = self.memory.mode
        add_trace(state, "memory_retrieval", "done", len(context), f"mode={self.memory.mode}")
        self._emit_progress("memory_retrieval", "done", len(context), f"mode={self.memory.mode}")
        return state

    def search_node(self, state: ResearchState) -> ResearchState:
        self._emit_progress("search_and_scrape", "running", note="Searching and reading source pages.")
        queries = state.get("plan", {}).get("search_queries") or [state["topic"]]
        state["sources"] = search_and_scrape(queries, max_sources=state.get("max_sources", 6))
        add_trace(state, "search_and_scrape", "done", len(state["sources"]))
        self._emit_progress("search_and_scrape", "done", len(state["sources"]))
        return state

    def evidence_node(self, state: ResearchState) -> ResearchState:
        state["evidence"] = []
        sources = state.get("sources", [])
        for index, source in enumerate(sources, start=1):
            self._emit_progress(
                "evidence_extraction",
                "running",
                index - 1,
                f"Reading {source.get('source_id', index)} of {len(sources)}.",
            )
            state["evidence"].append(self.evidence_agent.run(state["topic"], source))
            self._emit_progress(
                "evidence_extraction",
                "running",
                index,
                f"Completed {index} of {len(sources)} sources.",
            )
        add_trace(state, "evidence_extraction", "done", len(state["evidence"]))
        self._emit_progress("evidence_extraction", "done", len(state["evidence"]))
        return state

    def writer_node(self, state: ResearchState) -> ResearchState:
        self._emit_progress("writer", "running", note="Writing the cited research report.")
        state["report"] = self.writer.run(
            state["topic"],
            state.get("plan", {}),
            state.get("evidence", []),
            state.get("memory_context", []),
        )
        add_trace(state, "writer", "done", 1)
        self._emit_progress("writer", "done", 1)
        return state

    def verifier_node(self, state: ResearchState) -> ResearchState:
        self._emit_progress("verifier", "running", note="Checking citations, evidence quality, and freshness.")
        state["verifier"] = self.verifier.run(state["topic"], state.get("report", ""), state.get("evidence", []))
        state["scores"] = overall_quality_scores(state.get("report", ""), state.get("evidence", []), state.get("verifier", {}))
        add_trace(
            state,
            "verifier",
            "done",
            len(state.get("verifier", {}).get("recommended_fixes", []) or []),
            f"verdict={state['verifier'].get('verdict')}",
        )
        self._emit_progress(
            "verifier",
            "done",
            len(state.get("verifier", {}).get("recommended_fixes", []) or []),
            f"verdict={state['verifier'].get('verdict')}",
        )
        return state

    def revise_node(self, state: ResearchState) -> ResearchState:
        state["revision_count"] = state.get("revision_count", 0) + 1
        self._emit_progress("revision", "running", state["revision_count"], f"Revision pass {state['revision_count']}.")
        state["report"] = self.reviser.run(
            state["topic"], state.get("report", ""), state.get("verifier", {}), state.get("evidence", [])
        )
        add_trace(state, "revision", "done", state["revision_count"])
        self._emit_progress("revision", "done", state["revision_count"])
        return state

    def save_node(self, state: ResearchState) -> ResearchState:
        if state.get("revision_count", 0) == 0:
            self._emit_progress("revision", "skipped", note="No revision needed.")
        self._emit_progress("save_history_and_memory", "running", note="Saving run and memory.")
        state["runtime_seconds"] = round(time.time() - state.get("_started", time.time()), 2)  # type: ignore[arg-type]
        payload = {k: v for k, v in state.items() if not k.startswith("_")}
        state["run_id"] = save_run(state["topic"], payload, user_id=self.user_id)
        # Save final memory after run_id exists.
        payload["run_id"] = state["run_id"]
        self.memory.add_run(state["topic"], payload)
        add_trace(state, "save_history_and_memory", "done", 1, f"run_id={state['run_id']}")
        self._emit_progress("save_history_and_memory", "done", 1, f"run_id={state['run_id']}")
        return state

    def should_revise(self, state: ResearchState) -> str:
        verdict = (state.get("verifier", {}) or {}).get("verdict", "needs_review")
        score = state.get("scores", {}).get("overall_score", 0)
        if state.get("revision_count", 0) >= MAX_REVISIONS:
            return "save"
        if verdict in {"fail", "needs_review"} or score < 70:
            return "revise"
        return "save"

    def compile(self):
        from langgraph.graph import END, StateGraph

        graph = StateGraph(ResearchState)
        graph.add_node("planner", self.planner_node)
        graph.add_node("memory", self.memory_node)
        graph.add_node("search", self.search_node)
        graph.add_node("evidence", self.evidence_node)
        graph.add_node("writer", self.writer_node)
        graph.add_node("verifier", self.verifier_node)
        graph.add_node("revise", self.revise_node)
        graph.add_node("save", self.save_node)

        graph.set_entry_point("planner")
        graph.add_edge("planner", "memory")
        graph.add_edge("memory", "search")
        graph.add_edge("search", "evidence")
        graph.add_edge("evidence", "writer")
        graph.add_edge("writer", "verifier")
        graph.add_conditional_edges("verifier", self.should_revise, {"revise": "revise", "save": "save"})
        graph.add_edge("revise", "verifier")
        graph.add_edge("save", END)
        return graph.compile()

    def run_with_langgraph(self, topic: str, max_sources: int = 6) -> ResearchState:
        app = self.compile()
        initial: ResearchState = {
            "topic": topic,
            "user_id": self.user_id,  # type: ignore[typeddict-item]
            "max_sources": max_sources,
            "revision_count": 0,
            "trace": [],
            "_started": time.time(),  # type: ignore[typeddict-unknown-key]
        }
        result = app.invoke(initial)
        result.pop("_started", None)
        return result
