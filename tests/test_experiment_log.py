import tempfile
import unittest
from pathlib import Path

import experiment_log


class ExperimentLogTest(unittest.TestCase):
    def test_add_and_summarize_experiments_by_cluster(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "experiment_results.json"
            first = experiment_log.add_experiment(
                cluster_id="cluster-a",
                channel="reddit",
                asset_type="post",
                audience="r/shopify",
                views=120,
                replies=3,
                waitlist_signups=1,
                paid_commitments=0,
                objections=["already using Excel"],
                path=path,
            )
            experiment_log.add_experiment(
                cluster_id="cluster-a",
                channel="x",
                asset_type="dm",
                audience="Shopify operators",
                views=200,
                clicks=18,
                calls_booked=1,
                paid_commitments=1,
                path=path,
            )
            records = experiment_log.load_experiments(path)
            summaries = experiment_log.summarize_by_cluster(records)

        self.assertTrue(first["experiment_id"])
        self.assertEqual(len(records), 2)
        summary = summaries["cluster-a"]
        self.assertEqual(summary["experiments_count"], 2)
        self.assertEqual(summary["views"], 320)
        self.assertEqual(summary["clicks"], 18)
        self.assertEqual(summary["replies"], 3)
        self.assertEqual(summary["waitlist_signups"], 1)
        self.assertEqual(summary["calls_booked"], 1)
        self.assertEqual(summary["paid_commitments"], 1)
        self.assertIn("already using Excel", summary["main_objections"])

    def test_load_experiments_handles_missing_and_invalid_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "missing.json"
            self.assertEqual(experiment_log.load_experiments(path), [])

            path.write_text("{bad json", encoding="utf-8")
            self.assertEqual(experiment_log.load_experiments(path), [])


if __name__ == "__main__":
    unittest.main()
