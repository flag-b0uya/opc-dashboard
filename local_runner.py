#!/usr/bin/env python3
"""Run the demand engine locally and export a dashboard snapshot."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Union

from demand_engine import (
    DEFAULT_HN_QUERIES,
    DEFAULT_SUBREDDITS,
    format_markdown_report,
    get_history_summary,
    ideas_to_dicts,
    run_demand_scan,
    save_scan_to_history,
)
from snapshot_exporter import build_dashboard_snapshot, write_dashboard_snapshot


DEFAULT_CONFIG_PATH = Path("dashboard_config.json")
DEFAULT_OUTPUT_PATH = "data/dashboard_snapshot.json"


def _split_csv(value: str) -> List[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _as_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return _split_csv(value)
    if isinstance(value, Iterable):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def load_runner_config(path: Optional[Union[Path, str]]) -> Dict[str, Any]:
    if not path:
        if DEFAULT_CONFIG_PATH.exists():
            path = DEFAULT_CONFIG_PATH
        else:
            return {}
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Runner config must be a JSON object.")
    return payload


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run local demand scan and export Streamlit dashboard snapshot.")
    parser.add_argument("--config", help="Optional JSON config file. Defaults to dashboard_config.json when present.")
    parser.add_argument("--hn-query", action="append", dest="hn_queries", help="Hacker News query. Repeatable.")
    parser.add_argument("--subreddit", action="append", dest="subreddits", help="Reddit subreddit. Repeatable.")
    parser.add_argument("--reddit-query")
    parser.add_argument("--app-ids", help="Comma-separated App Store app IDs.")
    parser.add_argument("--app-store-country")
    parser.add_argument("--limit-per-source", type=int)
    parser.add_argument("--output")
    return parser.parse_args(argv)


def resolve_scan_options(args: argparse.Namespace) -> Dict[str, Any]:
    config = load_runner_config(args.config)
    hn_queries = args.hn_queries or _as_list(config.get("hn_queries")) or DEFAULT_HN_QUERIES
    subreddits = args.subreddits or _as_list(config.get("subreddits")) or DEFAULT_SUBREDDITS

    if args.app_ids is not None:
        app_ids = _split_csv(args.app_ids)
    else:
        app_ids = _as_list(config.get("app_ids"))

    return {
        "hn_queries": hn_queries,
        "subreddits": subreddits,
        "reddit_query": args.reddit_query
        or config.get("reddit_query")
        or "alternative OR expensive OR manual OR missing feature",
        "app_ids": app_ids,
        "app_store_country": args.app_store_country or config.get("app_store_country") or "us",
        "limit_per_source": args.limit_per_source or int(config.get("limit_per_source", 10)),
        "output": args.output or config.get("output") or DEFAULT_OUTPUT_PATH,
    }


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    options = resolve_scan_options(args)

    ideas, summary = run_demand_scan(
        hn_queries=options["hn_queries"],
        subreddits=options["subreddits"],
        reddit_query=options["reddit_query"],
        app_ids=options["app_ids"],
        app_store_country=options["app_store_country"],
        limit_per_source=options["limit_per_source"],
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
    output_path = Path(options["output"])
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
