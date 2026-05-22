"""Source-level quality metrics for the local demand pipeline."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional


SOURCE_METRICS_FILE = Path(__file__).resolve().parent / "data" / "source_metrics.json"
SOURCE_METRICS_HISTORY_FILE = Path(__file__).resolve().parent / "data" / "source_metrics_history.json"


def _source_name(item) -> str:
    if isinstance(item, dict):
        return str(item.get("source") or "Unknown")
    return str(getattr(item, "source", "") or "Unknown")


def _recommended_action(candidate_rate: float, error_count: int) -> str:
    if error_count > 0 and candidate_rate == 0:
        return "pause"
    if candidate_rate >= 0.35:
        return "increase"
    if candidate_rate >= 0.12:
        return "keep"
    if candidate_rate > 0:
        return "reduce"
    return "pause"


def build_source_metrics(
    raw_items: Iterable,
    candidate_items: Iterable,
    clusters: Iterable[Dict],
    errors_by_source: Optional[Dict[str, int]] = None,
) -> List[Dict]:
    raw_counts: Dict[str, int] = {}
    candidate_counts: Dict[str, int] = {}

    for item in raw_items:
        source = _source_name(item)
        raw_counts[source] = raw_counts.get(source, 0) + 1
    for item in candidate_items:
        source = _source_name(item)
        candidate_counts[source] = candidate_counts.get(source, 0) + 1
    return build_source_metrics_from_counts(raw_counts, candidate_counts, clusters, errors_by_source)


def build_source_metrics_from_counts(
    raw_counts: Dict[str, int],
    candidate_counts: Dict[str, int],
    clusters: Iterable[Dict],
    errors_by_source: Optional[Dict[str, int]] = None,
) -> List[Dict]:
    signal_counts = dict(candidate_counts)
    cluster_counts: Dict[str, int] = {}
    validation_counts: Dict[str, int] = {}

    for cluster in clusters:
        source_names = cluster.get("source_names") or []
        for source in source_names:
            cluster_counts[source] = cluster_counts.get(source, 0) + 1
            if cluster.get("decision_verdict") in {"Build Now", "Validate Manually"} or cluster.get("funnel_verdict") in {"Build Now", "Validate Manually"}:
                validation_counts[source] = validation_counts.get(source, 0) + 1

    errors_by_source = dict(errors_by_source or {})
    sources = sorted(set(raw_counts) | set(candidate_counts) | set(cluster_counts) | set(errors_by_source))
    rows: List[Dict] = []
    for source in sources:
        raw_count = raw_counts.get(source, 0)
        candidate_count = candidate_counts.get(source, 0)
        candidate_rate = round(candidate_count / raw_count, 4) if raw_count else 0.0
        error_count = int(errors_by_source.get(source, 0) or 0)
        rows.append({
            "source": source,
            "raw_count": raw_count,
            "candidate_count": candidate_count,
            "candidate_rate": candidate_rate,
            "signal_count": signal_counts.get(source, 0),
            "cluster_count": cluster_counts.get(source, 0),
            "validation_candidate_count": validation_counts.get(source, 0),
            "error_count": error_count,
            "recommended_action": _recommended_action(candidate_rate, error_count),
        })
    return rows


def save_source_metrics(rows: List[Dict], path: Optional[Path] = None) -> None:
    target = Path(path or SOURCE_METRICS_FILE)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def load_source_metrics(path: Optional[Path] = None) -> List[Dict]:
    target = Path(path or SOURCE_METRICS_FILE)
    if not target.exists():
        return []
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return payload if isinstance(payload, list) else []


def load_source_metrics_history(path: Optional[Path] = None) -> List[Dict]:
    target = Path(path or SOURCE_METRICS_HISTORY_FILE)
    if not target.exists():
        return []
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return payload if isinstance(payload, list) else []


def append_source_metrics_history(
    rows: List[Dict],
    generated_at: str,
    path: Optional[Path] = None,
    max_records: int = 30,
) -> List[Dict]:
    target = Path(path or SOURCE_METRICS_HISTORY_FILE)
    history = load_source_metrics_history(target)
    history.append({
        "generated_at": generated_at,
        "metrics": rows,
    })
    history = history[-max_records:]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
    return history


def _history_rows_for_source(history: List[Dict], source: str, limit: int) -> List[Dict]:
    rows: List[Dict] = []
    for record in reversed(history or []):
        for metric in record.get("metrics") or []:
            if metric.get("source") == source:
                rows.append(metric)
                break
        if len(rows) >= limit:
            break
    return list(reversed(rows))


def apply_source_metric_trends(rows: List[Dict], history: List[Dict], window: int = 3) -> List[Dict]:
    trended: List[Dict] = []
    for row in rows:
        item = dict(row)
        source = str(item.get("source") or "")
        samples = _history_rows_for_source(history, source, max(0, window - 1))
        samples.append(item)
        rates = [float(sample.get("candidate_rate") or 0) for sample in samples]
        errors = [int(sample.get("error_count") or 0) for sample in samples]
        trend_rate = round(sum(rates) / len(rates), 4) if rates else 0.0
        item["trend_window"] = len(rates)
        item["trend_candidate_rate"] = trend_rate
        item["trend_error_count"] = sum(errors)

        if len(rates) >= window:
            if sum(errors) >= window and trend_rate == 0:
                item["recommended_action"] = "pause"
            elif trend_rate < 0.12:
                item["recommended_action"] = "pause"
            elif trend_rate < 0.2 and item.get("recommended_action") == "keep":
                item["recommended_action"] = "reduce"
        trended.append(item)
    return trended
