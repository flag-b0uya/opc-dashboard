#!/usr/bin/env python3
"""Source fetch cache and coverage gates for OPC snapshot generation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
import json
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Tuple

from demand_engine import RawItem


DEFAULT_SOURCE_CACHE_PATH = Path("data/source_cache.json")
DEFAULT_CACHE_MAX_AGE_HOURS = 72


@dataclass
class SourceFetchResult:
    items: List[RawItem]
    errors: List[str]


def _now() -> datetime:
    return datetime.now()


def _raw_item_from_dict(payload: Dict) -> RawItem:
    return RawItem(
        id=str(payload.get("id", "")),
        source=str(payload.get("source", "")),
        title=str(payload.get("title", "")),
        body=str(payload.get("body", "")),
        source_url=str(payload.get("source_url", "")),
        published_at=str(payload.get("published_at", "")),
        metadata=dict(payload.get("metadata") or {}),
    )


def load_source_cache(path: Path = DEFAULT_SOURCE_CACHE_PATH) -> Dict:
    path = Path(path)
    if not path.exists():
        return {"version": 1, "sources": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"version": 1, "sources": {}}
    if not isinstance(payload, dict):
        return {"version": 1, "sources": {}}
    payload.setdefault("version", 1)
    payload.setdefault("sources", {})
    return payload


def write_source_cache(cache: Dict, path: Path = DEFAULT_SOURCE_CACHE_PATH) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def _cache_entry_is_fresh(entry: Dict, max_age_hours: int) -> bool:
    fetched_at = entry.get("fetched_at")
    if not fetched_at:
        return False
    try:
        fetched_time = datetime.fromisoformat(fetched_at)
    except ValueError:
        return False
    return _now() - fetched_time <= timedelta(hours=max_age_hours)


def _status(
    source_label: str,
    status: str,
    items: Iterable[RawItem],
    errors: Iterable[str],
    *,
    used_cache: bool = False,
    cache_age_hours: int | None = None,
) -> Dict:
    item_list = list(items)
    return {
        "source": source_label,
        "status": status,
        "count": len(item_list),
        "errors": list(errors),
        "used_cache": used_cache,
        "cache_age_hours": cache_age_hours,
    }


def run_source_with_cache(
    cache_path: Path,
    *,
    source_key: str,
    source_label: str,
    enabled: bool,
    fetcher: Callable[[], SourceFetchResult],
    max_age_hours: int = DEFAULT_CACHE_MAX_AGE_HOURS,
) -> Tuple[List[RawItem], Dict]:
    if not enabled:
        return [], _status(source_label, "disabled", [], [])

    cache = load_source_cache(cache_path)
    try:
        result = fetcher()
    except Exception as exc:
        result = SourceFetchResult([], [str(exc)])

    if result.items:
        status_name = "partial" if result.errors else "ok"
        cache["sources"][source_key] = {
            "source": source_label,
            "fetched_at": _now().isoformat(timespec="seconds"),
            "item_count": len(result.items),
            "items": [asdict(item) for item in result.items],
        }
        write_source_cache(cache, cache_path)
        return result.items, _status(source_label, status_name, result.items, result.errors)

    entry = cache.get("sources", {}).get(source_key) or {}
    if entry and _cache_entry_is_fresh(entry, max_age_hours):
        cached_items = [_raw_item_from_dict(item) for item in entry.get("items", [])]
        if cached_items:
            fetched_at = datetime.fromisoformat(entry["fetched_at"])
            age = max(0, round((_now() - fetched_at).total_seconds() / 3600))
            return cached_items, _status(
                source_label,
                "fallback",
                cached_items,
                result.errors,
                used_cache=True,
                cache_age_hours=age,
            )

    return [], _status(source_label, "failed", [], result.errors)


class SourceReliabilityReport:
    def __init__(self, statuses: List[Dict]):
        self.statuses = statuses

    def _usable_statuses(self) -> List[Dict]:
        return [
            status for status in self.statuses
            if status.get("status") in {"ok", "partial", "fallback"} and int(status.get("count") or 0) > 0
        ]

    def errors(self) -> List[str]:
        messages: List[str] = []
        for status in self.statuses:
            if status.get("status") == "failed":
                messages.extend(status.get("errors") or [])
        return messages

    def to_source_health(self, *, raw_count: int, unique_count: int, candidate_count: int) -> Dict:
        usable = self._usable_statuses()
        fallback_count = sum(1 for status in usable if status.get("status") == "fallback")
        partial_count = sum(1 for status in usable if status.get("status") == "partial")
        failed_count = sum(1 for status in self.statuses if status.get("status") == "failed")
        publishable = bool(usable) and candidate_count > 0

        if not publishable:
            coverage_status = "blocked"
        elif fallback_count or partial_count or failed_count:
            coverage_status = "degraded"
        else:
            coverage_status = "ok"

        return {
            "status": coverage_status,
            "coverage_status": coverage_status,
            "publishable": publishable,
            "raw_count": raw_count,
            "unique_count": unique_count,
            "candidate_count": candidate_count,
            "error_count": sum(len(status.get("errors") or []) for status in self.statuses),
            "errors": [error for status in self.statuses for error in (status.get("errors") or [])],
            "sources": self.statuses,
            "usable_source_count": len(usable),
            "cache_fallback_count": fallback_count,
            "partial_source_count": partial_count,
        }
