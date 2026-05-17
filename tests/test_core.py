import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from demand_engine.filters import filter_candidates
from demand_engine.models import RawItemInput
from demand_engine.reports import render_daily_report
from demand_engine.scoring import parse_score_response
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
            response_text='{"mvp_concept":"Report cleaner","target_audience":"agency operators","pain_summary":"Manual reports are slow","scores":{"errc":20,"jtbd":21,"opc":24,"rice":18,"total":0},"why":"Pain is frequent","validation_step":"Interview five agency operators"}',
        )

        self.assertEqual(scored.total_score, 83)
        self.assertEqual(scored.verdict, "Build Now")

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

    def test_render_daily_report_groups_opportunities(self):
        report = render_daily_report(
            date="2026-05-18",
            raw_count=10,
            candidate_count=2,
            scored_ideas=[
                {
                    "mvp_concept": "Client portal for approvals",
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
        self.assertIn("## Top Opportunities", report)
        self.assertIn("Client portal for approvals", report)
        self.assertIn("## Monitor List", report)
        self.assertIn("Spreadsheet cleanup helper", report)
        self.assertIn("Score failures: 1", report)


if __name__ == "__main__":
    unittest.main()
