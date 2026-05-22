"""Bounded comment sampling for selected containers."""

from __future__ import annotations

import copy
from typing import Dict, Iterable, List

from query_bank import competitor_terms, pain_terms_en, pain_terms_zh, workflow_terms


def _safe_int(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _relevance(comment: Dict) -> int:
    text = str(comment.get("text") or comment.get("body") or "").lower()
    terms = [*pain_terms_en, *pain_terms_zh, *workflow_terms, *competitor_terms]
    return sum(1 for term in terms if term.lower() in text)


def _comment_id(comment: Dict) -> str:
    return str(comment.get("comment_id") or comment.get("id") or comment.get("text") or comment.get("body") or "")


def _add_unique(target: List[Dict], seen: set, comments: Iterable[Dict], limit: int) -> None:
    for comment in comments:
        if len(target) >= limit:
            return
        key = _comment_id(comment)
        if not key or key in seen:
            continue
        seen.add(key)
        target.append(copy.deepcopy(comment))


def sample_comments(comments: Iterable[Dict], max_comments: int = 50) -> List[Dict]:
    limit = max(0, int(max_comments))
    rows = list(comments)
    if limit == 0 or not rows:
        return []

    per_bucket = max(1, limit // 3)
    top = sorted(rows, key=lambda item: _safe_int(item.get("score")), reverse=True)
    newest = sorted(rows, key=lambda item: str(item.get("created_at", "")), reverse=True)
    relevant = sorted(rows, key=lambda item: (_relevance(item), _safe_int(item.get("score"))), reverse=True)

    sampled: List[Dict] = []
    seen: set = set()
    _add_unique(sampled, seen, top, per_bucket)
    _add_unique(sampled, seen, newest, per_bucket * 2)
    _add_unique(sampled, seen, relevant, limit)
    _add_unique(sampled, seen, rows, limit)
    return sampled


def sample_from_containers(
    containers: Iterable[Dict],
    comments_by_container: Dict[str, List[Dict]],
    max_per_container: int = 50,
) -> List[Dict]:
    sampled: List[Dict] = []
    for container in containers:
        if not container.get("selected_for_sampling"):
            continue
        container_id = str(container.get("container_id", ""))
        comments = comments_by_container.get(container_id, [])
        for comment in sample_comments(comments, max_comments=max_per_container):
            row = copy.deepcopy(comment)
            row["container_id"] = container_id
            sampled.append(row)
    return sampled
