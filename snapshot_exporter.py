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
        "idea_id": idea.get("idea_id", ""),
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


def _source_platform(source: str) -> str:
    if source.startswith("Reddit "):
        return "Reddit"
    if source.startswith("App Store"):
        return "App Store"
    if source.startswith("Hacker News"):
        return "Hacker News"
    return source or "Unknown"


def _rank_counts(counts: Dict[str, int], total: int, name_key: str, limit: int = 8) -> List[Dict]:
    rows = []
    for name, count in sorted(counts.items(), key=lambda item: item[1], reverse=True)[:limit]:
        rows.append({
            name_key: name,
            "count": count,
            "percent": round(count / max(total, 1) * 100),
        })
    return rows


def build_source_stats(ideas: List[Dict]) -> Dict:
    source_counts: Dict[str, int] = {}
    platform_counts: Dict[str, int] = {}
    for idea in ideas:
        source = idea.get("source") or "Unknown"
        platform = _source_platform(source)
        source_counts[source] = source_counts.get(source, 0) + 1
        platform_counts[platform] = platform_counts.get(platform, 0) + 1

    total = sum(source_counts.values())
    return {
        "total_candidates": total,
        "platforms": _rank_counts(platform_counts, total, "name"),
        "top_sources": _rank_counts(source_counts, total, "source", limit=10),
    }


def _default_decision_summary(opportunity_clusters: List[Dict]) -> Dict:
    counts = {"Build Now": 0, "Monitor": 0, "Discard": 0}
    for cluster in opportunity_clusters:
        verdict = cluster.get("decision_verdict", "Monitor")
        counts[verdict] = counts.get(verdict, 0) + 1
    return {
        "total_clusters": len(opportunity_clusters),
        "build_now_count": counts.get("Build Now", 0),
        "monitor_count": counts.get("Monitor", 0),
        "discard_count": counts.get("Discard", 0),
    }


def _default_source_health(summary: Dict, ideas: List[Dict]) -> Dict:
    errors = list(summary.get("errors", []))
    source_counts: Dict[str, int] = {}
    for idea in ideas:
        source = idea.get("source") or "Unknown"
        source_counts[source] = source_counts.get(source, 0) + 1
    if not summary and not ideas:
        status = "unknown"
    elif errors:
        status = "degraded"
    else:
        status = "ok"
    return {
        "status": status,
        "raw_count": _safe_int(summary.get("raw_count")),
        "unique_count": _safe_int(summary.get("unique_count")),
        "candidate_count": _safe_int(summary.get("candidate_count")),
        "error_count": len(errors),
        "errors": errors,
        "source_counts": source_counts,
    }


def build_dashboard_snapshot(
    ideas: List[Dict],
    summary: Dict,
    history_summary: Dict,
    markdown_report: str,
    top_n: int = 12,
    opportunity_clusters: Optional[List[Dict]] = None,
    decision_summary: Optional[Dict] = None,
    source_health: Optional[Dict] = None,
    analysis_metadata: Optional[Dict] = None,
    source_metrics: Optional[List[Dict]] = None,
    container_summary: Optional[Dict] = None,
    pain_signal_summary: Optional[Dict] = None,
) -> Dict:
    top_ideas = [_idea_to_snapshot_row(idea) for idea in ideas[:top_n]]
    clusters = list(opportunity_clusters or [])
    return {
        "schema_version": 2,
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
        "opportunity_clusters": clusters,
        "decision_summary": dict(decision_summary or _default_decision_summary(clusters)),
        "source_health": dict(source_health or _default_source_health(summary, ideas)),
        "source_stats": build_source_stats(ideas),
        "source_metrics": list(source_metrics or []),
        "container_summary": dict(container_summary or {}),
        "pain_signal_summary": dict(pain_signal_summary or {}),
        "label_counts": count_labels(ideas),
        "analysis_metadata": dict(analysis_metadata or {"analysis_provider": "heuristic", "analysis_status": "local"}),
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
