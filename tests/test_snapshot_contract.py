import unittest

from offline_demo import build_offline_demo_snapshot
from snapshot_contract import validate_snapshot_contract


class SnapshotContractTest(unittest.TestCase):
    def test_validates_complete_offline_demo_snapshot(self):
        snapshot = build_offline_demo_snapshot()

        result = validate_snapshot_contract(snapshot)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["warnings"], [])

    def test_reports_core_shape_errors(self):
        result = validate_snapshot_contract({
            "schema_version": 2,
            "summary": {"candidate_count": 1},
            "opportunity_clusters": "not-a-list",
        })

        self.assertEqual(result["status"], "error")
        self.assertIn("missing top-level field: top_ideas", result["errors"])
        self.assertIn("summary missing field: raw_count", result["errors"])
        self.assertIn("opportunity_clusters must be a list", result["errors"])

    def test_reports_architecture_fields_as_warnings_for_older_snapshots(self):
        result = validate_snapshot_contract({
            "schema_version": 2,
            "generated_at": "2026-05-21 10:00:00",
            "summary": {
                "raw_count": 1,
                "unique_count": 1,
                "candidate_count": 1,
                "build_now_count": 0,
                "monitor_count": 1,
                "discard_count": 0,
                "saved_count": 0,
                "errors": [],
            },
            "top_ideas": [],
            "opportunity_clusters": [
                {"cluster_id": "cluster-1", "title": "Manual workflow", "decision_verdict": "Monitor"}
            ],
            "decision_summary": {},
            "source_health": {},
            "source_stats": {},
            "category_counts": {},
            "repeated_signals_7d": [],
            "label_counts": {},
            "analysis_metadata": {},
            "markdown_report": "",
        })

        self.assertEqual(result["status"], "warning")
        self.assertIn("missing architecture field: source_metrics", result["warnings"])
        self.assertIn("cluster cluster-1 missing action field: funnel_score", result["warnings"])


if __name__ == "__main__":
    unittest.main()
