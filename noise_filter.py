"""Local heuristic filter for raw pain-signal text."""

from __future__ import annotations

from typing import Dict, Iterable, List

from query_bank import (
    competitor_terms,
    noise_terms,
    pain_terms_en,
    pain_terms_zh,
    payment_terms,
    workflow_terms,
)


def _hits(text: str, terms: Iterable[str]) -> List[str]:
    lowered = text.lower()
    return [term for term in terms if term.lower() in lowered]


def analyze_text(text: str) -> Dict:
    value = (text or "").strip()
    pain_hits = _hits(value, [*pain_terms_en, *pain_terms_zh])
    workflow_hits = _hits(value, workflow_terms)
    payment_hits = _hits(value, payment_terms)
    competitor_hits = _hits(value, competitor_terms)
    noise_hits = _hits(value, noise_terms)

    score = 0
    score += min(len(pain_hits), 4) * 12
    score += min(len(workflow_hits), 4) * 8
    score += min(len(payment_hits), 3) * 10
    score += min(len(competitor_hits), 3) * 8
    score -= min(len(noise_hits), 4) * 18
    specific_short_signal = (
        len(value) < 30
        and bool(pain_hits)
        and bool(workflow_hits)
        and (bool(payment_hits) or bool(competitor_hits))
    )
    if len(value) < 30 and not specific_short_signal:
        score -= 12
    score = max(0, min(score, 100))

    if score >= 40 and pain_hits and not (noise_hits and score < 60):
        decision = "keep"
    elif score >= 18 and (pain_hits or workflow_hits or competitor_hits):
        decision = "watch"
    else:
        decision = "discard"

    reasons: List[str] = []
    if pain_hits:
        reasons.append("pain signal")
    if workflow_hits:
        reasons.append("workflow signal")
    if payment_hits:
        reasons.append("payment signal")
    if competitor_hits:
        reasons.append("competitor signal")
    if noise_hits:
        reasons.append("noise signal")
    if len(value) < 30:
        reasons.append("too short")

    return {
        "decision": decision,
        "candidate_score": score,
        "filter_reason": ", ".join(reasons) or "no matching signal",
        "pain_hits": pain_hits,
        "workflow_hits": workflow_hits,
        "payment_hits": payment_hits,
        "competitor_hits": competitor_hits,
        "noise_hits": noise_hits,
    }
