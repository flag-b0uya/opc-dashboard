#!/usr/bin/env python3
"""Run the demand engine locally and export a dashboard snapshot."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Union

from codex_analysis import CodexAnalysisError, analyze_clusters_with_codex
from demand_engine import (
    build_decision_summary,
    build_opportunity_clusters,
    dedupe_items,
    fetch_app_store_reviews,
    fetch_hn_items,
    fetch_reddit_items,
    filter_candidates,
    format_markdown_report,
    get_history_summary,
    get_repeat_counts,
    ideas_to_dicts,
    save_scan_to_history,
    score_candidate,
)
from manual_intake import load_manual_items, manual_items_to_raw_items
from pipeline_enricher import enrich_clusters_with_pipeline
from query_bank import runner_app_ids, runner_hn_queries, runner_subreddits
from snapshot_exporter import build_dashboard_snapshot, write_dashboard_snapshot
from source_metrics import (
    append_source_metrics_history,
    apply_source_metric_trends,
    build_source_metrics_from_counts,
    load_source_metrics_history,
    save_source_metrics,
)
from source_reliability import (
    DEFAULT_SOURCE_CACHE_PATH,
    SourceFetchResult,
    SourceReliabilityReport,
    run_source_with_cache,
)


DEFAULT_CONFIG_PATH = Path("dashboard_config.json")
DEFAULT_OUTPUT_PATH = "data/dashboard_snapshot.json"
DEFAULT_HISTORY_MAX_RECORDS = 10000
DEFAULT_RUNNER_HN_QUERIES = list(runner_hn_queries)
DEFAULT_RUNNER_SUBREDDITS = list(runner_subreddits)
DEFAULT_RUNNER_APP_IDS = list(runner_app_ids)


def failed_snapshot_path(output_path: Path) -> Path:
    return output_path.parent / "failed_snapshot.json"


def is_empty_failed_scan(summary: Dict[str, Any]) -> bool:
    return (
        int(summary.get("raw_count") or 0) == 0
        and int(summary.get("candidate_count") or 0) == 0
        and bool(summary.get("errors"))
    )


def should_preserve_existing_snapshot(summary: Dict[str, Any], output_path: Path) -> bool:
    return output_path.exists() and is_empty_failed_scan(summary)


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
    parser.add_argument("--history-max-records", type=int)
    parser.add_argument("--output")
    parser.add_argument("--analysis-provider", choices=["heuristic", "codex"], default=None)
    parser.add_argument("--source-cache", help="Local last-good source cache path.")
    return parser.parse_args(argv)


def resolve_scan_options(args: argparse.Namespace) -> Dict[str, Any]:
    config = load_runner_config(args.config)
    if args.hn_queries is not None:
        hn_queries = args.hn_queries
    elif "hn_queries" in config:
        hn_queries = _as_list(config.get("hn_queries"))
    else:
        hn_queries = DEFAULT_RUNNER_HN_QUERIES

    if args.subreddits is not None:
        subreddits = args.subreddits
    elif "subreddits" in config:
        subreddits = _as_list(config.get("subreddits"))
    else:
        subreddits = DEFAULT_RUNNER_SUBREDDITS

    if args.app_ids is not None:
        app_ids = _split_csv(args.app_ids)
    elif "app_ids" in config:
        app_ids = _as_list(config.get("app_ids"))
    else:
        app_ids = DEFAULT_RUNNER_APP_IDS

    return {
        "hn_queries": hn_queries,
        "subreddits": subreddits,
        "reddit_query": args.reddit_query
        or config.get("reddit_query")
        or "alternative OR expensive OR manual OR missing feature",
        "app_ids": app_ids,
        "app_store_country": args.app_store_country or config.get("app_store_country") or "us",
        "limit_per_source": args.limit_per_source or int(config.get("limit_per_source", 10)),
        "history_max_records": args.history_max_records
        or int(config.get("history_max_records", DEFAULT_HISTORY_MAX_RECORDS)),
        "output": args.output or config.get("output") or DEFAULT_OUTPUT_PATH,
        "analysis_provider": args.analysis_provider or config.get("analysis_provider") or "heuristic",
        "source_cache_path": args.source_cache or config.get("source_cache_path") or str(DEFAULT_SOURCE_CACHE_PATH),
    }


def _fetch_result(fetch_output) -> SourceFetchResult:
    items, errors = fetch_output
    return SourceFetchResult(items=list(items), errors=list(errors))


def _source_status(source_label: str, status: str, items: Iterable, errors: Iterable[str]) -> Dict[str, Any]:
    item_list = list(items)
    return {
        "source": source_label,
        "status": status,
        "count": len(item_list),
        "errors": list(errors),
        "used_cache": False,
        "cache_age_hours": None,
    }


def fetch_items_with_reliability(options: Dict[str, Any], extra_items: Optional[Iterable] = None):
    cache_path = Path(options["source_cache_path"])
    statuses = []
    all_items = []

    hn_items, hn_status = run_source_with_cache(
        cache_path,
        source_key="hacker_news",
        source_label="Hacker News",
        enabled=bool(options["hn_queries"]),
        fetcher=lambda: _fetch_result(fetch_hn_items(options["hn_queries"], options["limit_per_source"])),
    )
    all_items.extend(hn_items)
    statuses.append(hn_status)

    reddit_items, reddit_status = run_source_with_cache(
        cache_path,
        source_key="reddit",
        source_label="Reddit",
        enabled=bool(options["subreddits"]),
        fetcher=lambda: _fetch_result(
            fetch_reddit_items(options["subreddits"], options["reddit_query"], options["limit_per_source"])
        ),
    )
    all_items.extend(reddit_items)
    statuses.append(reddit_status)

    app_items, app_status = run_source_with_cache(
        cache_path,
        source_key="app_store",
        source_label="App Store",
        enabled=bool(options["app_ids"]),
        fetcher=lambda: _fetch_result(
            fetch_app_store_reviews(
                options["app_ids"],
                options["app_store_country"],
                options["limit_per_source"],
            )
        ),
    )
    all_items.extend(app_items)
    statuses.append(app_status)

    manual_items = list(extra_items or [])
    if manual_items:
        all_items.extend(manual_items)
        statuses.append(_source_status("Manual intake", "ok", manual_items, []))

    return all_items, SourceReliabilityReport(statuses)


def score_items(all_items):
    unique_items = dedupe_items(all_items)
    candidates = filter_candidates(unique_items)
    scored = [score_candidate(item, rules) for item, rules in candidates]
    repeat_counts = get_repeat_counts(scored, days=7)
    for idea in scored:
        idea.repeat_7d = repeat_counts.get(idea.signal_key, 1)
    scored.sort(key=lambda idea: idea.total_score, reverse=True)
    return unique_items, candidates, scored


def _count_items_by_source(items: Iterable) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for item in items:
        source = str(getattr(item, "source", "") or "Unknown")
        counts[source] = counts.get(source, 0) + 1
    return counts


def _source_error_counts(statuses: Iterable[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for status in statuses:
        errors = status.get("errors") or []
        if errors:
            source = str(status.get("source") or "Unknown")
            counts[source] = counts.get(source, 0) + len(errors)
    return counts


def _build_failed_snapshot(snapshot: Dict[str, Any], output_path: Path) -> int:
    failed_path = failed_snapshot_path(output_path)
    write_dashboard_snapshot(snapshot, failed_path)
    if output_path.exists():
        print(f"Snapshot preserved: {output_path}")
    else:
        print(f"Snapshot not written: {output_path}")
    print(f"Failed snapshot written: {failed_path}")
    return 0 if output_path.exists() else 1


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    options = resolve_scan_options(args)
    manual_raw_items = manual_items_to_raw_items(load_manual_items())

    all_items, reliability_report = fetch_items_with_reliability(options, manual_raw_items)
    unique_items, candidates, ideas = score_items(all_items)
    summary = {
        "raw_count": len(all_items),
        "unique_count": len(unique_items),
        "candidate_count": len(candidates),
        "build_now_count": sum(1 for idea in ideas if idea.verdict == "Build Now"),
        "monitor_count": sum(1 for idea in ideas if idea.verdict == "Monitor"),
        "discard_count": sum(1 for idea in ideas if idea.verdict == "Discard"),
        "errors": reliability_report.errors(),
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "raw_source_counts": _count_items_by_source(unique_items),
        "candidate_source_counts": _count_items_by_source(item for item, _rules in candidates),
        "source_error_counts": _source_error_counts(reliability_report.statuses),
    }
    source_health = reliability_report.to_source_health(
        raw_count=summary["raw_count"],
        unique_count=summary["unique_count"],
        candidate_count=summary["candidate_count"],
    )

    saved_count = 0
    if source_health["publishable"] and not is_empty_failed_scan(summary):
        saved_count = save_scan_to_history(ideas, summary, max_records=options["history_max_records"])
    summary["saved_count"] = saved_count

    report = format_markdown_report(ideas, summary)
    rows = ideas_to_dicts(ideas)
    history_summary = get_history_summary(days=7)
    opportunity_clusters = build_opportunity_clusters(rows, history_summary)
    analysis_metadata = {
        "analysis_provider": options["analysis_provider"],
        "analysis_status": "heuristic",
    }
    if options["analysis_provider"] == "codex" and opportunity_clusters:
        try:
            opportunity_clusters, analysis_metadata = analyze_clusters_with_codex(rows, opportunity_clusters)
        except CodexAnalysisError as exc:
            analysis_metadata = {
                "analysis_provider": "codex",
                "analysis_status": "fallback",
                "analysis_error": str(exc),
            }
            summary.setdefault("errors", []).append(f"Codex analysis fallback: {exc}")

    opportunity_clusters = enrich_clusters_with_pipeline(opportunity_clusters)
    source_metric_rows = build_source_metrics_from_counts(
        summary.get("raw_source_counts", {}),
        summary.get("candidate_source_counts", {}),
        opportunity_clusters,
        summary.get("source_error_counts", {}),
    )
    source_metric_rows = apply_source_metric_trends(source_metric_rows, load_source_metrics_history())
    decision_summary = build_decision_summary(opportunity_clusters)
    snapshot = build_dashboard_snapshot(
        ideas=rows,
        summary=summary,
        history_summary=history_summary,
        markdown_report=report,
        opportunity_clusters=opportunity_clusters,
        decision_summary=decision_summary,
        source_health=source_health,
        analysis_metadata=analysis_metadata,
        source_metrics=source_metric_rows,
    )
    output_path = Path(options["output"])

    if not source_health["publishable"] or is_empty_failed_scan(summary):
        print("Snapshot blocked: source coverage is not publishable.")
        print(f"Coverage: {source_health.get('coverage_status')}")
        for error in source_health.get("errors", []):
            print(f"  {error}")
        exit_code = _build_failed_snapshot(snapshot, output_path)
        print(f"Candidates: {summary.get('candidate_count', 0)}")
        print(f"Errors: {len(summary.get('errors', []))}")
        return exit_code

    save_source_metrics(source_metric_rows)
    append_source_metrics_history(source_metric_rows, summary.get("generated_at", ""))
    write_dashboard_snapshot(snapshot, output_path)

    print(f"Snapshot written: {output_path}")
    print(f"Candidates: {summary.get('candidate_count', 0)}")
    print(f"Build Now: {summary.get('build_now_count', 0)}")
    print(f"Source coverage: {source_health.get('coverage_status', 'unknown')}")
    print(f"Source cache: {options['source_cache_path']}")
    print(f"Analysis: {analysis_metadata.get('analysis_provider')} / {analysis_metadata.get('analysis_status')}")
    print("Next:")
    print(f"  git add {output_path}")
    print('  git commit -m "Update dashboard snapshot"')
    print("  git push origin main")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
