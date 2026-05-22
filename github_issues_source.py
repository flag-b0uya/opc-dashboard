"""GitHub Issues container adapter."""

from __future__ import annotations

import urllib.parse
from typing import Callable, Dict, List, Optional, Tuple

from container_discovery import rank_containers
from http_json import fetch_json_url


FetchJson = Callable[[str, Optional[Dict[str, str]]], Dict]


def _repo_name(repository_url: str) -> str:
    marker = "/repos/"
    if marker not in repository_url:
        return ""
    return repository_url.split(marker, 1)[1]


def _issue_container(issue: Dict, source_query: str) -> Dict:
    issue_id = str(issue.get("id") or issue.get("number") or "")
    return {
        "container_id": f"github-{issue_id}",
        "platform": "github",
        "container_type": "issue",
        "title": issue.get("title", ""),
        "url": issue.get("html_url", ""),
        "author": (issue.get("user") or {}).get("login", ""),
        "published_at": issue.get("created_at", ""),
        "source_query": source_query,
        "comment_count": int(issue.get("comments") or 0),
        "like_count": 0,
        "view_count": 0,
        "repository": _repo_name(str(issue.get("repository_url", ""))),
    }


def search_github_issue_containers(
    query: str,
    limit: int = 10,
    token: str = "",
    fetch_json: FetchJson = fetch_json_url,
) -> Tuple[List[Dict], List[str]]:
    if not query.strip():
        return [], ["GitHub issue query missing; skip github source."]
    params = urllib.parse.urlencode({
        "q": f"{query.strip()} type:issue",
        "sort": "updated",
        "order": "desc",
        "per_page": max(1, min(int(limit), 25)),
    })
    headers = {"Authorization": f"Bearer {token}"} if token else None
    url = f"https://api.github.com/search/issues?{params}"
    try:
        payload = fetch_json(url, headers)
    except Exception as exc:
        return [], [f"GitHub Issues `{query}` search failed: {exc}"]
    containers = [_issue_container(item, query) for item in payload.get("items", []) if isinstance(item, dict)]
    return rank_containers(containers), []
