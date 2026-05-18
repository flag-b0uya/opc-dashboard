import tempfile
import unittest
from pathlib import Path

from demand_engine.cli import run_daily
from demand_engine.models import RawItemInput
from streamlit_app import find_latest_report, load_dashboard_data


class StreamlitAppTests(unittest.TestCase):
    def test_dashboard_loaders_read_generated_report_and_database(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw_items = [
                RawItemInput(
                    source="reddit",
                    source_url="https://reddit.com/r/SaaS/comments/1",
                    title="Manual client reports",
                    body="Manual client reports are slow and frustrating for our small team.",
                )
            ]
            run_daily(
                root_dir=root,
                config_path=root / "config" / "sources.json",
                db_path=root / "data" / "demand_engine.db",
                offline_items=raw_items,
                report_date="2026-05-18",
                no_llm=True,
            )

            report_path = find_latest_report(root)
            dashboard = load_dashboard_data(root)
            metrics = dashboard["metrics"]
            tracks = dashboard["tracks"]

            self.assertEqual(report_path, root / "reports" / "2026-05-18.md")
            self.assertEqual(metrics["raw_items"], 1)
            self.assertEqual(metrics["candidates"], 1)
            self.assertGreaterEqual(metrics["scored_ideas"], 1)
            self.assertEqual(len(tracks), 1)
            self.assertIn("Manual client reports", tracks[0]["mvp_concept"])
            self.assertIn("source_url", tracks[0])

    def test_dashboard_prefers_published_latest_json_without_database(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reports_dir = root / "reports"
            reports_dir.mkdir()
            (reports_dir / "latest.json").write_text(
                """{
                  "date": "2026-05-18",
                  "analysis_mode": "llm",
                  "summary": {
                    "raw_count": 10,
                    "candidate_count": 4,
                    "scored_count": 2,
                    "build_now_count": 1,
                    "monitor_count": 1,
                    "failed_scores": 0
                  },
                  "tracks": [
                    {
                      "mvp_concept": "Approval tracker",
                      "total_score": 83,
                      "verdict": "Build Now",
                      "target_audience": "small agencies",
                      "pain_summary": "Approvals are slow",
                      "why": "Clustered evidence",
                      "validation_step": "Interview five agencies",
                      "source_urls": ["https://example.com"]
                    }
                  ]
                }""",
                encoding="utf-8",
            )

            dashboard = load_dashboard_data(root)

            self.assertEqual(dashboard["source"], "published")
            self.assertEqual(dashboard["metrics"]["raw_items"], 10)
            self.assertEqual(dashboard["metrics"]["build_now"], 1)
            self.assertEqual(dashboard["tracks"][0]["mvp_concept"], "Approval tracker")


if __name__ == "__main__":
    unittest.main()
