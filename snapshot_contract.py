"""Dashboard snapshot contract validation."""

from __future__ import annotations

from typing import Dict, List


REQUIRED_TOP_LEVEL_FIELDS = [
    "schema_version",
    "generated_at",
    "summary",
    "top_ideas",
    "opportunity_clusters",
    "decision_summary",
    "source_health",
    "source_stats",
    "category_counts",
    "repeated_signals_7d",
    "label_counts",
    "analysis_metadata",
    "markdown_report",
]

ARCHITECTURE_FIELDS = [
    "source_metrics",
    "container_summary",
    "pain_signal_summary",
]

SUMMARY_FIELDS = [
    "raw_count",
    "unique_count",
    "candidate_count",
    "build_now_count",
    "monitor_count",
    "discard_count",
    "saved_count",
    "errors",
]

CLUSTER_ACTION_FIELDS = [
    "funnel_score",
    "funnel_verdict",
    "funnel_next_step",
]


def _cluster_id(cluster: Dict, index: int) -> str:
    return str(cluster.get("cluster_id") or cluster.get("title") or f"#{index + 1}")


def validate_snapshot_contract(snapshot: Dict) -> Dict:
    errors: List[str] = []
    warnings: List[str] = []

    if not isinstance(snapshot, dict):
        return {
            "status": "error",
            "errors": ["snapshot must be a JSON object"],
            "warnings": [],
        }

    if snapshot.get("schema_version") != 2:
        errors.append("schema_version must be 2")

    for field in REQUIRED_TOP_LEVEL_FIELDS:
        if field not in snapshot:
            errors.append(f"missing top-level field: {field}")

    for field in ARCHITECTURE_FIELDS:
        if field not in snapshot:
            warnings.append(f"missing architecture field: {field}")

    summary = snapshot.get("summary")
    if not isinstance(summary, dict):
        errors.append("summary must be an object")
    else:
        for field in SUMMARY_FIELDS:
            if field not in summary:
                errors.append(f"summary missing field: {field}")

    top_ideas = snapshot.get("top_ideas")
    if "top_ideas" in snapshot and not isinstance(top_ideas, list):
        errors.append("top_ideas must be a list")

    clusters = snapshot.get("opportunity_clusters")
    if "opportunity_clusters" in snapshot and not isinstance(clusters, list):
        errors.append("opportunity_clusters must be a list")
        clusters = []

    for index, cluster in enumerate(clusters or []):
        if not isinstance(cluster, dict):
            errors.append(f"cluster #{index + 1} must be an object")
            continue
        name = _cluster_id(cluster, index)
        for field in CLUSTER_ACTION_FIELDS:
            if field not in cluster:
                warnings.append(f"cluster {name} missing action field: {field}")
    status = "error" if errors else "warning" if warnings else "ok"
    return {
        "status": status,
        "errors": errors,
        "warnings": warnings,
    }
