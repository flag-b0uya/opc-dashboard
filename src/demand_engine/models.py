from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Literal


SourceName = Literal["hn", "reddit", "app_store"]
Verdict = Literal["Build Now", "Monitor", "Discard"]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_hash(*parts: object) -> str:
    payload = "\x1f".join("" if part is None else str(part) for part in parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def stable_json(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True)
class RawItemInput:
    source: SourceName
    source_url: str
    title: str
    body: str
    author: str | None = None
    published_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def id(self) -> str:
        return stable_hash(self.source, self.source_url, self.title, self.body)

    @property
    def body_hash(self) -> str:
        return stable_hash(normalize_text(self.body))


@dataclass(frozen=True)
class CandidateInput:
    raw_item_id: str
    normalized_text: str
    matched_rules: list[str]
    language: Literal["en", "zh", "unknown"]
    source_url: str = ""
    title: str = ""
    body_hash: str = ""

    @property
    def id(self) -> str:
        return stable_hash(self.raw_item_id, self.normalized_text)


@dataclass(frozen=True)
class ScoredIdea:
    candidate_id: str
    mvp_concept: str
    target_audience: str
    pain_summary: str
    errc_score: int
    jtbd_score: int
    opc_score: int
    rice_score: int
    total_score: int
    verdict: Verdict
    why: str
    validation_step: str
    source_excerpt: str = ""
    opportunity_thesis: str = ""
    existing_workaround: str = ""
    anti_signals: list[str] = field(default_factory=list)
    confidence_note: str = ""
    source_urls: list[str] = field(default_factory=list)
    scored_at: str = field(default_factory=utc_now_iso)

    def evidence_payload(self) -> dict[str, Any]:
        return {
            "source_excerpt": self.source_excerpt,
            "opportunity_thesis": self.opportunity_thesis,
            "existing_workaround": self.existing_workaround,
            "anti_signals": list(self.anti_signals),
            "confidence_note": self.confidence_note,
            "source_urls": list(self.source_urls),
        }

    @staticmethod
    def from_evidence_payload(payload: dict[str, Any] | str | None) -> dict[str, Any]:
        if isinstance(payload, str):
            try:
                raw = json.loads(payload) if payload else {}
            except json.JSONDecodeError:
                raw = {}
        elif isinstance(payload, dict):
            raw = payload
        else:
            raw = {}

        anti_signals = raw.get("anti_signals", [])
        if not isinstance(anti_signals, list):
            anti_signals = []
        source_urls = raw.get("source_urls", [])
        if not isinstance(source_urls, list):
            source_urls = []

        return {
            "source_excerpt": str(raw.get("source_excerpt", "")),
            "opportunity_thesis": str(raw.get("opportunity_thesis", "")),
            "existing_workaround": str(raw.get("existing_workaround", "")),
            "anti_signals": [str(signal) for signal in anti_signals if str(signal).strip()],
            "confidence_note": str(raw.get("confidence_note", "")),
            "source_urls": [str(url) for url in source_urls if str(url).strip()],
        }


def normalize_text(value: str) -> str:
    return " ".join(value.strip().split())
