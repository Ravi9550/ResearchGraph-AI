"""SQLite-backed research memory."""

from __future__ import annotations

import math
from collections import Counter
from typing import Any, Dict, List

from storage import list_memory_chunks, save_memory_chunk


def _tokenize(text: str) -> List[str]:
    return [t.lower() for t in text.split() if len(t) > 2]


def _cosine_counts(a: Counter, b: Counter) -> float:
    common = set(a) & set(b)
    num = sum(a[t] * b[t] for t in common)
    den1 = math.sqrt(sum(v * v for v in a.values()))
    den2 = math.sqrt(sum(v * v for v in b.values()))
    if not den1 or not den2:
        return 0.0
    return num / (den1 * den2)


class ResearchMemory:
    """Store and retrieve reusable research evidence."""

    def __init__(self, user_id: int | None = None) -> None:
        self.user_id = user_id
        self.mode = "sqlite"

    def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        q_counter = Counter(_tokenize(query))
        scored = []
        for chunk in list_memory_chunks(limit=1000, user_id=self.user_id):
            score = _cosine_counts(q_counter, Counter(_tokenize(chunk["text"] + " " + chunk["topic"])))
            if score > 0:
                scored.append({"score": round(score, 4), **chunk})
        return sorted(scored, key=lambda x: x["score"], reverse=True)[:limit]

    def add(self, topic: str, text: str, metadata: Dict[str, Any]) -> None:
        save_memory_chunk(topic, text, metadata, user_id=self.user_id)

    def add_run(self, topic: str, result: Dict[str, Any]) -> None:
        for item in result.get("evidence", []):
            text = "\n".join(
                [
                    item.get("summary", ""),
                    "\n".join(item.get("key_points", [])),
                    "\n".join(item.get("limitations", [])),
                ]
            )
            self.add(topic, text, {"kind": "evidence", "source_id": item.get("source_id"), "url": item.get("url")})
        report = result.get("report", "")
        if report:
            self.add(topic, report[:6000], {"kind": "report", "overall_score": result.get("scores", {}).get("overall_score")})
