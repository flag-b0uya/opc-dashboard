#!/usr/bin/env python3
"""Upgrade older dashboard snapshots to the current local contract."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Dict, List, Optional

from artifact_summaries import summarize_containers, summarize_pain_signal_rows
from demand_engine import build_decision_summary
from pipeline_enricher import enrich_clusters_with_pipeline
from snapshot_exporter import SNAPSHOT_PATH
from source_metrics import build_source_metrics_from_counts


def _source_counts_from_snapshot(snapshot: Dict) -> Dict[str, int]:
    source_health = snapshot.get("source_health") or {}
    counts = source_health.get("source_counts")
    if isinstance(counts, dict) and counts:
        return {str(source): int(count or 0) for source, count in counts.items()}

    fallback: Dict[str, int] = {}
    for idea in snapshot.get("top_ideas") or []:
        if not isinstance(idea, dict):
            continue
        source = str(idea.get("source") or "Unknown")
        fallback[source] = fallback.get(source, 0) + 1
    return fallback


def _zero_container_summary() -> Dict:
    return summarize_containers([])


def _zero_pain_signal_summary() -> Dict:
    return summarize_pain_signal_rows([])


def migrate_snapshot_to_current_contract(snapshot: Dict) -> Dict:
    upgraded = copy.deepcopy(snapshot)
    clusters = upgraded.get("opportunity_clusters") or []
    if isinstance(clusters, list):
        upgraded["opportunity_clusters"] = enrich_clusters_with_pipeline(clusters)

    if not upgraded.get("source_metrics"):
        source_counts = _source_counts_from_snapshot(upgraded)
        upgraded["source_metrics"] = build_source_metrics_from_counts(
            source_counts,
            source_counts,
            upgraded.get("opportunity_clusters") or [],
            {},
        )
    upgraded.setdefault("container_summary", _zero_container_summary())
    upgraded.setdefault("pain_signal_summary", _zero_pain_signal_summary())
    upgraded["decision_summary"] = build_decision_summary(upgraded.get("opportunity_clusters") or [])
    return upgraded


def load_snapshot(path: Path) -> Dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Snapshot must be a JSON object.")
    return payload


def upgrade_snapshot_file(path: Optional[Path] = None) -> Dict:
    target = Path(path or SNAPSHOT_PATH)
    upgraded = migrate_snapshot_to_current_contract(load_snapshot(target))
    target.write_text(json.dumps(upgraded, ensure_ascii=False, indent=2), encoding="utf-8")
    return upgraded


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Upgrade an existing dashboard snapshot to the current contract.")
    parser.add_argument("--snapshot", default=str(SNAPSHOT_PATH))
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    snapshot_path = Path(args.snapshot)
    upgraded = upgrade_snapshot_file(snapshot_path)
    print(f"Snapshot upgraded: {snapshot_path}")
    print(f"Clusters: {len(upgraded.get('opportunity_clusters') or [])}")
    print(f"Source metrics: {len(upgraded.get('source_metrics') or [])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
