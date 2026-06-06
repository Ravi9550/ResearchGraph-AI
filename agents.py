"""Agent definitions for ResearchGraph AI V2.

V2 improves the tutorial-style project with explicit agent roles, JSON contracts,
verification, revision, and source-backed outputs.
"""

from __future__ import annotations

import ast
import json
from typing import Any, Dict, List

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from llm_factory import get_llm


def safe_json_loads(raw: str, fallback: Any) -> Any:
    """Parse model JSON even if wrapped in markdown fences."""
    if not raw:
        return fallback
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        try:
            parsed = ast.literal_eval(text)
            if isinstance(parsed, (dict, list)):
                return parsed
        except (SyntaxError, ValueError):
            pass
        start_obj, end_obj = text.find("{"), text.rfind("}")
        start_arr, end_arr = text.find("["), text.rfind("]")
        candidates = []
        if start_obj != -1 and end_obj > start_obj:
            candidates.append(text[start_obj : end_obj + 1])
        if start_arr != -1 and end_arr > start_arr:
            candidates.append(text[start_arr : end_arr + 1])
        for candidate in candidates:
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                try:
                    parsed = ast.literal_eval(candidate)
                    if isinstance(parsed, (dict, list)):
                        return parsed
                except (SyntaxError, ValueError):
                    continue
    return fallback


def coerce_evidence_object(value: Any, fallback: Dict[str, Any]) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                return item
        if value:
            coerced = dict(fallback)
            coerced["key_points"] = [str(item) for item in value[:8]]
            coerced["limitations"] = ["Evidence agent returned a JSON list instead of an object."]
            return coerced
    return dict(fallback)


def coerce_json_object(value: Any, fallback: Dict[str, Any]) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                return item
    return dict(fallback)


class PlannerAgent:
    """Break a research topic into questions, queries, and verification needs."""

    def __init__(self) -> None:
        self.chain = (
            ChatPromptTemplate.from_messages(
                [
                    ("system", "You are a senior research planner. Return compact valid JSON only."),
                    (
                        "human",
                        """
Topic: {topic}

Create a research plan. Return JSON only:
{{
  "objective": "clear research objective",
  "questions": ["4 to 6 precise research questions"],
  "search_queries": ["4 to 6 web search queries"],
  "must_verify": ["specific facts, numbers, dates, or assumptions to verify"],
  "trusted_source_hints": ["types of sources that would be reliable for this topic"]
}}
""",
                    ),
                ]
            )
            | get_llm(0)
            | StrOutputParser()
        )

    def run(self, topic: str) -> Dict[str, Any]:
        raw = self.chain.invoke({"topic": topic})
        fallback = {
            "objective": f"Research {topic} using reliable public sources.",
            "questions": [f"What are the most important facts about {topic}?"],
            "search_queries": [topic],
            "must_verify": ["dates", "numbers", "claims", "source reliability"],
            "trusted_source_hints": ["official documentation", "reputable news", "primary sources"],
        }
        plan = coerce_json_object(safe_json_loads(raw, fallback), fallback)
        plan["raw_output"] = raw
        return plan


class EvidenceAgent:
    """Extract structured evidence from a single source."""

    def __init__(self) -> None:
        self.chain = (
            ChatPromptTemplate.from_messages(
                [
                    (
                        "system",
                        "You extract only facts supported by the provided source text. Never invent facts. Return JSON only.",
                    ),
                    (
                        "human",
                        """
Topic: {topic}
Source ID: {source_id}
Title: {title}
URL: {url}
Published/Updated hint: {published_at}
Content:
{content}

Return JSON only:
{{
  "source_id": "{source_id}",
  "summary": "2 sentence summary",
  "key_points": ["4 to 8 factual points directly supported by this source"],
  "numbers_or_dates": ["important statistics or dates found, else empty list"],
  "confidence": 0.0,
  "freshness_note": "whether this source appears current or possibly outdated",
  "limitations": ["missing context, bias, outdated info, weak evidence, or uncertainty"],
  "best_quote_or_snippet": "short useful snippet under 35 words"
}}
""",
                    ),
                ]
            )
            | get_llm(0)
            | StrOutputParser()
        )

    def run(self, topic: str, source: Dict[str, Any]) -> Dict[str, Any]:
        raw = self.chain.invoke(
            {
                "topic": topic,
                "source_id": source["source_id"],
                "title": source.get("title", "Untitled"),
                "url": source.get("url", ""),
                "published_at": source.get("published_at", "unknown"),
                "content": source.get("content") or source.get("snippet", "")[:9000],
            }
        )
        fallback = {
            "source_id": source["source_id"],
            "summary": source.get("snippet") or source.get("title", "No summary available."),
            "key_points": [source.get("snippet", "Evidence extraction failed; inspect source manually.")],
            "numbers_or_dates": [],
            "confidence": 0.5,
            "freshness_note": "Unknown freshness.",
            "limitations": ["Agent did not return valid JSON."],
            "best_quote_or_snippet": source.get("snippet", "")[:180],
        }
        evidence = coerce_evidence_object(safe_json_loads(raw, fallback), fallback)
        evidence.update(
            {
                "url": source.get("url", ""),
                "title": source.get("title", "Untitled"),
                "domain": source.get("domain", "unknown"),
                "published_at": source.get("published_at", "unknown"),
                "scrape_status": source.get("scrape_status", "unknown"),
                "raw_output": raw,
            }
        )
        return evidence


