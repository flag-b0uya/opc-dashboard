"""Opportunity funnel scoring for action-oriented cluster decisions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass
class FunnelInput:
    cluster_id: str
    title: str
    category: str
    evidence_score: int
    source_count: int
    count_7d: int
    top_score: int
    text: str


def _count_any(text: str, patterns: List[str]) -> int:
    lowered = text.lower()
    return sum(1 for pattern in patterns if pattern in lowered)


def score_funnel(item: FunnelInput) -> Dict:
    competitor_score = min(20, _count_any(item.text, [
        "alternative",
        "competitor",
        "expensive",
        "doesn't support",
        "missing",
        "tried",
        "替代",
        "竞品",
        "太贵",
        "缺少",
    ]) * 5)
    distribution_score = min(15, item.source_count * 4 + _count_any(item.text, [
        "reddit",
        "hacker news",
        "github",
        "shopify",
        "api",
        "community",
    ]) * 2)
    evidence_score = min(35, round(item.evidence_score * 0.35))
    repeat_score = min(15, item.count_7d * 5)
    quality_score = min(15, round(item.top_score * 0.15))
    risk_penalty = min(25, _count_any(item.text, [
        "hardware",
        "medical",
        "banking",
        "insurance",
        "legal",
        "合规",
        "医疗",
        "银行",
    ]) * 8)

    total_score = max(0, min(100, evidence_score + repeat_score + quality_score + competitor_score + distribution_score - risk_penalty))
    blockers: List[str] = []
    if item.evidence_score < 60:
        blockers.append("evidence chain is incomplete")
    if item.source_count < 2:
        blockers.append("needs a second independent source")
    if item.count_7d < 2:
        blockers.append("needs repeated signals")
    if competitor_score == 0:
        blockers.append("competitor or alternative pain is weak")
    if risk_penalty:
        blockers.append(f"risk penalty -{risk_penalty}")

    if total_score >= 78 and not blockers:
        verdict = "Build Now"
    elif total_score >= 55:
        verdict = "Validate Manually"
    elif total_score >= 35:
        verdict = "Monitor"
    else:
        verdict = "Discard"

    if verdict == "Build Now":
        next_step = "Run 5 user interviews and ask for a paid commitment before building."
    elif verdict == "Validate Manually":
        next_step = "Send 10 targeted DMs or one community post, then record replies and objections."
    elif verdict == "Monitor":
        next_step = "Collect more repeated signals and a clearer workflow before outreach."
    else:
        next_step = "Do not invest; keep only as a historical negative sample."

    return {
        "total_score": total_score,
        "verdict": verdict,
        "competitor_score": competitor_score,
        "distribution_score": distribution_score,
        "risk_penalty": risk_penalty,
        "reasons": [
            f"evidence {item.evidence_score}",
            f"sources {item.source_count}",
            f"repeat_7d {item.count_7d}",
            f"top_score {item.top_score}",
        ],
        "blockers": blockers,
        "next_step": next_step,
    }
