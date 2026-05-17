from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from typing import Any
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

from .models import RawItemInput


USER_AGENT = "blue-ocean-demand-engine/0.1"


def _get_json(url: str, timeout: int = 20) -> Any:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_hn(config: dict[str, Any]) -> list[RawItemInput]:
    max_items = int(config.get("max_items", 100))
    lookback_hours = int(config.get("lookback_hours", 24))
    queries = config.get("queries") or ["alternative to", "too expensive", "I wish", "manual workflow"]
    after = int((datetime.now(timezone.utc) - timedelta(hours=lookback_hours)).timestamp())
    items: list[RawItemInput] = []

    for query in queries:
        url = (
            "https://hn.algolia.com/api/v1/search_by_date"
            f"?query={quote_plus(str(query))}&tags=story,comment&numericFilters=created_at_i>{after}"
        )
        payload = _get_json(url)
        for hit in payload.get("hits", []):
            object_id = str(hit.get("objectID") or "")
            title = str(hit.get("title") or hit.get("story_title") or "")
            body = str(hit.get("comment_text") or hit.get("story_text") or title)
            story_id = hit.get("story_id") or object_id
            if not body and not title:
                continue
            items.append(
                RawItemInput(
                    source="hn",
                    source_url=f"https://news.ycombinator.com/item?id={story_id}",
                    title=title,
                    body=body,
                    author=hit.get("author"),
                    published_at=hit.get("created_at"),
                    metadata={
                        "object_id": object_id,
                        "query": query,
                        "points": hit.get("points"),
                        "num_comments": hit.get("num_comments"),
                    },
                )
            )
            if len(items) >= max_items:
                return items
    return items


def fetch_reddit(config: dict[str, Any]) -> list[RawItemInput]:
    subreddits = config.get("subreddits") or ["SaaS", "Entrepreneur", "smallbusiness", "freelance", "webdev"]
    max_items = int(config.get("max_items_per_subreddit", 50))
    items: list[RawItemInput] = []

    for subreddit in subreddits:
        url = f"https://www.reddit.com/r/{quote_plus(str(subreddit))}/new.json?limit={max_items}"
        payload = _get_json(url)
        for child in payload.get("data", {}).get("children", []):
            data = child.get("data", {})
            title = str(data.get("title") or "")
            body = str(data.get("selftext") or title)
            permalink = data.get("permalink") or ""
            if not body and not title:
                continue
            published = data.get("created_utc")
            published_at = None
            if isinstance(published, (int, float)):
                published_at = datetime.fromtimestamp(published, timezone.utc).isoformat()
            items.append(
                RawItemInput(
                    source="reddit",
                    source_url=f"https://www.reddit.com{permalink}",
                    title=title,
                    body=body,
                    author=data.get("author"),
                    published_at=published_at,
                    metadata={
                        "subreddit": subreddit,
                        "score": data.get("score"),
                        "num_comments": data.get("num_comments"),
                    },
                )
            )
    return items


def fetch_app_store(config: dict[str, Any]) -> list[RawItemInput]:
    apps = config.get("apps") or []
    max_reviews = int(config.get("max_reviews_per_app", 50))
    items: list[RawItemInput] = []

    for app in apps:
        app_id = app.get("id")
        country = app.get("country", "us")
        name = app.get("name", app_id)
        if not app_id:
            continue
        url = f"https://itunes.apple.com/{country}/rss/customerreviews/id={quote_plus(str(app_id))}/sortBy=mostRecent/json"
        payload = _get_json(url)
        entries = payload.get("feed", {}).get("entry", [])
        for entry in entries[:max_reviews]:
            title = entry.get("title", {}).get("label", "")
            body = entry.get("content", {}).get("label", "")
            review_id = entry.get("id", {}).get("label", "")
            rating = entry.get("im:rating", {}).get("label")
            if not body and not title:
                continue
            items.append(
                RawItemInput(
                    source="app_store",
                    source_url=review_id or f"https://apps.apple.com/{country}/app/id{app_id}",
                    title=str(title),
                    body=str(body),
                    author=entry.get("author", {}).get("name", {}).get("label"),
                    published_at=entry.get("updated", {}).get("label"),
                    metadata={"app_name": name, "app_id": app_id, "country": country, "rating": rating},
                )
            )
    return items


def fetch_source(source: str, config: dict[str, Any]) -> list[RawItemInput]:
    if source == "hn":
        return fetch_hn(config.get("hn", {}))
    if source == "reddit":
        return fetch_reddit(config.get("reddit", {}))
    if source == "app_store":
        return fetch_app_store(config.get("app_store", {}))
    raise ValueError(f"unknown source: {source}")


def fetch_all(config: dict[str, Any]) -> list[RawItemInput]:
    items: list[RawItemInput] = []
    for source in ("hn", "reddit", "app_store"):
        try:
            items.extend(fetch_source(source, config))
        except Exception as exc:
            items.append(
                RawItemInput(
                    source="hn",
                    source_url=f"error://{source}",
                    title=f"{source} fetch failed",
                    body=f"Fetcher error: {exc}",
                    metadata={"source": source, "error": str(exc), "fetch_failed": True},
                )
            )
    return [item for item in items if not item.metadata.get("fetch_failed")]

