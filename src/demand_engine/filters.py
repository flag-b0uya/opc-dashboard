from __future__ import annotations

import re

from .models import CandidateInput, RawItemInput, normalize_text, stable_hash


PAIN_RULES = [
    "alternative to",
    "i wish",
    "too expensive",
    "doesn't support",
    "does not support",
    "manual",
    "slow",
    "broken",
    "missing",
    "frustrating",
    "switching from",
    "looking for a tool",
    "pay for",
    "budget",
    "subscription",
    "client work",
]


def detect_language(text: str) -> str:
    if re.search(r"[\u4e00-\u9fff]", text):
        return "zh"
    if re.search(r"[a-zA-Z]", text):
        return "en"
    return "unknown"


def matched_rules(text: str) -> list[str]:
    lowered = text.lower()
    return [rule for rule in PAIN_RULES if rule in lowered]


def filter_candidates(
    raw_items: list[RawItemInput],
    existing_body_hashes: set[str],
    min_chars: int = 30,
) -> list[CandidateInput]:
    candidates: list[CandidateInput] = []
    seen_hashes = set(existing_body_hashes)

    for item in raw_items:
        combined = normalize_text(f"{item.title}\n{item.body}")
        body_hash = stable_hash(combined.lower())
        if len(combined) < min_chars or body_hash in seen_hashes:
            continue

        rules = matched_rules(combined)
        if not rules:
            continue

        seen_hashes.add(body_hash)
        candidates.append(
            CandidateInput(
                raw_item_id=item.id,
                normalized_text=combined,
                matched_rules=rules,
                language=detect_language(combined),
                source_url=item.source_url,
                title=item.title,
                body_hash=body_hash,
            )
        )

    return candidates

