#!/usr/bin/env python3
"""Build and load dashboard snapshot files for the read-only Streamlit app."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional


SNAPSHOT_PATH = Path(__file__).resolve().parent / "data" / "dashboard_snapshot.json"


def _safe_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _idea_to_snapshot_row(idea: Dict) -> Dict:
    return {
        "mvp_concept": idea.get("mvp_concept", ""),
        "category": idea.get("category", "其他/待判定"),
        "total_score": _safe_int(idea.get("total_score")),
        "verdict": idea.get("verdict", "Monitor"),
        "pain_summary": idea.get("pain_summary", ""),
        "validation_step": idea.get("validation_step", ""),
        "source": idea.get("source", ""),
        "title": idea.get("title", ""),
        "source_url": idea.get("source_url", ""),
        "repeat_7d": _safe_int(idea.get("repeat_7d"), 1),
        "label": idea.get("label", "未标注"),
    }


def count_labels(ideas: Iterable[Dict]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for idea in ideas:
        label = idea.get("label", "未标注") or "未标注"
        counts[label] = counts.get(label, 0) + 1
    return counts


def build_dashboard_snapshot(
    ideas: List[Dict],
    summary: Dict,
    history_summary: Dict,
    markdown_report: str,
    top_n: int = 12,
) -> Dict:
    top_ideas = [_idea_to_snapshot_row(idea) for idea in ideas[:top_n]]
    return {
        "schema_version": 1,
        "generated_at": summary.get("generated_at", ""),
        "summary": {
            "raw_count": _safe_int(summary.get("raw_count")),
            "unique_count": _safe_int(summary.get("unique_count")),
            "candidate_count": _safe_int(summary.get("candidate_count")),
            "build_now_count": _safe_int(summary.get("build_now_count")),
            "monitor_count": _safe_int(summary.get("monitor_count")),
            "discard_count": _safe_int(summary.get("discard_count")),
            "saved_count": _safe_int(summary.get("saved_count")),
            "errors": list(summary.get("errors", [])),
        },
        "top_ideas": top_ideas,
        "category_counts": dict(history_summary.get("category_counts", {})),
        "repeated_signals_7d": list(history_summary.get("repeated_signals", []))[:12],
        "label_counts": count_labels(ideas),
        "markdown_report": markdown_report,
    }


def write_dashboard_snapshot(snapshot: Dict, path: Path = SNAPSHOT_PATH) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")


def load_dashboard_snapshot(path: Path = SNAPSHOT_PATH) -> Optional[Dict]:
    path = Path(path)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload
