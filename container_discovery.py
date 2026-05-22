"""Score and select discussion containers before comment sampling."""

from __future__ import annotations

import copy
from typing import Dict, Iterable, List

from query_bank import competitor_terms, noise_terms, pain_terms_en, pain_terms_zh, workflow_terms


def _text(container: Dict) -> str:
    parts = [
        container.get("title", ""),
        container.get("description", ""),
        container.get("source_query", ""),
        container.get("platform", ""),
        container.get("container_type", ""),
    ]
    return " ".join(str(part) for part in parts if part).lower()


def _has_any(text: str, terms: Iterable[str]) -> bool:
    return any(term.lower() in text for term in terms)


def _count_any(text: str, terms: Iterable[str]) -> int:
    return sum(1 for term in terms if term.lower() in text)


def _safe_int(value) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _engagement_points(container: Dict) -> int:
    comments = _safe_int(container.get("comment_count"))
    likes = _safe_int(container.get("like_count"))
    views = _safe_int(container.get("view_count"))
    if comments >= 50 or likes >= 100 or views >= 5000:
        return 10
    if comments >= 15 or likes >= 25 or views >= 1000:
        return 7
    if comments >= 5 or likes >= 10 or views >= 250:
        return 4
    return 0


def score_container(container: Dict, threshold: int = 35) -> Dict:
    row = copy.deepcopy(container)
    text = _text(row)
    pain_query_match = 1 if _has_any(text, [*pain_terms_en, *pain_terms_zh]) else 0
    workflow_query_match = 1 if _has_any(text, workflow_terms) else 0
    competitor_query_match = 1 if _has_any(text, competitor_terms) else 0
    engagement_score = _engagement_points(row)
    recency_score = 10 if str(row.get("published_at", "")).startswith(("2026", "2025")) else 0
    niche_focus = 10 if _count_any(text, ["shopify", "invoice", "support", "ticket", "crm", "github", "reddit", "财务", "客服"]) else 0
    marketing_noise_penalty = 20 if _has_any(text, noise_terms) else 0

    score = (
        pain_query_match * 20
        + workflow_query_match * 15
        + competitor_query_match * 15
        + engagement_score
        + recency_score
        + niche_focus
        - marketing_noise_penalty
    )
    row["container_score"] = max(0, min(score, 100))
    row["selected_for_sampling"] = row["container_score"] >= threshold
    return row


def rank_containers(containers: Iterable[Dict], limit: int | None = None, threshold: int = 35) -> List[Dict]:
    ranked = [score_container(container, threshold=threshold) for container in containers]
    ranked.sort(
        key=lambda item: (
            item.get("container_score", 0),
            _safe_int(item.get("comment_count")),
            _safe_int(item.get("like_count")),
        ),
        reverse=True,
    )
    if limit is not None:
        return ranked[: max(0, int(limit))]
    return ranked
