"""Summaries for optional local discovery artifacts."""

from __future__ import annotations

from typing import Dict, Iterable, List


def _safe_int(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _safe_float(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def summarize_containers(containers: Iterable[Dict]) -> Dict:
    rows = [item for item in containers if isinstance(item, dict)]
    platform_counts: Dict[str, int] = {}
    for item in rows:
        platform = str(item.get("platform") or "unknown")
        platform_counts[platform] = platform_counts.get(platform, 0) + 1
    top = sorted(rows, key=lambda item: _safe_int(item.get("container_score")), reverse=True)[:5]
    return {
        "total_containers": len(rows),
        "selected_for_sampling": sum(1 for item in rows if item.get("selected_for_sampling")),
        "platform_counts": platform_counts,
        "top_containers": [
            {
                "container_id": item.get("container_id", ""),
                "platform": item.get("platform", ""),
                "title": item.get("title", ""),
                "container_score": _safe_int(item.get("container_score")),
                "selected_for_sampling": bool(item.get("selected_for_sampling")),
            }
            for item in top
        ],
    }


def summarize_pain_signal_rows(rows: Iterable[Dict]) -> Dict:
    items = [item for item in rows if isinstance(item, dict)]
    workflow_counts: Dict[str, int] = {}
    distribution_counts: Dict[str, int] = {}
    total_confidence = 0.0
    high_confidence = 0
    payment_count = 0

    for item in items:
        signal = item.get("pain_signal") or {}
        confidence = _safe_float(signal.get("confidence"))
        total_confidence += confidence
        if confidence >= 0.65:
            high_confidence += 1
        if signal.get("payment_signal"):
            payment_count += 1
        workflow = str(signal.get("workflow") or "").strip()
        if workflow:
            workflow_counts[workflow] = workflow_counts.get(workflow, 0) + 1
        for hint in signal.get("distribution_hint") or []:
            hint = str(hint)
            distribution_counts[hint] = distribution_counts.get(hint, 0) + 1

    return {
        "total_pain_signals": len(items),
        "high_confidence_count": high_confidence,
        "payment_signal_count": payment_count,
        "average_confidence": round(total_confidence / len(items), 2) if items else 0.0,
        "top_workflows": [
            {"workflow": workflow, "count": count}
            for workflow, count in sorted(workflow_counts.items(), key=lambda row: row[1], reverse=True)[:5]
        ],
        "distribution_counts": distribution_counts,
    }
