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


def verdict_for(total_score: int, opc_score: int, source_excerpt: str = "", anti_signals: list[str] | None = None) -> str:
    has_evidence = bool(source_excerpt.strip()) and bool(anti_signals)
    if total_score >= 80 and opc_score >= 22 and has_evidence:
        return "Build Now"
    if total_score >= 60:
        return "Monitor"
    return "Discard"


def _required_text_field(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ScoreParseError(f"{key} is required")
    return value.strip()


def _anti_signals_field(payload: dict[str, object]) -> list[str]:
    if "anti_signals" not in payload:
        raise ScoreParseError("anti_signals is required")
    value = payload["anti_signals"]
    if not isinstance(value, list) or not all(isinstance(signal, str) for signal in value):
        raise ScoreParseError("anti_signals must be a list of strings")
    return [signal.strip() for signal in value if signal.strip()]


def parse_score_response(candidate_id: str, response_text: str) -> ScoredIdea:
    try:
        payload = json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise ScoreParseError(f"invalid JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise ScoreParseError("top-level JSON object is required")

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
        "source_excerpt",
        "opportunity_thesis",
        "existing_workaround",
        "confidence_note",
        "why",
        "validation_step",
    ]
    text_fields = {key: _required_text_field(payload, key) for key in required_text}
    anti_signals = _anti_signals_field(payload)

    return ScoredIdea(
        candidate_id=candidate_id,
        mvp_concept=text_fields["mvp_concept"],
        target_audience=text_fields["target_audience"],
        pain_summary=text_fields["pain_summary"],
        errc_score=errc,
        jtbd_score=jtbd,
        opc_score=opc,
        rice_score=rice,
        total_score=total,
        verdict=verdict_for(total, opc, text_fields["source_excerpt"], anti_signals),
        why=text_fields["why"],
        validation_step=text_fields["validation_step"],
        source_excerpt=text_fields["source_excerpt"],
        opportunity_thesis=text_fields["opportunity_thesis"],
        existing_workaround=text_fields["existing_workaround"],
        anti_signals=anti_signals,
        confidence_note=text_fields["confidence_note"],
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
    source_excerpt = candidate.normalized_text[:240]
    matched_rules = ", ".join(candidate.matched_rules) if candidate.matched_rules else "general pain signals"
    return ScoredIdea(
        candidate_id=candidate.id,
        mvp_concept=f"Micro-tool for: {title[:80]}",
        target_audience="one-person company developers validating a narrow workflow pain",
        pain_summary=candidate.normalized_text[:180],
        errc_score=errc,
        jtbd_score=jtbd,
        opc_score=opc,
        rice_score=rice,
        total_score=total,
        verdict=verdict_for(
            total,
            opc,
            source_excerpt,
            ["Heuristic signal only; needs direct user validation before building."],
        ),
        why="Heuristic fallback score based on pain, alternative, budget, and workflow signals.",
        validation_step="Find five similar users and ask how they solve this today.",
        source_excerpt=source_excerpt,
        opportunity_thesis=f"{title[:80]} points to a narrow workflow where a small tool may beat broad software.",
        existing_workaround=f"Current workaround inferred from matched rules: {matched_rules}.",
        anti_signals=["Heuristic signal only; needs direct user validation before building."],
        confidence_note="Generated from deterministic local heuristics; confidence should increase only after user interviews.",
    )
