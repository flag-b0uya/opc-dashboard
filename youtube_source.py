"""YouTube container adapter for the OPC pain intelligence pipeline."""

from __future__ import annotations

import urllib.parse
from typing import Callable, Dict, List, Optional, Tuple

from container_discovery import rank_containers
from http_json import fetch_json_url


FetchJson = Callable[[str, Optional[Dict[str, str]]], Dict]


def _video_container(item: Dict, source_query: str) -> Dict:
    snippet = item.get("snippet") or {}
    video_id = ""
    raw_id = item.get("id")
    if isinstance(raw_id, dict):
        video_id = str(raw_id.get("videoId") or "")
    else:
        video_id = str(raw_id or "")
    return {
        "container_id": f"youtube-{video_id}",
        "platform": "youtube",
        "container_type": "video",
        "title": snippet.get("title", ""),
        "url": f"https://www.youtube.com/watch?v={urllib.parse.quote(video_id)}" if video_id else "",
        "author": snippet.get("channelTitle", ""),
        "published_at": snippet.get("publishedAt", ""),
        "source_query": source_query,
        "comment_count": 0,
        "like_count": 0,
        "view_count": 0,
    }


def search_youtube_containers(
    query: str,
    api_key: str = "",
    max_results: int = 10,
    fetch_json: FetchJson = fetch_json_url,
) -> Tuple[List[Dict], List[str]]:
    if not api_key:
        return [], ["YouTube API key missing; skip youtube source."]
    params = urllib.parse.urlencode({
        "part": "snippet",
        "type": "video",
        "q": query,
        "maxResults": max(1, min(int(max_results), 25)),
        "key": api_key,
    })
    url = f"https://www.googleapis.com/youtube/v3/search?{params}"
    try:
        payload = fetch_json(url, None)
    except Exception as exc:
        return [], [f"YouTube `{query}` search failed: {exc}"]
    containers = [_video_container(item, query) for item in payload.get("items", []) if isinstance(item, dict)]
    return rank_containers(containers), []
