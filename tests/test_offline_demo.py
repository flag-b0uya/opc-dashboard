import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from offline_demo import build_offline_demo_snapshot, write_offline_demo_snapshot


class OfflineDemoTest(unittest.TestCase):
    def test_build_offline_demo_snapshot_runs_complete_pipeline_without_network(self):
        with patch("demand_engine.fetch_hn_items") as fetch_hn, \
            patch("demand_engine.fetch_reddit_items") as fetch_reddit, \
            patch("demand_engine.fetch_app_store_reviews") as fetch_app_store, \
            patch("demand_engine.get_repeat_counts", return_value={}):
            fetch_hn.return_value = ([], [])
            fetch_reddit.return_value = ([], [])
            fetch_app_store.return_value = ([], [])
            snapshot = build_offline_demo_snapshot()

        fetch_hn.assert_called_once_with([], 10)
        fetch_reddit.assert_called_once_with([], "", 10)
        fetch_app_store.assert_called_once_with([], "us", 10)
        self.assertEqual(snapshot["schema_version"], 2)
        self.assertGreaterEqual(snapshot["summary"]["candidate_count"], 3)
        self.assertGreaterEqual(len(snapshot["opportunity_clusters"]), 1)
        self.assertGreaterEqual(len(snapshot["source_metrics"]), 3)
        self.assertEqual(snapshot["container_summary"], {})
        self.assertEqual(snapshot["pain_signal_summary"], {})
        self.assertEqual(snapshot["analysis_metadata"]["analysis_provider"], "offline_demo")

        cluster = snapshot["opportunity_clusters"][0]
        self.assertIn("funnel_score", cluster)
        self.assertIn("funnel_verdict", cluster)
        self.assertIn("funnel_next_step", cluster)

    def test_write_offline_demo_snapshot_writes_json_to_target_path(self):
        with tempfile.TemporaryDirectory() as tmpdir, \
            patch("demand_engine.fetch_hn_items", return_value=([], [])), \
            patch("demand_engine.fetch_reddit_items", return_value=([], [])), \
            patch("demand_engine.fetch_app_store_reviews", return_value=([], [])), \
            patch("demand_engine.get_repeat_counts", return_value={}):
            output_path = Path(tmpdir) / "demo" / "snapshot.json"

            snapshot = write_offline_demo_snapshot(output_path)

            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_version"], snapshot["schema_version"])
            self.assertEqual(payload["analysis_metadata"]["analysis_status"], "fixture")


if __name__ == "__main__":
    unittest.main()
