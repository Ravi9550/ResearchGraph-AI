"""Export helpers for Markdown, JSON, and PDF reports."""

from __future__ import annotations

import json
import re
import time
from html import escape
from io import BytesIO
from pathlib import Path
from typing import Any, Dict

from config import EXPORT_DIR


def _safe_slug(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", text.strip().lower())[:60].strip("_")
    return slug or "research_report"


def export_markdown(result: Dict[str, Any]) -> Path:
    path = EXPORT_DIR / f"{_safe_slug(result.get('topic', 'research'))}_{int(time.time())}.md"
    path.write_text(result.get("report", ""), encoding="utf-8")
    return path


def export_json(result: Dict[str, Any]) -> Path:
    path = EXPORT_DIR / f"{_safe_slug(result.get('topic', 'research'))}_{int(time.time())}.json"
    path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return path


def _pdf_escape(value: Any) -> str:
    return escape(str(value), quote=True)


def _build_pdf(result: Dict[str, Any], target: str | BytesIO) -> None:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    doc = SimpleDocTemplate(target, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []
    story.append(Paragraph(_pdf_escape(result.get("topic", "Research Report")), styles["Title"]))
    story.append(Spacer(1, 12))
    for line in result.get("report", "").splitlines():
        line = line.strip()
        if not line:
            story.append(Spacer(1, 6))
        elif line.startswith("# "):
            story.append(Paragraph(_pdf_escape(line[2:]), styles["Heading1"]))
        elif line.startswith("## "):
            story.append(Paragraph(_pdf_escape(line[3:]), styles["Heading2"]))
        else:
            story.append(Paragraph(_pdf_escape(line), styles["BodyText"]))

    sources = result.get("sources") or []
    if sources:
        story.append(Spacer(1, 12))
        story.append(Paragraph("Evidence Sources", styles["Heading2"]))
        for source in sources:
            source_id = source.get("source_id", "")
            title = source.get("title", "Untitled")
            url = source.get("url", "")
            safe_source_id = _pdf_escape(source_id)
            safe_title = _pdf_escape(title)
            safe_url = _pdf_escape(url)
            if safe_url.startswith(("http://", "https://")):
                text = f'{safe_source_id}: {safe_title}<br/><link href="{safe_url}">{safe_url}</link>'
            else:
                text = f"{safe_source_id}: {safe_title}<br/>{safe_url}"
            story.append(Paragraph(text, styles["BodyText"]))
            story.append(Spacer(1, 6))
    doc.build(story)


def export_pdf_bytes(result: Dict[str, Any]) -> bytes:
    """Build PDF bytes for browser downloads."""
    buffer = BytesIO()
    _build_pdf(result, buffer)
    return buffer.getvalue()


def export_pdf(result: Dict[str, Any]) -> Path:
    """Export a simple PDF. Uses reportlab if installed; otherwise writes .txt fallback."""
    try:

        path = EXPORT_DIR / f"{_safe_slug(result.get('topic', 'research'))}_{int(time.time())}.pdf"
        _build_pdf(result, str(path))
        return path
    except Exception:
        path = EXPORT_DIR / f"{_safe_slug(result.get('topic', 'research'))}_{int(time.time())}.txt"
        path.write_text(result.get("report", ""), encoding="utf-8")
        return path
