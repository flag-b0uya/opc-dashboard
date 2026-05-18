from __future__ import annotations

from typing import Any


def _idea_value(idea: Any, key: str, default: str = "") -> Any:
    if isinstance(idea, dict):
        return idea.get(key, default)
    return getattr(idea, key, default)


def _idea_list(idea: Any, key: str) -> list[str]:
    value = _idea_value(idea, key, [])
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _score_breakdown(idea: Any) -> str:
    parts = []
    for label, key in [
        ("ERRC", "errc_score"),
        ("JTBD", "jtbd_score"),
        ("OPC", "opc_score"),
        ("RICE", "rice_score"),
    ]:
        value = _idea_value(idea, key, None)
        if value is not None:
            parts.append(f"{label} {value}")
    total = _idea_value(idea, "total_score")
    return f"{total}" if not parts else f"{total} ({', '.join(parts)})"


def _append_evidence_track(lines: list[str], index: int, idea: Any) -> None:
    anti_signals = _idea_list(idea, "anti_signals")
    if not anti_signals:
        anti_signals = ["No anti-signal captured yet."]
    source_urls = _idea_list(idea, "source_urls")
    if not source_urls:
        source_url = _idea_value(idea, "source_url", "")
        source_urls = [source_url] if source_url else []

    lines.extend(
        [
            f"### {index}. {_idea_value(idea, 'mvp_concept')}",
            "",
            f"- Score: {_score_breakdown(idea)}",
            f"- Verdict: {_idea_value(idea, 'verdict')}",
            f"- Source: {_idea_value(idea, 'source_url', 'n/a')}",
            "",
            "#### Evidence",
            "",
            f"- Excerpt: {_idea_value(idea, 'source_excerpt', _idea_value(idea, 'pain_summary'))}",
            f"- Existing workaround: {_idea_value(idea, 'existing_workaround', 'Unknown')}",
        ]
    )
    if source_urls:
        lines.append(f"- Sources: {', '.join(source_urls)}")
    lines.extend(
        [
            "",
            "#### Why This Might Be Real",
            "",
            f"- Thesis: {_idea_value(idea, 'opportunity_thesis', _idea_value(idea, 'why'))}",
            f"- Target audience: {_idea_value(idea, 'target_audience')}",
            f"- Pain: {_idea_value(idea, 'pain_summary')}",
            "",
            "#### Why This Might Be Wrong",
            "",
        ]
    )
    lines.extend(f"- {signal}" for signal in anti_signals)
    lines.extend(
        [
            f"- Confidence: {_idea_value(idea, 'confidence_note', 'Needs more validation.')}",
            "",
            "#### Next Validation Step",
            "",
            f"- {_idea_value(idea, 'validation_step')}",
            "",
        ]
    )


def render_daily_report(
    date: str,
    raw_count: int,
    candidate_count: int,
    scored_ideas: list[Any],
    failed_scores: int = 0,
) -> str:
    ideas = sorted(scored_ideas, key=lambda idea: int(_idea_value(idea, "total_score", 0)), reverse=True)
    build_now = [idea for idea in ideas if _idea_value(idea, "verdict") == "Build Now"]
    monitor = [idea for idea in ideas if _idea_value(idea, "verdict") == "Monitor"]
    top_tracks = build_now if build_now else monitor[:3]

    lines = [
        f"# Blue Ocean Demand Report - {date}",
        "",
        "## Executive Summary",
        "",
        f"- Raw items collected: {raw_count}",
        f"- Candidates after filtering: {candidate_count}",
        f"- Ideas scored: {len(scored_ideas)}",
        f"- Build Now: {len(build_now)}",
        f"- Monitor: {len(monitor)}",
        f"- Score failures: {failed_scores}",
        "",
        "## Top Opportunity Tracks",
        "",
    ]

    if not top_tracks:
        lines.extend(["No opportunity tracks today.", ""])
    for index, idea in enumerate(top_tracks, start=1):
        _append_evidence_track(lines, index, idea)

    lines.extend(["## Monitor List", "", "| Score | Concept | Source | Validation |", "| --- | --- | --- | --- |"])
    for idea in monitor:
        lines.append(
            f"| {_idea_value(idea, 'total_score')} | {_idea_value(idea, 'mvp_concept')} | "
            f"{_idea_value(idea, 'source_url', 'n/a')} | {_idea_value(idea, 'validation_step')} |"
        )

    lines.extend(
        [
            "",
            "## Discarded Patterns",
            "",
            "- Low willingness to pay:",
            "- Too broad:",
            "- Too hard for one person:",
            "",
            "## Rule Notes",
            "",
            "- New useful phrases:",
            "- False positives:",
            "- Source quality notes:",
            "",
            "## Human Review",
            "",
            "- Best signal today:",
            "- Worst false positive:",
            "- New phrase to add:",
            "- Phrase to downrank:",
            "- Source to increase:",
            "- Source to decrease:",
            "- One MVP worth validating tomorrow:",
            "",
        ]
    )

    return "\n".join(lines)
