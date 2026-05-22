import tempfile
import unittest
from pathlib import Path

import source_metrics
from demand_engine import RawItem


def raw_item(source: str, item_id: str) -> RawItem:
    return RawItem(
        id=item_id,
        source=source,
        title=f"{source} title",
        body="manual workflow is slow",
        source_url=f"https://example.com/{item_id}",
        published_at="",
        metadata={},
    )


class SourceMetricsTest(unittest.TestCase):
    def test_build_source_metrics_calculates_rates_and_actions(self):
        raw_items = [
            raw_item("Reddit r/SaaS", "a"),
            raw_item("Reddit r/SaaS", "b"),
            raw_item("Hacker News", "c"),
        ]
        candidate_items = [raw_items[0], raw_items[1]]
        clusters = [
            {
                "cluster_id": "cluster-a",
                "source_names": ["Reddit r/SaaS"],
                "decision_verdict": "Build Now",
            }
        ]

        rows = source_metrics.build_source_metrics(raw_items, candidate_items, clusters, {"Hacker News": 1})
        by_source = {row["source"]: row for row in rows}

        self.assertEqual(by_source["Reddit r/SaaS"]["raw_count"], 2)
        self.assertEqual(by_source["Reddit r/SaaS"]["candidate_count"], 2)
        self.assertEqual(by_source["Reddit r/SaaS"]["candidate_rate"], 1.0)
        self.assertEqual(by_source["Reddit r/SaaS"]["validation_candidate_count"], 1)
        self.assertEqual(by_source["Reddit r/SaaS"]["recommended_action"], "increase")
        self.assertEqual(by_source["Hacker News"]["recommended_action"], "pause")

    def test_save_and_load_source_metrics(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "source_metrics.json"
            rows = [{"source": "Manual x", "raw_count": 1}]

            source_metrics.save_source_metrics(rows, path)
            loaded = source_metrics.load_source_metrics(path)

        self.assertEqual(loaded, rows)

    def test_history_trend_overrides_actions_after_repeated_low_quality_runs(self):
        current_rows = [
            {
                "source": "Reddit r/SaaS",
                "raw_count": 10,
                "candidate_count": 1,
                "candidate_rate": 0.1,
                "signal_count": 1,
                "cluster_count": 0,
                "validation_candidate_count": 0,
                "error_count": 0,
                "recommended_action": "reduce",
            },
            {
                "source": "Manual x",
                "raw_count": 1,
                "candidate_count": 1,
                "candidate_rate": 1.0,
                "signal_count": 1,
                "cluster_count": 1,
                "validation_candidate_count": 1,
                "error_count": 0,
                "recommended_action": "increase",
            },
        ]
        history = [
            {
                "generated_at": "2026-05-20",
                "metrics": [{"source": "Reddit r/SaaS", "candidate_rate": 0.05, "error_count": 0}],
            },
            {
                "generated_at": "2026-05-21",
                "metrics": [{"source": "Reddit r/SaaS", "candidate_rate": 0.08, "error_count": 0}],
            },
        ]

        trended = source_metrics.apply_source_metric_trends(current_rows, history)
        by_source = {row["source"]: row for row in trended}

        self.assertEqual(by_source["Reddit r/SaaS"]["recommended_action"], "pause")
        self.assertEqual(by_source["Reddit r/SaaS"]["trend_window"], 3)
        self.assertLess(by_source["Reddit r/SaaS"]["trend_candidate_rate"], 0.12)
        self.assertEqual(by_source["Manual x"]["recommended_action"], "increase")

    def test_append_and_load_source_metric_history_limits_records(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "source_metrics_history.json"

            source_metrics.append_source_metrics_history(
                [{"source": "old", "candidate_rate": 0}],
                generated_at="2026-05-20",
                path=path,
                max_records=1,
            )
            source_metrics.append_source_metrics_history(
                [{"source": "new", "candidate_rate": 1}],
                generated_at="2026-05-21",
                path=path,
                max_records=1,
            )
            history = source_metrics.load_source_metrics_history(path)

        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["generated_at"], "2026-05-21")
        self.assertEqual(history[0]["metrics"][0]["source"], "new")


if __name__ == "__main__":
    unittest.main()
