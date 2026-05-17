from __future__ import annotations

import json

from .models import CandidateInput, ScoredIdea


class ScoreParseError(ValueError):
    pass


def _score_range(name: str, value: object, low: int, high: int) -> int:
    if not isinstance(value, int):
        raise ScoreParseError(f"{name} must be an integer")
    if value < low or value > high:
        raise ScoreParseError(f"{name} must be between {low} and {high}")
    return value


def verdict_for(total_score: int, opc_score: int) -> str:
    if total_score >= 80 and opc_score >= 22:
        return "Build Now"
    if total_score >= 60:
        return "Monitor"
    return "Discard"


def parse_score_response(candidate_id: str, response_text: str) -> ScoredIdea:
    try:
        payload = json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise ScoreParseError(f"invalid JSON: {exc}") from exc

    scores = payload.get("scores")
    if not isinstance(scores, dict):
        raise ScoreParseError("scores object is required")

    errc = _score_range("errc", scores.get("errc"), 0, 25)
    jtbd = _score_range("jtbd", scores.get("jtbd"), 0, 25)
    opc = _score_range("opc", scores.get("opc"), 0, 30)
    rice = _score_range("rice", scores.get("rice"), 0, 20)
    total = errc + jtbd + opc + rice

    required_text = [
        "mvp_concept",
        "target_audience",
        "pain_summary",
        "why",
        "validation_step",
    ]
    missing = [key for key in required_text if not payload.get(key)]
    if missing:
        raise ScoreParseError(f"missing fields: {', '.join(missing)}")

    return ScoredIdea(
        candidate_id=candidate_id,
        mvp_concept=str(payload["mvp_concept"]),
        target_audience=str(payload["target_audience"]),
        pain_summary=str(payload["pain_summary"]),
        errc_score=errc,
        jtbd_score=jtbd,
        opc_score=opc,
        rice_score=rice,
        total_score=total,
        verdict=verdict_for(total, opc),
        why=str(payload["why"]),
        validation_step=str(payload["validation_step"]),
    )


def heuristic_score(candidate: CandidateInput) -> ScoredIdea:
    text = candidate.normalized_text.lower()
    errc = 12
    jtbd = 12
    opc = 14
    rice = 8

    if "manual" in text or "slow" in text:
        errc += 5
        jtbd += 4
    if "too expensive" in text or "subscription" in text or "pay for" in text:
        opc += 6
        rice += 3
    if "alternative to" in text or "looking for a tool" in text:
        errc += 4
        rice += 4
    if "client" in text or "business" in text or "team" in text:
        opc += 5

    errc = min(errc, 25)
    jtbd = min(jtbd, 25)
    opc = min(opc, 30)
    rice = min(rice, 20)
    total = errc + jtbd + opc + rice

    title = candidate.title or "Demand signal"
    return ScoredIdea(
        candidate_id=candidate.id,
        mvp_concept=f"Micro-tool for: {title[:80]}",
        target_audience="users showing repeated workflow pain",
        pain_summary=candidate.normalized_text[:180],
        errc_score=errc,
        jtbd_score=jtbd,
        opc_score=opc,
        rice_score=rice,
        total_score=total,
        verdict=verdict_for(total, opc),
        why="Heuristic fallback score based on pain, alternative, budget, and workflow signals.",
        validation_step="Find five similar users and ask how they solve this today.",
    )

