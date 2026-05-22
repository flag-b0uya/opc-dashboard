"""Orchestrate container discovery across source adapters."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Tuple

from github_issues_source import search_github_issue_containers
from http_json import fetch_json_url
from reddit_source import search_reddit_containers
from youtube_source import search_youtube_containers


CONTAINERS_FILE = Path(__file__).resolve().parent / "data" / "containers.json"
FetchJson = Callable[[str, Optional[Dict[str, str]]], Dict]


def _sort_containers(containers: Iterable[Dict]) -> List[Dict]:
    return sorted(
        containers,
        key=lambda item: (
            int(item.get("container_score") or 0),
            int(item.get("comment_count") or 0),
            int(item.get("like_count") or 0),
        ),
        reverse=True,
    )


def collect_containers(
    youtube_queries: Optional[List[str]] = None,
    reddit_targets: Optional[List[Dict]] = None,
    github_queries: Optional[List[str]] = None,
    youtube_api_key: str = "",
    github_token: str = "",
    per_source_limit: int = 10,
    fetch_json: FetchJson = fetch_json_url,
) -> Tuple[List[Dict], List[str]]:
    containers: List[Dict] = []
    errors: List[str] = []

    for query in youtube_queries or []:
        rows, source_errors = search_youtube_containers(
            query,
            api_key=youtube_api_key,
            max_results=per_source_limit,
            fetch_json=fetch_json,
        )
        containers.extend(rows)
        errors.extend(source_errors)

    for target in reddit_targets or []:
        rows, source_errors = search_reddit_containers(
            str(target.get("subreddit", "")),
            str(target.get("query", "")),
            limit=per_source_limit,
            fetch_json=fetch_json,
        )
        containers.extend(rows)
        errors.extend(source_errors)

    for query in github_queries or []:
        rows, source_errors = search_github_issue_containers(
            query,
            limit=per_source_limit,
            token=github_token,
            fetch_json=fetch_json,
        )
        containers.extend(rows)
        errors.extend(source_errors)

    return _sort_containers(containers), errors


def save_containers(containers: List[Dict], path: Optional[Path] = None) -> None:
    target = Path(path or CONTAINERS_FILE)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(containers, ensure_ascii=False, indent=2), encoding="utf-8")


def load_containers(path: Optional[Path] = None) -> List[Dict]:
    target = Path(path or CONTAINERS_FILE)
    if not target.exists():
        return []
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return payload if isinstance(payload, list) else []


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect scored containers for later comment sampling.")
    parser.add_argument("--youtube-query", action="append", default=[])
    parser.add_argument("--reddit", action="append", default=[], help="Format: subreddit[:query]")
    parser.add_argument("--github-query", action="append", default=[])
    parser.add_argument("--youtube-api-key", default=os.environ.get("YOUTUBE_API_KEY", ""))
    parser.add_argument("--github-token", default=os.environ.get("GITHUB_TOKEN", ""))
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--output", default=str(CONTAINERS_FILE))
    return parser.parse_args(argv)


def _reddit_targets(values: List[str]) -> List[Dict]:
    targets = []
    for value in values:
        subreddit, _, query = value.partition(":")
        if subreddit.strip():
            targets.append({"subreddit": subreddit.strip(), "query": query.strip()})
    return targets


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    containers, errors = collect_containers(
        youtube_queries=args.youtube_query,
        reddit_targets=_reddit_targets(args.reddit),
        github_queries=args.github_query,
        youtube_api_key=args.youtube_api_key,
        github_token=args.github_token,
        per_source_limit=args.limit,
    )
    save_containers(containers, Path(args.output))
    print(f"Containers written: {args.output}")
    print(f"Containers: {len(containers)}")
    if errors:
        print("Errors:")
        for error in errors:
            print(f"  - {error}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
