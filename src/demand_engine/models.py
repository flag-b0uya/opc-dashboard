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
    scored_at: str = field(default_factory=utc_now_iso)


def normalize_text(value: str) -> str:
    return " ".join(value.strip().split())

