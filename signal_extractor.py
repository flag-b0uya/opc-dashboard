"""Heuristic pain-signal extraction from raw source items."""

from __future__ import annotations

import hashlib
import re
from typing import Dict, Iterable, List

from query_bank import competitor_terms, payment_terms, workflow_terms


KNOWN_COMPETITORS = [
    "Expensify",
    "Ramp",
    "Brex",
    "Notion",
    "Airtable",
    "Excel",
    "Google Sheets",
    "Shopify",
    "Slack",
    "Linear",
    "Jira",
]

USER_SEGMENTS = [
    "finance team",
    "support team",
    "sales team",
    "ops team",
    "developers",
    "founders",
    "agency",
    "freelancers",
    "small business",
    "财务",
    "客服",
    "销售",
    "运营",
    "开发者",
]

COMPLAINT_PATTERNS = [
    "too expensive",
    "missing",
    "manual",
    "takes too long",
    "slow",
    "doesn't support",
    "hard to",
    "不好用",
    "太贵",
    "缺少",
    "手动",
    "麻烦",
]

FREQUENCY_PATTERNS = ["daily", "every day", "weekly", "every week", "monthly", "每天", "每周", "每月"]


def _text(item: Dict) -> str:
    return " ".join(
        str(part)
        for part in [item.get("title", ""), item.get("text", ""), item.get("body", ""), item.get("description", "")]
        if part
    ).strip()


def _make_id(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]


def _hits(text: str, terms: Iterable[str]) -> List[str]:
    lowered = text.lower()
    return [term for term in terms if term.lower() in lowered]


def _first_sentence(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if len(cleaned) <= 180:
        return cleaned
    sentence = re.split(r"(?<=[.!?。！？])\s+", cleaned)[0]
    if 40 <= len(sentence) <= 220:
        return sentence
    return cleaned[:177].rstrip() + "..."


def _user_segment(text: str) -> str:
    lowered = text.lower()
    for segment in USER_SEGMENTS:
        if segment.lower() in lowered:
            return segment
    if "reddit r/" in lowered:
        return "community users"
    return ""


def _workflow(text: str) -> str:
    hits = _hits(text, workflow_terms)
    if hits:
        return " / ".join(hits[:3])
    return ""


def _competitors(text: str) -> List[str]:
    found: List[str] = []
    lowered = text.lower()
    for name in KNOWN_COMPETITORS:
        if name.lower() in lowered and name not in found:
            found.append(name)
    for term in competitor_terms:
        if term.lower() in lowered and term not in found:
            found.append(term)
    return found


def _distribution(source: str, text: str) -> List[str]:
    lowered = f"{source} {text}".lower()
    hints = []
    for name in ["reddit", "hacker news", "github", "youtube", "xiaohongshu", "manual"]:
        if name in lowered:
            hints.append(name)
    return hints


def extract_pain_signal(item: Dict) -> Dict:
    text = _text(item)
    source_item_id = str(item.get("source_item_id") or item.get("id") or item.get("container_id") or "")
    source = str(item.get("source") or item.get("platform") or "")
    workflow = _workflow(text)
    competitor_names = _competitors(text)
    complaint_type = _hits(text, COMPLAINT_PATTERNS)
    payment_signal = bool(_hits(text, payment_terms))
    distribution_hint = _distribution(source, text)
    frequency_hits = _hits(text, FREQUENCY_PATTERNS)

    confidence_parts = [
        bool(complaint_type),
        bool(workflow),
        bool(_user_segment(text)),
        payment_signal,
        bool(competitor_names),
        bool(distribution_hint),
    ]
    confidence = round(sum(1 for part in confidence_parts if part) / len(confidence_parts), 2)

    return {
        "signal_id": _make_id(source_item_id, source, text),
        "source_item_id": source_item_id,
        "source": source,
        "user_segment": _user_segment(text),
        "pain_statement": _first_sentence(text),
        "job_to_be_done": f"Resolve {workflow} without repeated manual work" if workflow else "",
        "workflow": workflow,
        "current_solution": " / ".join(name for name in competitor_names if name in {"Excel", "Google Sheets", "Notion", "Airtable"}) or "",
        "competitor_names": competitor_names,
        "complaint_type": complaint_type,
        "frequency": frequency_hits[0] if frequency_hits else "",
        "payment_signal": payment_signal,
        "distribution_hint": distribution_hint,
        "ai_leverage": "summarize, classify, and automate repeated workflow steps" if workflow else "",
        "mvp_shape": f"lightweight assistant for {workflow}" if workflow else "",
        "confidence": confidence,
    }
