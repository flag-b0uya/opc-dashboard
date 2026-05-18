from __future__ import annotations

from contextlib import closing
from pathlib import Path
import sqlite3

from .models import CandidateInput, RawItemInput, ScoredIdea, stable_json, utc_now_iso


class DemandStore:
    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)

    def connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def initialize(self) -> None:
        with closing(self.connect()) as conn:
            conn.executescript(
                """
                create table if not exists raw_items (
                  id text primary key,
                  source text not null,
                  source_url text not null,
                  title text not null,
                  body text not null,
                  author text,
                  published_at text,
                  fetched_at text not null,
                  metadata_json text not null
                );

                create table if not exists candidates (
                  id text primary key,
                  raw_item_id text not null,
                  normalized_text text not null,
                  matched_rules text not null,
                  language text not null,
                  body_hash text not null,
                  created_at text not null,
                  foreign key(raw_item_id) references raw_items(id)
                );

                create table if not exists scored_ideas (
                  id text primary key,
                  candidate_id text not null,
                  mvp_concept text not null,
                  target_audience text not null,
                  pain_summary text not null,
                  errc_score integer not null,
                  jtbd_score integer not null,
                  opc_score integer not null,
                  rice_score integer not null,
                  total_score integer not null,
                  verdict text not null,
                  why text not null,
                  validation_step text not null,
                  evidence_json text not null default '{}',
                  scored_at text not null,
                  foreign key(candidate_id) references candidates(id)
                );
                """
            )
            columns = {
                str(row["name"])
                for row in conn.execute("pragma table_info(scored_ideas)").fetchall()
            }
            if "evidence_json" not in columns:
                conn.execute("alter table scored_ideas add column evidence_json text not null default '{}'")
            conn.commit()

    def upsert_raw_items(self, items: list[RawItemInput]) -> int:
        inserted = 0
        with closing(self.connect()) as conn:
            for item in items:
                cursor = conn.execute(
                    """
                    insert or ignore into raw_items
                    (id, source, source_url, title, body, author, published_at, fetched_at, metadata_json)
                    values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item.id,
                        item.source,
                        item.source_url,
                        item.title,
                        item.body,
                        item.author,
                        item.published_at,
                        utc_now_iso(),
                        stable_json(item.metadata),
                    ),
                )
                inserted += cursor.rowcount
            conn.commit()
        return inserted

    def existing_candidate_body_hashes(self) -> set[str]:
        with closing(self.connect()) as conn:
            rows = conn.execute("select body_hash from candidates").fetchall()
        return {str(row["body_hash"]) for row in rows}

    def insert_candidates(self, candidates: list[CandidateInput]) -> int:
        inserted = 0
        with closing(self.connect()) as conn:
            for candidate in candidates:
                cursor = conn.execute(
                    """
                    insert or ignore into candidates
                    (id, raw_item_id, normalized_text, matched_rules, language, body_hash, created_at)
                    values (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        candidate.id,
                        candidate.raw_item_id,
                        candidate.normalized_text,
                        stable_json({"rules": candidate.matched_rules}),
                        candidate.language,
                        candidate.body_hash,
                        utc_now_iso(),
                    ),
                )
                inserted += cursor.rowcount
            conn.commit()
        return inserted

    def insert_scored_ideas(self, ideas: list[ScoredIdea]) -> int:
        inserted = 0
        with closing(self.connect()) as conn:
            for idea in ideas:
                cursor = conn.execute(
                    """
                    insert or ignore into scored_ideas
                    (id, candidate_id, mvp_concept, target_audience, pain_summary,
                     errc_score, jtbd_score, opc_score, rice_score, total_score,
                     verdict, why, validation_step, evidence_json, scored_at)
                    values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        idea.candidate_id,
                        idea.candidate_id,
                        idea.mvp_concept,
                        idea.target_audience,
                        idea.pain_summary,
                        idea.errc_score,
                        idea.jtbd_score,
                        idea.opc_score,
                        idea.rice_score,
                        idea.total_score,
                        idea.verdict,
                        idea.why,
                        idea.validation_step,
                        stable_json(idea.evidence_payload()),
                        idea.scored_at,
                    ),
                )
                inserted += cursor.rowcount
            conn.commit()
        return inserted
