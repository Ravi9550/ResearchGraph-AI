"""Deterministic evaluation metrics for ResearchGraph AI V2."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List
from urllib.parse import urlparse


def _sentences(text: str) -> List[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text or "") if len(s.strip()) > 35]


def _citation_ids(text: str) -> List[str]:
    return re.findall(r"\[S\d+\]", text or "")


def citation_coverage_score(report: str) -> Dict[str, Any]:
    sentences = _sentences(report)
    if not sentences:
        return {"score": 0, "cited_sentences": 0, "total_sentences": 0}
    cited = sum(1 for sentence in sentences if _citation_ids(sentence))
    return {"score": round((cited / len(sentences)) * 100), "cited_sentences": cited, "total_sentences": len(sentences)}


def citation_validity_score(report: str, evidence: List[Dict[str, Any]]) -> Dict[str, Any]:
    used = set(_citation_ids(report))
    valid = {f"[{item.get('source_id')}]" for item in evidence if item.get("source_id")}
    invalid = sorted(used - valid)
    score = 100 if not used else round(((len(used) - len(invalid)) / len(used)) * 100)
    return {"score": score, "used_citations": sorted(used), "invalid_citations": invalid}


def source_diversity_score(evidence: List[Dict[str, Any]]) -> Dict[str, Any]:
    domains = []
    for item in evidence:
        domain = item.get("domain") or urlparse(item.get("url", "")).netloc.replace("www.", "")
        if domain:
            domains.append(domain)
    unique = sorted(set(domains))
    score = min(100, len(unique) * 18 + min(10, len(evidence) * 2))
    return {"score": score, "unique_domains": len(unique), "domains": unique}


def evidence_depth_score(evidence: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not evidence:
        return {"score": 0, "avg_key_points": 0, "source_count": 0}
    counts = [len(item.get("key_points", [])) for item in evidence]
    avg = sum(counts) / len(counts)
    confidence_values = []
    for item in evidence:
        try:
            confidence_values.append(float(item.get("confidence", 0.5)))
        except Exception:
            confidence_values.append(0.5)
    avg_conf = sum(confidence_values) / len(confidence_values)
    score = min(100, round((len(evidence) * 9) + (avg * 10) + (avg_conf * 20)))
    return {"score": score, "avg_key_points": round(avg, 2), "avg_confidence": round(avg_conf, 2), "source_count": len(evidence)}


def freshness_score(evidence: List[Dict[str, Any]]) -> Dict[str, Any]:
    current_year = datetime.now(timezone.utc).year
    years = []
    unknown = 0
    for item in evidence:
        text = " ".join([str(item.get("published_at", "")), str(item.get("freshness_note", "")), str(item.get("summary", ""))])
        match = re.findall(r"\b20\d{2}\b", text)
        if match:
            years.append(max(int(y) for y in match))
        else:
            unknown += 1
    if not evidence:
        return {"score": 0, "known_dates": 0, "unknown_dates": 0}
    if not years:
        return {"score": 45, "known_dates": 0, "unknown_dates": unknown, "note": "No clear dates detected."}
    avg_age = sum(current_year - year for year in years) / len(years)
    score = max(20, min(100, round(100 - (avg_age * 12) - (unknown * 5))))
    return {"score": score, "known_dates": len(years), "unknown_dates": unknown, "latest_year": max(years)}


def readability_score(report: str) -> Dict[str, Any]:
    words = re.findall(r"\w+", report or "")
    sentences = _sentences(report)
    if not words or not sentences:
        return {"score": 0, "avg_sentence_words": 0}
    avg_sentence = len(words) / len(sentences)
    # Sweet spot for report readability: roughly 14-24 words/sentence.
    if 14 <= avg_sentence <= 24:
        score = 100
    elif avg_sentence < 14:
        score = max(60, round(100 - (14 - avg_sentence) * 4))
    else:
        score = max(35, round(100 - (avg_sentence - 24) * 4))
    return {"score": score, "avg_sentence_words": round(avg_sentence, 2), "word_count": len(words)}


def verifier_penalty(verifier: Dict[str, Any]) -> Dict[str, Any]:
    unsupported = len(verifier.get("unsupported_claims", []) or [])
    citation_issues = len(verifier.get("citation_issues", []) or [])
    contradictions = len(verifier.get("contradictions", []) or [])
    freshness = len(verifier.get("freshness_issues", []) or [])
    penalty = unsupported * 10 + citation_issues * 6 + contradictions * 10 + freshness * 4
    return {
        "penalty": min(60, penalty),
        "unsupported_claim_count": unsupported,
        "citation_issue_count": citation_issues,
        "contradiction_count": contradictions,
        "freshness_issue_count": freshness,
    }


def overall_quality_scores(report: str, evidence: List[Dict[str, Any]], verifier: Dict[str, Any] | None = None) -> Dict[str, Any]:
    citation = citation_coverage_score(report)
    validity = citation_validity_score(report, evidence)
    diversity = source_diversity_score(evidence)
    depth = evidence_depth_score(evidence)
    fresh = freshness_score(evidence)
    readable = readability_score(report)
    penalty = verifier_penalty(verifier or {})

    base = round(
        citation["score"] * 0.25
        + validity["score"] * 0.20
        + diversity["score"] * 0.15
        + depth["score"] * 0.15
        + fresh["score"] * 0.15
        + readable["score"] * 0.10
    )
    overall = max(0, min(100, base - penalty["penalty"]))
    return {
        "overall_score": overall,
        "base_score_before_verifier_penalty": base,
        "citation_coverage": citation,
        "citation_validity": validity,
        "source_diversity": diversity,
        "evidence_depth": depth,
        "freshness": fresh,
        "readability": readable,
        "verifier_penalty": penalty,
    }
