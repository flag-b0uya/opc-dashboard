#!/usr/bin/env python3
"""Run the demand engine locally and export a dashboard snapshot."""

from __future__ import annotations

import argparse
from pathlib import Path

from demand_engine import (
    DEFAULT_HN_QUERIES,
    DEFAULT_SUBREDDITS,
    format_markdown_report,
    get_history_summary,
    ideas_to_dicts,
    run_demand_scan,
    save_scan_to_history,
)
from snapshot_exporter import SNAPSHOT_PATH, build_dashboard_snapshot, write_dashboard_snapshot


def _split_csv(value: str):
    return [item.strip() for item in value.split(",") if item.strip()]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run local demand scan and export Streamlit dashboard snapshot.")
    parser.add_argument("--hn-query", action="append", dest="hn_queries", help="Hacker News query. Repeatable.")
    parser.add_argument("--subreddit", action="append", dest="subreddits", help="Reddit subreddit. Repeatable.")
    parser.add_argument("--reddit-query", default="alternative OR expensive OR manual OR missing feature")
    parser.add_argument("--app-ids", default="", help="Comma-separated App Store app IDs.")
    parser.add_argument("--app-store-country", default="us")
    parser.add_argument("--limit-per-source", type=int, default=10)
    parser.add_argument("--output", default=str(SNAPSHOT_PATH))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    hn_queries = args.hn_queries or DEFAULT_HN_QUERIES
    subreddits = args.subreddits or DEFAULT_SUBREDDITS
    app_ids = _split_csv(args.app_ids)

    ideas, summary = run_demand_scan(
        hn_queries=hn_queries,
        subreddits=subreddits,
        reddit_query=args.reddit_query,
        app_ids=app_ids,
        app_store_country=args.app_store_country,
        limit_per_source=args.limit_per_source,
    )
    saved_count = save_scan_to_history(ideas, summary)
    summary["saved_count"] = saved_count

    report = format_markdown_report(ideas, summary)
    rows = ideas_to_dicts(ideas)
    snapshot = build_dashboard_snapshot(
        ideas=rows,
        summary=summary,
        history_summary=get_history_summary(days=7),
        markdown_report=report,
    )
    output_path = Path(args.output)
    write_dashboard_snapshot(snapshot, output_path)

    print(f"Snapshot written: {output_path}")
    print(f"Candidates: {summary.get('candidate_count', 0)}")
    print(f"Build Now: {summary.get('build_now_count', 0)}")
    print("Next:")
    print(f"  git add {output_path}")
    print('  git commit -m "Update dashboard snapshot"')
    print("  git push origin main")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