class WriterAgent:
    """Write a report with inline citations and section confidence."""

    def __init__(self) -> None:
        self.chain = (
            ChatPromptTemplate.from_messages(
                [
                    (
                        "system",
                        "You are an evidence-based research analyst. Every factual claim needs source citations like [S1].",
                    ),
                    (
                        "human",
                        """
Write a source-backed research report.

Topic: {topic}
Research Plan:
{plan}

Relevant Memory From Previous Runs:
{memory_context}

Evidence Pack:
{evidence_pack}

Rules:
- Use only the evidence pack and relevant memory.
- Prefer current, reliable sources.
- Cite factual claims with source IDs like [S1].
- If a claim is uncertain, say what is uncertain.
- Do not hide limitations.
- Include section confidence as High / Medium / Low.
- Markdown tables must be valid GitHub-style tables: one row per line, with a blank line before and after the table.
- In the Evidence Table, use exactly these columns: Finding | Evidence | Source.
- In the Source List, use exactly these columns: Source | Summary.
- Do not collapse multiple table rows onto one line.

Structure:
# Executive Summary
# Key Findings
# Evidence Table
# Contradictions or Uncertainties
# Risks / Limitations
# Practical Recommendations
# Source List
""",
                    ),
                ]
            )
            | get_llm(0.2)
            | StrOutputParser()
        )

    def run(
        self,
        topic: str,
        plan: Dict[str, Any],
        evidence: List[Dict[str, Any]],
        memory_context: List[Dict[str, Any]] | None = None,
    ) -> str:
        return self.chain.invoke(
            {
                "topic": topic,
                "plan": json.dumps(plan, indent=2),
                "evidence_pack": json.dumps(evidence, indent=2),
                "memory_context": json.dumps(memory_context or [], indent=2),
            }
        )


class VerifierAgent:
    """Audit the report for citations, unsupported claims, and source quality."""

    def __init__(self) -> None:
        self.chain = (
            ChatPromptTemplate.from_messages(
                [
                    (
                        "system",
                        "You are a strict research QA reviewer. Flag unsupported, stale, contradictory, or overconfident claims.",
                    ),
                    (
                        "human",
                        """
Audit this report against the evidence pack.

Topic: {topic}
Report:
{report}

Evidence Pack:
{evidence_pack}

Return JSON only:
{{
  "verdict": "pass | needs_review | fail",
  "score": 0,
  "unsupported_claims": ["claims that lack source support"],
  "citation_issues": ["missing, weak, or invalid citations"],
  "freshness_issues": ["date-sensitive or outdated areas"],
  "contradictions": ["source or report contradictions"],
  "source_quality_notes": ["notes about reliability and diversity"],
  "recommended_fixes": ["specific fixes before publishing"]
}}
""",
                    ),
                ]
            )
            | get_llm(0)
            | StrOutputParser()
        )

    def run(self, topic: str, report: str, evidence: List[Dict[str, Any]]) -> Dict[str, Any]:
        raw = self.chain.invoke(
            {
                "topic": topic,
                "report": report,
                "evidence_pack": json.dumps(evidence, indent=2),
            }
        )
        fallback = {
            "verdict": "needs_review",
            "score": 50,
            "unsupported_claims": [],
            "citation_issues": ["Verifier did not return valid JSON."],
            "freshness_issues": [],
            "contradictions": [],
            "source_quality_notes": [],
            "recommended_fixes": ["Manually inspect report and evidence."],
        }
        result = coerce_json_object(safe_json_loads(raw, fallback), fallback)
        result["raw_output"] = raw
        return result


class RevisionAgent:
    """Rewrite a report using verifier feedback."""

    def __init__(self) -> None:
        self.chain = (
            ChatPromptTemplate.from_messages(
                [
                    ("system", "You revise reports to fix evidence and citation issues. Do not add unsupported claims."),
                    (
                        "human",
                        """
Topic: {topic}
Original Report:
{report}

Verifier Feedback:
{verifier}

Evidence Pack:
{evidence_pack}

Revise the report. Keep the same structure. Fix citation gaps, remove unsupported claims, and add uncertainty notes where needed.
""",
                    ),
                ]
            )
            | get_llm(0.15)
            | StrOutputParser()
        )

    def run(self, topic: str, report: str, verifier: Dict[str, Any], evidence: List[Dict[str, Any]]) -> str:
        return self.chain.invoke(
            {
                "topic": topic,
                "report": report,
                "verifier": json.dumps(verifier, indent=2),
                "evidence_pack": json.dumps(evidence, indent=2),
            }
        )
