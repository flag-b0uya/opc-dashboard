import json
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
            latest_json = json.loads((root / "reports" / "latest.json").read_text(encoding="utf-8"))
            self.assertIn("Blue Ocean Demand Report", report)
            self.assertIn("Top Opportunity Tracks", report)
            self.assertIn("Evidence", report)
            self.assertIn("Why This Might Be Wrong", report)
            self.assertIn("Next Validation Step", report)
            self.assertEqual(result["raw_count"], 1)
            self.assertEqual(result["candidate_count"], 1)
            self.assertGreaterEqual(result["scored_count"], 1)
            self.assertEqual(latest_json["date"], "2026-05-18")
            self.assertEqual(latest_json["summary"]["raw_count"], 1)
            self.assertEqual(len(latest_json["tracks"]), 1)

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

    def test_run_daily_uses_injected_llm_client_for_clustered_tracks(self):
        class FakeLLMClient:
            def analyze(self, prompt, schema):
                packet = json.loads(prompt.split("Candidates JSON:\n", 1)[1])
                candidate_ids = [item["candidate_id"] for item in packet]
                return {
                    "tracks": [
                        {
                            "candidate_ids": candidate_ids,
                            "mvp_concept": "Approval tracker for small agencies",
                            "target_audience": "small agency owners",
                            "pain_summary": "Approvals are scattered across email and spreadsheets.",
                            "source_excerpt": "manual client approvals across email and spreadsheets",
                            "opportunity_thesis": "A narrow approval trail beats broad PM tools for small agencies.",
                            "existing_workaround": "Email, spreadsheets, and repeated follow-up.",
                            "anti_signals": ["May be a feature inside project management tools."],
                            "confidence_note": "Multiple similar pain signals in one run.",
                            "scores": {"errc": 22, "jtbd": 21, "opc": 25, "rice": 15},
                            "why": "Repeated workflow pain with a clear manual workaround.",
                            "validation_step": "Ask five agency owners for their latest approval thread.",
                        }
                    ]
                }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw_items = [
                RawItemInput(
                    source="reddit",
                    source_url="https://reddit.com/r/smallbusiness/comments/a",
                    title="Agency approvals are manual",
                    body="Our manual client approval workflow is slow and stuck in spreadsheets.",
                ),
                RawItemInput(
                    source="reddit",
                    source_url="https://reddit.com/r/smallbusiness/comments/b",
                    title="Looking for approval tool",
                    body="Looking for a tool because client approvals are missing from our current workflow.",
                ),
            ]
            fake_client = FakeLLMClient()

            result = run_daily(
                root_dir=root,
                config_path=root / "config" / "sources.json",
                db_path=root / "data" / "demand_engine.db",
                offline_items=raw_items,
                report_date="2026-05-18",
                llm_client=fake_client,
                max_llm_candidates=10,
            )

            report = (root / "reports" / "2026-05-18.md").read_text(encoding="utf-8")
            latest_json = json.loads((root / "reports" / "latest.json").read_text(encoding="utf-8"))
            self.assertEqual(result["analysis_mode"], "llm")
            self.assertEqual(result["scored_count"], 1)
            self.assertEqual(result["failed_scores"], 0)
            self.assertIn("Approval tracker for small agencies", report)
            self.assertNotIn("Micro-tool for: Agency approvals are manual", report)
            self.assertEqual(latest_json["analysis_mode"], "llm")
            self.assertEqual(latest_json["tracks"][0]["mvp_concept"], "Approval tracker for small agencies")

    def test_run_daily_no_llm_keeps_heuristic_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw_items = [
                RawItemInput(
                    source="hn",
                    source_url="https://news.ycombinator.com/item?id=123",
                    title="Manual reports are slow",
                    body="Manual reports are slow and frustrating, and we would pay for a better workflow.",
                )
            ]

            result = run_daily(
                root_dir=root,
                config_path=root / "config" / "sources.json",
                db_path=root / "data" / "demand_engine.db",
                offline_items=raw_items,
                report_date="2026-05-18",
                no_llm=True,
            )

            self.assertEqual(result["analysis_mode"], "heuristic")
            self.assertEqual(result["failed_scores"], 0)

    def test_run_daily_codex_provider_uses_codex_client_factory(self):
        class FakeLLMClient:
            def analyze(self, prompt, schema):
                packet = json.loads(prompt.split("Candidates JSON:\n", 1)[1])
                return {
                    "tracks": [
                        {
                            "candidate_ids": [packet[0]["candidate_id"]],
                            "mvp_concept": "Codex-mined report workflow",
                            "target_audience": "solo consultants",
                            "pain_summary": "Manual reports are slow.",
                            "source_excerpt": "Manual reports are slow and frustrating",
                            "opportunity_thesis": "Solo consultants need a tighter report workflow.",
                            "existing_workaround": "Copying data manually.",
                            "anti_signals": ["May be solved by BI exports."],
                            "confidence_note": "Codex provider test fixture.",
                            "scores": {"errc": 20, "jtbd": 20, "opc": 24, "rice": 16},
                            "why": "Narrow repeated workflow pain.",
                            "validation_step": "Ask five consultants for their last report workflow.",
                        }
                    ],
                    "discarded_patterns": [],
                    "source_quality_notes": [],
                }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw_items = [
                RawItemInput(
                    source="hn",
                    source_url="https://news.ycombinator.com/item?id=555",
                    title="Manual reports are slow",
                    body="Manual reports are slow and frustrating.",
                )
            ]

            result = run_daily(
                root_dir=root,
                config_path=root / "config" / "sources.json",
                db_path=root / "data" / "demand_engine.db",
                offline_items=raw_items,
                report_date="2026-05-18",
                llm_provider="codex",
                llm_client_factory=lambda provider: FakeLLMClient(),
            )

            self.assertEqual(result["analysis_mode"], "codex")
            latest_json = json.loads((root / "reports" / "latest.json").read_text(encoding="utf-8"))
            self.assertEqual(latest_json["analysis_mode"], "codex")


if __name__ == "__main__":
    unittest.main()
