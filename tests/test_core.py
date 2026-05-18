import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from demand_engine.filters import filter_candidates
from demand_engine.models import RawItemInput
from demand_engine.reports import render_daily_report
from demand_engine.scoring import ScoreParseError, heuristic_score, parse_score_response
from demand_engine.storage import DemandStore


class CoreTests(unittest.TestCase):
    def test_filter_candidates_keeps_pain_signals(self):
        raw = RawItemInput(
            source="hn",
            source_url="https://news.ycombinator.com/item?id=1",
            title="Looking for a tool",
            body="I wish there was an alternative to this slow manual reporting workflow.",
            author="alice",
            published_at="2026-05-18T00:00:00Z",
            metadata={"points": 12},
        )

        candidates = filter_candidates([raw], existing_body_hashes=set())

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].language, "en")
        self.assertIn("alternative to", candidates[0].matched_rules)
        self.assertIn("manual", candidates[0].matched_rules)

    def test_parse_score_response_recomputes_total_and_verdict(self):
        scored = parse_score_response(
            candidate_id="candidate-1",
            response_text='{"mvp_concept":"Report cleaner","target_audience":"agency operators","pain_summary":"Manual reports are slow","source_excerpt":"Manual reports are slow","opportunity_thesis":"Agencies need approval evidence in one place","existing_workaround":"Spreadsheets and email threads","anti_signals":["Could be too agency-specific"],"confidence_note":"High pain, narrow workflow","scores":{"errc":20,"jtbd":21,"opc":24,"rice":18,"total":0},"why":"Pain is frequent","validation_step":"Interview five agency operators"}',
        )

        self.assertEqual(scored.total_score, 83)
        self.assertEqual(scored.verdict, "Build Now")
        self.assertEqual(scored.source_excerpt, "Manual reports are slow")
        self.assertEqual(scored.opportunity_thesis, "Agencies need approval evidence in one place")
        self.assertEqual(scored.existing_workaround, "Spreadsheets and email threads")
        self.assertIn("Could be too agency-specific", scored.anti_signals)
        self.assertEqual(scored.confidence_note, "High pain, narrow workflow")

    def test_parse_score_response_rejects_malformed_anti_signals(self):
        with self.assertRaisesRegex(ScoreParseError, "anti_signals"):
            parse_score_response(
                candidate_id="candidate-1",
                response_text='{"mvp_concept":"Report cleaner","target_audience":"agency operators","pain_summary":"Manual reports are slow","source_excerpt":"Manual reports are slow","opportunity_thesis":"Agencies need approval evidence in one place","existing_workaround":"Spreadsheets and email threads","anti_signals":"too broad","confidence_note":"High pain, narrow workflow","scores":{"errc":20,"jtbd":21,"opc":24,"rice":18},"why":"Pain is frequent","validation_step":"Interview five agency operators"}',
            )

    def test_parse_score_response_rejects_non_object_json(self):
        with self.assertRaisesRegex(ScoreParseError, "top-level JSON object"):
            parse_score_response(
                candidate_id="candidate-1",
                response_text='["not", "an", "object"]',
            )

    def test_heuristic_score_outputs_evidence_pack_fields(self):
        raw = RawItemInput(
            source="hn",
            source_url="https://news.ycombinator.com/item?id=7",
            title="Alternative to slow client reports",
            body="I wish there was an alternative to this slow manual client reporting workflow. We would pay for a simple tool.",
            author="builder",
            published_at="2026-05-18T00:00:00Z",
            metadata={},
        )
        candidate = filter_candidates([raw], existing_body_hashes=set())[0]

        scored = heuristic_score(candidate)

        self.assertTrue(scored.source_excerpt)
        self.assertIn("one-person", scored.target_audience)
        self.assertTrue(scored.opportunity_thesis)
        self.assertTrue(scored.existing_workaround)
        self.assertTrue(scored.anti_signals)
        self.assertTrue(scored.confidence_note)

    def test_storage_is_idempotent_for_raw_items(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = DemandStore(Path(tmp) / "engine.db")
            store.initialize()
            raw = RawItemInput(
                source="reddit",
                source_url="https://reddit.com/r/SaaS/comments/1",
                title="Too expensive",
                body="This subscription is too expensive for small client teams.",
                author=None,
                published_at=None,
                metadata={"subreddit": "SaaS"},
            )

            first = store.upsert_raw_items([raw])
            second = store.upsert_raw_items([raw])

            self.assertEqual(first, 1)
            self.assertEqual(second, 0)
            with closing(sqlite3.connect(store.db_path)) as conn:
                count = conn.execute("select count(*) from raw_items").fetchone()[0]
            self.assertEqual(count, 1)

    def test_storage_persists_evidence_pack_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = DemandStore(Path(tmp) / "engine.db")
            store.initialize()
            raw = RawItemInput(
                source="hn",
                source_url="https://news.ycombinator.com/item?id=8",
                title="Alternative to manual onboarding",
                body="I wish there was an alternative to our manual onboarding checklist for client teams.",
                author="founder",
                published_at=None,
                metadata={},
            )
            store.upsert_raw_items([raw])
            candidate = filter_candidates([raw], existing_body_hashes=set())[0]
            store.insert_candidates([candidate])
            idea = heuristic_score(candidate)

            inserted = store.insert_scored_ideas([idea])

            self.assertEqual(inserted, 1)
            with closing(sqlite3.connect(store.db_path)) as conn:
                row = conn.execute(
                    "select evidence_json from scored_ideas where id = ?",
                    (idea.candidate_id,),
                ).fetchone()
            self.assertIsNotNone(row)
            self.assertIn("anti_signals", row[0])

    def test_storage_migrates_legacy_scored_ideas_table(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "engine.db"
            with closing(sqlite3.connect(db_path)) as conn:
                conn.executescript(
                    """
                    create table scored_ideas (
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
                      scored_at text not null
                    );
                    insert into scored_ideas
                    (id, candidate_id, mvp_concept, target_audience, pain_summary,
                     errc_score, jtbd_score, opc_score, rice_score, total_score,
                     verdict, why, validation_step, scored_at)
                    values
                    ('idea-1', 'candidate-1', 'Legacy concept', 'legacy users', 'legacy pain',
                     1, 2, 3, 4, 10, 'Monitor', 'legacy why', 'legacy validation', '2026-05-18T00:00:00Z');
                    """
                )
                conn.commit()

            store = DemandStore(db_path)
            store.initialize()

            with closing(sqlite3.connect(db_path)) as conn:
                columns = [row[1] for row in conn.execute("pragma table_info(scored_ideas)").fetchall()]
                row = conn.execute("select evidence_json from scored_ideas where id = 'idea-1'").fetchone()
            self.assertIn("evidence_json", columns)
            self.assertEqual(row[0], "{}")

    def test_evidence_gate_downgrades_build_now_without_anti_signals(self):
        scored = parse_score_response(
            candidate_id="candidate-1",
            response_text='{"mvp_concept":"Report cleaner","target_audience":"agency operators","pain_summary":"Manual reports are slow","source_excerpt":"Manual reports are slow","opportunity_thesis":"Agencies need approval evidence in one place","existing_workaround":"Spreadsheets and email threads","anti_signals":[],"confidence_note":"High pain, narrow workflow","scores":{"errc":20,"jtbd":21,"opc":24,"rice":18},"why":"Pain is frequent","validation_step":"Interview five agency operators"}',
        )

        self.assertEqual(scored.total_score, 83)
        self.assertEqual(scored.verdict, "Monitor")

    def test_render_daily_report_groups_opportunities(self):
        report = render_daily_report(
            date="2026-05-18",
            raw_count=10,
            candidate_count=2,
            scored_ideas=[
                {
                    "mvp_concept": "Client portal for approvals",
                    "source_excerpt": "I wish approvals did not happen across email.",
                    "opportunity_thesis": "Small agencies need one lightweight approval trail.",
                    "existing_workaround": "Email threads and spreadsheets.",
                    "anti_signals": ["May be a feature inside project management tools."],
                    "confidence_note": "Strong pain and narrow audience.",
                    "total_score": 84,
                    "verdict": "Build Now",
                    "source_url": "https://example.com/1",
                    "target_audience": "small agencies",
                    "pain_summary": "Approvals happen across scattered emails.",
                    "why": "High-frequency workflow pain.",
                    "validation_step": "Ask ten agency owners about approval delays.",
                },
                {
                    "mvp_concept": "Spreadsheet cleanup helper",
                    "source_excerpt": "CSV cleanup is repetitive.",
                    "opportunity_thesis": "Operators need repeatable cleanup recipes.",
                    "existing_workaround": "Manual spreadsheet formulas.",
                    "anti_signals": ["Generic pain with many existing tools."],
                    "confidence_note": "Common pain, weaker narrowness.",
                    "total_score": 66,
                    "verdict": "Monitor",
                    "source_url": "https://example.com/2",
                    "target_audience": "operators",
                    "pain_summary": "CSV cleanup is repetitive.",
                    "why": "Common but generic.",
                    "validation_step": "Collect five messy CSV examples.",
                },
            ],
            failed_scores=1,
        )

        self.assertIn("# Blue Ocean Demand Report - 2026-05-18", report)
        self.assertIn("## Top Opportunity Tracks", report)
        self.assertIn("#### Evidence", report)
        self.assertIn("#### Why This Might Be Real", report)
        self.assertIn("#### Why This Might Be Wrong", report)
        self.assertIn("#### Next Validation Step", report)
        self.assertIn("Client portal for approvals", report)
        self.assertIn("## Monitor List", report)
        self.assertIn("Spreadsheet cleanup helper", report)
        self.assertIn("Score failures: 1", report)

    def test_render_daily_report_shows_strongest_monitor_when_no_build_now(self):
        report = render_daily_report(
            date="2026-05-18",
            raw_count=3,
            candidate_count=1,
            scored_ideas=[
                {
                    "mvp_concept": "Client report cleanup",
                    "source_excerpt": "Manual reports are slow.",
                    "opportunity_thesis": "Solo consultants need a tiny reporting workflow.",
                    "existing_workaround": "Copying data into slides.",
                    "anti_signals": ["May be solved by existing BI exports."],
                    "confidence_note": "Narrow pain but moderate score.",
                    "errc_score": 18,
                    "jtbd_score": 18,
                    "opc_score": 18,
                    "rice_score": 10,
                    "total_score": 64,
                    "verdict": "Monitor",
                    "source_url": "https://example.com/monitor",
                    "target_audience": "one-person company consultants",
                    "pain_summary": "Manual reports are slow.",
                    "why": "Repeated workflow pain.",
                    "validation_step": "Ask five consultants for report examples.",
                }
            ],
        )

        self.assertIn("## Top Opportunity Tracks", report)
        self.assertIn("Client report cleanup", report)
        self.assertIn("- Verdict: Monitor", report)


if __name__ == "__main__":
    unittest.main()
