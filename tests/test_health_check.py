import tempfile
import unittest
import json
from pathlib import Path

from health_check import check_local_pipeline, summarize_status


class HealthCheckTest(unittest.TestCase):
    def test_check_local_pipeline_reports_required_and_optional_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            data = root / "data"
            data.mkdir()
            (data / "dashboard_snapshot.json").write_text(json.dumps({
                "schema_version": 2,
                "generated_at": "2026-05-21 10:00:00",
                "summary": {
                    "raw_count": 0,
                    "unique_count": 0,
                    "candidate_count": 0,
                    "build_now_count": 0,
                    "monitor_count": 0,
                    "discard_count": 0,
                    "saved_count": 0,
                    "errors": [],
                },
                "top_ideas": [],
                "opportunity_clusters": [],
                "decision_summary": {},
                "source_health": {},
                "source_stats": {},
                "source_metrics": [],
                "container_summary": {},
                "pain_signal_summary": {},
                "category_counts": {},
                "repeated_signals_7d": [],
                "label_counts": {},
                "analysis_metadata": {},
                "markdown_report": "",
            }), encoding="utf-8")
            (data / "manual_intake.json").write_text("[]", encoding="utf-8")

            result = check_local_pipeline(root)

        by_name = {item["name"]: item for item in result["checks"]}
        self.assertEqual(by_name["dashboard_snapshot"]["status"], "ok")
        self.assertEqual(by_name["manual_intake"]["status"], "ok")
        self.assertEqual(by_name["experiment_results"]["status"], "missing_optional")
        self.assertEqual(result["status"], "ok")

    def test_check_local_pipeline_surfaces_snapshot_contract_errors(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            data = root / "data"
            data.mkdir()
            (data / "dashboard_snapshot.json").write_text('{"schema_version": 2}', encoding="utf-8")

            result = check_local_pipeline(root)

        by_name = {item["name"]: item for item in result["checks"]}
        self.assertEqual(result["status"], "error")
        self.assertEqual(by_name["dashboard_snapshot"]["status"], "contract_error")
        self.assertTrue(by_name["dashboard_snapshot"]["contract_errors"])

    def test_check_local_pipeline_reports_invalid_json_as_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            data = root / "data"
            data.mkdir()
            (data / "dashboard_snapshot.json").write_text("{bad json", encoding="utf-8")

            result = check_local_pipeline(root)

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["checks"][0]["status"], "invalid_json")

    def test_check_local_pipeline_warns_when_source_metrics_sidecar_is_stale(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            data = root / "data"
            data.mkdir()
            snapshot = {
                "schema_version": 2,
                "generated_at": "2026-05-21 10:00:00",
                "summary": {
                    "raw_count": 3,
                    "unique_count": 3,
                    "candidate_count": 2,
                    "build_now_count": 1,
                    "monitor_count": 1,
                    "discard_count": 0,
                    "saved_count": 0,
                    "errors": [],
                },
                "top_ideas": [],
                "opportunity_clusters": [],
                "decision_summary": {},
                "source_health": {},
                "source_stats": {},
                "source_metrics": [
                    {
                        "source": "Manual xiaohongshu",
                        "raw_count": 3,
                        "candidate_count": 2,
                        "candidate_rate": 0.67,
                    }
                ],
                "container_summary": {},
                "pain_signal_summary": {},
                "category_counts": {},
                "repeated_signals_7d": [],
                "label_counts": {},
                "analysis_metadata": {},
                "markdown_report": "",
            }
            stale_metrics = [
                {
                    "source": "Manual xiaohongshu",
                    "raw_count": 0,
                    "candidate_count": 0,
                    "candidate_rate": 0.0,
                }
            ]
            (data / "dashboard_snapshot.json").write_text(json.dumps(snapshot), encoding="utf-8")
            (data / "source_metrics.json").write_text(json.dumps(stale_metrics), encoding="utf-8")

            result = check_local_pipeline(root)

        by_name = {item["name"]: item for item in result["checks"]}
        self.assertEqual(result["status"], "ok")
        self.assertEqual(by_name["source_metrics"]["status"], "stale_warning")
        self.assertIn("does not match dashboard_snapshot", by_name["source_metrics"]["warning"])
        self.assertEqual(result["summary"]["warnings"], 1)

    def test_summarize_status_counts_error_and_missing_optional(self):
        summary = summarize_status([
            {"status": "ok"},
            {"status": "missing_optional"},
            {"status": "invalid_json"},
            {"status": "contract_warning"},
        ])

        self.assertEqual(summary["ok"], 1)
        self.assertEqual(summary["missing_optional"], 1)
        self.assertEqual(summary["errors"], 1)
        self.assertEqual(summary["warnings"], 1)


if __name__ == "__main__":
    unittest.main()
