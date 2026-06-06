"""Offline smoke tests. Does not call any paid LLM provider or Tavily."""

from scoring import overall_quality_scores
from storage import init_db, list_runs, save_run
from memory import ResearchMemory


def test_scoring():
    evidence = [
        {
            "source_id": "S1",
            "url": "https://example.com/a",
            "domain": "example.com",
            "key_points": ["Point one", "Point two", "Point three"],
            "confidence": 0.8,
            "published_at": "2026",
            "summary": "Current source summary.",
        },
        {
            "source_id": "S2",
            "url": "https://another.com/b",
            "domain": "another.com",
            "key_points": ["Point four", "Point five"],
            "confidence": 0.7,
            "published_at": "2025",
            "summary": "Another source summary.",
        },
    ]
    report = "This is a supported factual sentence about the topic [S1]. Another supported sentence uses a second source [S2]."
    scores = overall_quality_scores(report, evidence, {"unsupported_claims": [], "citation_issues": []})
    assert 0 <= scores["overall_score"] <= 100
    assert scores["citation_validity"]["score"] == 100


def test_storage_and_memory():
    init_db()
    payload = {"topic": "offline smoke test", "scores": {"overall_score": 88}, "verifier": {"verdict": "pass"}}
    run_id = save_run("offline smoke test", payload)
    assert run_id > 0
    assert isinstance(list_runs(limit=1), list)
    memory = ResearchMemory()
    memory.add("offline smoke test", "FastAPI LangGraph citations verifier memory", {"kind": "test"})
    matches = memory.search("LangGraph verifier", limit=3)
    assert isinstance(matches, list)


if __name__ == "__main__":
    test_scoring()
    test_storage_and_memory()
    print("Offline smoke tests passed.")
