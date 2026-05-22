"""Reddit thread container adapter."""

from __future__ import annotations

from datetime import datetime, timezone
import urllib.parse
from typing import Callable, Dict, List, Optional, Tuple

from container_discovery import rank_containers
from http_json import fetch_json_url


FetchJson = Callable[[str, Optional[Dict[str, str]]], Dict]


def _iso_from_utc(value) -> str:
    try:
        return datetime.fromtimestamp(float(value), tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return ""


def _thread_container(post: Dict, subreddit: str, source_query: str) -> Dict:
    post_id = str(post.get("id") or post.get("name") or "")
    permalink = post.get("permalink") or ""
    return {
        "container_id": f"reddit-{subreddit}-{post_id}",
        "platform": "reddit",
        "container_type": "thread",
        "title": post.get("title", ""),
        "url": f"https://www.reddit.com{permalink}" if permalink else str(post.get("url") or ""),
        "author": post.get("author", ""),
        "published_at": _iso_from_utc(post.get("created_utc")),
        "source_query": source_query,
        "comment_count": int(post.get("num_comments") or 0),
        "like_count": int(post.get("score") or 0),
        "view_count": 0,
    }


def search_reddit_containers(
    subreddit: str,
    query: str = "",
    limit: int = 10,
    fetch_json: FetchJson = fetch_json_url,
) -> Tuple[List[Dict], List[str]]:
    clean_subreddit = subreddit.strip().strip("/")
    if not clean_subreddit:
        return [], ["Reddit subreddit missing; skip reddit source."]
    if query.strip():
        params = urllib.parse.urlencode({
            "q": query.strip(),
            "restrict_sr": "1",
            "sort": "new",
            "limit": max(1, min(int(limit), 25)),
        })
        url = f"https://www.reddit.com/r/{urllib.parse.quote(clean_subreddit)}/search.json?{params}"
    else:
        params = urllib.parse.urlencode({"limit": max(1, min(int(limit), 25))})
        url = f"https://www.reddit.com/r/{urllib.parse.quote(clean_subreddit)}/new.json?{params}"
    try:
        payload = fetch_json(url, None)
    except Exception as exc:
        return [], [f"Reddit `r/{clean_subreddit}` container search failed: {exc}"]
    children = payload.get("data", {}).get("children", [])
    containers = [
        _thread_container(child.get("data", {}), clean_subreddit, query)
        for child in children
        if isinstance(child, dict)
    ]
    return rank_containers(containers), []
