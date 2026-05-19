#!/usr/bin/env python3
"""Check whether configured public data sources can be fetched locally."""

from __future__ import annotations

import argparse
import json
from typing import Dict, List, Tuple

from demand_engine import fetch_app_store_reviews, fetch_hn_items, fetch_reddit_items
from local_runner import parse_args as parse_runner_args
from local_runner import resolve_scan_options


def _sample_titles(items, limit: int = 3) -> List[str]:
    return [item.title for item in items[:limit] if item.title]


def _source_result(name: str, items, errors: List[str], targets: List[Dict]) -> Dict:
    return {
        "source": name,
        "count": len(items),
        "ok": bool(items) and not errors and all(target["ok"] for target in targets),
        "sample_titles": _sample_titles(items),
        "errors": errors,
        "targets": targets,
    }


def _target_result(name: str, items, errors: List[str]) -> Dict:
    return {
        "target": name,
        "count": len(items),
        "ok": bool(items) and not errors,
        "errors": errors,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check HN, Reddit, and App Store source adapters.")
    parser.add_argument("--config", help="Optional local_runner JSON config file.")
    parser.add_argument("--limit", type=int, default=3, help="Small per-source fetch limit for health checks.")
    parser.add_argument("--all-configured", action="store_true", help="Check every configured query/subreddit/app.")
    return parser.parse_args()


def run_checks(config_path: str = "", limit: int = 3, all_configured: bool = False) -> Tuple[List[Dict], int]:
    runner_args = parse_runner_args(["--config", config_path] if config_path else [])
    options = resolve_scan_options(runner_args)
    limit = max(1, min(limit, 5))
    source_count = None if all_configured else 2

    hn_queries = options["hn_queries"][:source_count]
    subreddits = options["subreddits"][:source_count]
    app_ids = options["app_ids"][:source_count]

    hn_items = []
    hn_errors = []
    hn_targets = []
    for query in hn_queries:
        items, errors = fetch_hn_items([query], limit)
        hn_items.extend(items)
        hn_errors.extend(errors)
        hn_targets.append(_target_result(query, items, errors))

    reddit_items = []
    reddit_errors = []
    reddit_targets = []
    for subreddit in subreddits:
        items, errors = fetch_reddit_items([subreddit], options["reddit_query"], limit)
        reddit_items.extend(items)
        reddit_errors.extend(errors)
        reddit_targets.append(_target_result(subreddit, items, errors))

    app_items = []
    app_errors = []
    app_targets = []
    for app_id in app_ids:
        items, errors = fetch_app_store_reviews([app_id], options["app_store_country"], limit)
        app_items.extend(items)
        app_errors.extend(errors)
        app_targets.append(_target_result(app_id, items, errors))

    results = []
    if hn_queries:
        results.append(_source_result("Hacker News", hn_items, hn_errors, hn_targets))
    if subreddits:
        results.append(_source_result("Reddit", reddit_items, reddit_errors, reddit_targets))
    if app_ids:
        results.append(_source_result("App Store", app_items, app_errors, app_targets))
    failed = [item for item in results if not item["ok"]]
    return results, 1 if failed or not results else 0


def main() -> int:
    args = parse_args()
    results, exit_code = run_checks(args.config or "", args.limit, args.all_configured)
    print(json.dumps({"results": results}, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
