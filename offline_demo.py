#!/usr/bin/env python3
"""Offline fixture pipeline for validating the first-phase dashboard architecture."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, List, Optional

from demand_engine import (
    RawItem,
    build_decision_summary,
    build_opportunity_clusters,
    format_markdown_report,
    ideas_to_dicts,
    run_demand_scan,
)
from pipeline_enricher import enrich_clusters_with_pipeline
from snapshot_exporter import build_dashboard_snapshot, write_dashboard_snapshot
from source_metrics import build_source_metrics_from_counts


DEFAULT_OFFLINE_DEMO_OUTPUT = Path("data/offline_demo_snapshot.json")


def build_demo_raw_items() -> List[RawItem]:
    return [
        RawItem(
            id="demo-manual-invoice",
            source="Manual xiaohongshu",
            title="每周手动导出 Shopify 发票到 Excel 太麻烦了",
            body="财务团队每周都要手动整理账单报表，Expensify 太贵，而且缺少我们需要的导出 workflow。",
            source_url="offline://manual/demo-manual-invoice",
            published_at="2026-05-21T09:00:00",
            metadata={"fixture": True},
        ),
        RawItem(
            id="demo-reddit-invoice",
            source="Reddit r/smallbusiness",
            title="Need alternative to Expensify for invoice export workflow",
            body="Our finance team manually exports Shopify invoices to Excel every week. Expensify is too expensive and missing the report workflow we need.",
            source_url="offline://reddit/demo-reddit-invoice",
            published_at="2026-05-21T09:05:00",
            metadata={"fixture": True, "subreddit": "smallbusiness"},
        ),
        RawItem(
            id="demo-github-reporting",
            source="GitHub issues",
            title="Missing CSV export for weekly support dashboard",
            body="Support team needs a weekly report export. Current dashboard is slow and manual, and customers keep asking for automation.",
            source_url="offline://github/demo-github-reporting",
            published_at="2026-05-21T09:10:00",
            metadata={"fixture": True, "repo": "demo/support-dashboard"},
        ),
        RawItem(
            id="demo-youtube-comments",
            source="YouTube comments",
            title="Looking for a cheaper report automation workflow",
            body="Small business operators say the current subscription is too expensive and the manual export process takes too long every week.",
            source_url="offline://youtube/demo-youtube-comments",
            published_at="2026-05-21T09:15:00",
            metadata={"fixture": True},
        ),
    ]


def build_offline_demo_snapshot() -> Dict:
    ideas, summary = run_demand_scan([], [], "", [], "us", extra_items=build_demo_raw_items())
    summary["saved_count"] = 0

    rows = ideas_to_dicts(ideas)
    history_summary = {
        "records": [],
        "total": 0,
        "category_counts": {},
        "repeated_signals": [],
    }
    clusters = build_opportunity_clusters(rows, history_summary)
    clusters = enrich_clusters_with_pipeline(clusters)
    source_metrics = build_source_metrics_from_counts(
        summary.get("raw_source_counts", {}),
        summary.get("candidate_source_counts", {}),
        clusters,
        summary.get("source_error_counts", {}),
    )

    return build_dashboard_snapshot(
        ideas=rows,
        summary=summary,
        history_summary=history_summary,
        markdown_report=format_markdown_report(ideas, summary),
        opportunity_clusters=clusters,
        decision_summary=build_decision_summary(clusters),
        analysis_metadata={
            "analysis_provider": "offline_demo",
            "analysis_status": "fixture",
        },
        source_metrics=source_metrics,
    )


def write_offline_demo_snapshot(path: Optional[Path] = None) -> Dict:
    snapshot = build_offline_demo_snapshot()
    write_dashboard_snapshot(snapshot, Path(path or DEFAULT_OFFLINE_DEMO_OUTPUT))
    return snapshot


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an offline demo snapshot without API keys or network data.")
    parser.add_argument("--output", default=str(DEFAULT_OFFLINE_DEMO_OUTPUT))
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    snapshot = write_offline_demo_snapshot(Path(args.output))
    print(f"Offline demo snapshot written: {args.output}")
    print(f"Candidates: {snapshot['summary']['candidate_count']}")
    print(f"Clusters: {len(snapshot['opportunity_clusters'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
