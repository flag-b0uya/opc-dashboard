"""Generate validation assets for opportunity clusters."""

from __future__ import annotations

from typing import Dict, List


def _sample_pain(cluster: Dict) -> str:
    for idea in cluster.get("sample_ideas", []) or []:
        pain = str(idea.get("pain_summary", "")).strip()
        if pain:
            return pain
    return str(cluster.get("evidence_summary") or cluster.get("title") or "The workflow is still painful.").strip()


def _audience(cluster: Dict) -> str:
    for idea in cluster.get("sample_ideas", []) or []:
        source = str(idea.get("source", "")).strip()
        if source:
            return source.replace("Reddit ", "").replace("Manual ", "")
    category = str(cluster.get("category", "目标用户"))
    if category == "运营/内部流程":
        return "ops and finance teams"
    if category == "销售/线索转化":
        return "sales operators"
    if category == "客服/成功/留存":
        return "support teams"
    return "people with this workflow"


def generate_validation_pack(cluster: Dict) -> Dict:
    title = str(cluster.get("title") or "待验证机会")
    pain = _sample_pain(cluster)
    audience = _audience(cluster)
    pitch = f"Help {audience} turn '{pain[:96]}' into a faster, measurable workflow."
    headline = f"Stop losing hours to {title}"
    subtitle = "Validate the workflow first: one post, ten DMs, five interviews, then decide whether to build."

    return {
        "one_sentence_pitch": pitch,
        "landing_page_headline": headline,
        "landing_page_subtitle": subtitle,
        "problem_section": f"People in {audience} are describing this pain: {pain}",
        "solution_section": "A lightweight workflow assistant that removes the repeated manual step before a full product is built.",
        "reddit_post": (
            f"Anyone here dealing with this? {pain}\n\n"
            "I am testing whether this is painful enough to solve. "
            "What are you using today, and where does it break?"
        ),
        "x_post": (
            f"Researching a workflow pain: {pain} "
            "If this is familiar, I want to hear what you use today and what would make you switch."
        ),
        "cold_dm": (
            f"Hi, I saw people in {audience} mention this problem: {pain} "
            "Can I ask 2 questions about how you handle it today? No pitch, just research."
        ),
        "interview_questions": [
            "When did this workflow last happen?",
            "What tool or workaround do you use today?",
            "How much time or money does it cost each week?",
            "What have you tried that did not work?",
            "What would make this urgent enough to pay for?",
            "Who else on your team feels the pain?",
        ],
        "success_metrics": [
            "At least 3 meaningful replies from 10 targeted DMs.",
            "At least 2 users describe the same current workaround.",
            "At least 1 user agrees to a follow-up call or waitlist.",
        ],
        "kill_criteria": [
            "Fewer than 2 replies after 20 targeted messages.",
            "No one can describe a recent concrete occurrence.",
            "Users say the current workaround is good enough or free alternatives solve it.",
        ],
    }
