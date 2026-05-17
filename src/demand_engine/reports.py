from __future__ import annotations

from typing import Any


def _idea_value(idea: Any, key: str, default: str = "") -> Any:
    if isinstance(idea, dict):
        return idea.get(key, default)
    return getattr(idea, key, default)


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
        "## Top Opportunities",
        "",
    ]

    if not build_now:
        lines.extend(["No Build Now opportunities today.", ""])
    for index, idea in enumerate(build_now, start=1):
        lines.extend(
            [
                f"### {index}. {_idea_value(idea, 'mvp_concept')}",
                "",
                f"- Score: {_idea_value(idea, 'total_score')}",
                f"- Verdict: {_idea_value(idea, 'verdict')}",
                f"- Source: {_idea_value(idea, 'source_url', 'n/a')}",
                f"- Target audience: {_idea_value(idea, 'target_audience')}",
                f"- Pain: {_idea_value(idea, 'pain_summary')}",
                f"- Why now: {_idea_value(idea, 'why')}",
                f"- Validation step: {_idea_value(idea, 'validation_step')}",
                "",
            ]
        )

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
