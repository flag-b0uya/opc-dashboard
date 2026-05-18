import tempfile
import unittest
from pathlib import Path

from demand_engine.cli import load_config, run_daily
from demand_engine.models import RawItemInput


class CliTests(unittest.TestCase):
    def test_load_config_returns_defaults_when_file_missing(self):
        config = load_config(Path("missing-config.json"))

        self.assertIn("hn", config)
        self.assertEqual(config["hn"]["lookback_hours"], 24)
        self.assertIn("reddit", config)
        self.assertIn("app_store", config)

    def test_run_daily_writes_report_from_offline_items(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw_items = [
                RawItemInput(
                    source="hn",
                    source_url="https://news.ycombinator.com/item?id=42",
                    title="Alternative to manual reports",
                    body="I wish there was an alternative to our slow manual client reporting workflow. We would pay for this.",
                    author="operator",
                    published_at="2026-05-18T00:00:00Z",
                    metadata={"points": 20},
                )
            ]

            result = run_daily(
                root_dir=root,
                config_path=root / "config" / "sources.json",
                db_path=root / "data" / "demand_engine.db",
                offline_items=raw_items,
                report_date="2026-05-18",
            )

            report_path = root / "reports" / "2026-05-18.md"
            self.assertTrue(report_path.exists())
            report = report_path.read_text(encoding="utf-8")
            self.assertIn("Blue Ocean Demand Report", report)
            self.assertIn("Top Opportunity Tracks", report)
            self.assertIn("Evidence", report)
            self.assertIn("Why This Might Be Wrong", report)
            self.assertIn("Next Validation Step", report)
            self.assertEqual(result["raw_count"], 1)
            self.assertEqual(result["candidate_count"], 1)
            self.assertGreaterEqual(result["scored_count"], 1)

    def test_run_daily_rerun_keeps_report_useful_without_duplicate_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw_items = [
                RawItemInput(
                    source="hn",
                    source_url="https://news.ycombinator.com/item?id=99",
                    title="Slow manual reports",
                    body="Our slow manual reports are frustrating, and we would pay for an alternative to this workflow.",
                    author="operator",
                    published_at="2026-05-18T00:00:00Z",
                    metadata={"points": 20},
                )
            ]
            kwargs = {
                "root_dir": root,
                "config_path": root / "config" / "sources.json",
                "db_path": root / "data" / "demand_engine.db",
                "offline_items": raw_items,
                "report_date": "2026-05-18",
            }

            first = run_daily(**kwargs)
            second = run_daily(**kwargs)

            self.assertEqual(first["raw_inserted"], 1)
            self.assertEqual(second["raw_inserted"], 0)
            self.assertEqual(second["candidate_count"], 1)
            report = (root / "reports" / "2026-05-18.md").read_text(encoding="utf-8")
            self.assertIn("Slow manual reports", report)


if __name__ == "__main__":
    unittest.main()
