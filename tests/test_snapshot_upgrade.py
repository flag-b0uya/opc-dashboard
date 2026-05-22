import copy
import json
import tempfile
import unittest
from pathlib import Path

from snapshot_contract import validate_snapshot_contract
from snapshot_upgrade import migrate_snapshot_to_current_contract, upgrade_snapshot_file


def old_snapshot() -> dict:
    return {
        "schema_version": 2,
        "generated_at": "2026-05-21 10:00:00",
        "summary": {
            "raw_count": 4,
            "unique_count": 4,
            "candidate_count": 2,
            "build_now_count": 1,
            "monitor_count": 1,
            "discard_count": 0,
            "saved_count": 2,
            "errors": [],
        },
        "top_ideas": [
            {
                "idea_id": "idea-1",
                "source": "Reddit r/SaaS",
                "title": "Need alternative to manual invoice workflow",
                "pain_summary": "Finance team manually exports invoices every week. Expensify is too expensive.",
                "source_url": "https://example.com/idea-1",
                "total_score": 78,
            },
            {
                "idea_id": "idea-2",
                "source": "Hacker News",
                "title": "Missing report export workflow",
                "pain_summary": "Support team needs weekly report export automation.",
                "source_url": "https://example.com/idea-2",
                "total_score": 65,
            },
        ],
        "opportunity_clusters": [
            {
                "cluster_id": "cluster-invoice",
                "title": "Invoice export workflow",
                "category": "运营/内部流程",
                "decision_verdict": "Build Now",
                "decision_score": 88,
                "decision_reason": "Repeated workflow pain with payment signal.",
                "evidence_summary": "Two sources complain about manual export.",
                "count_7d": 2,
                "source_count": 2,
                "source_names": ["Reddit r/SaaS", "Hacker News"],
                "top_score": 78,
                "avg_score": 71.5,
                "sample_ideas": [
                    {
                        "idea_id": "idea-1",
                        "source": "Reddit r/SaaS",
                        "title": "Need alternative to manual invoice workflow",
                        "pain_summary": "Finance team manually exports invoices every week. Expensify is too expensive.",
                        "source_url": "https://example.com/idea-1",
                        "total_score": 78,
                    },
                    {
                        "idea_id": "idea-2",
                        "source": "Hacker News",
                        "title": "Missing report export workflow",
                        "pain_summary": "Support team needs weekly report export automation.",
                        "source_url": "https://example.com/idea-2",
                        "total_score": 65,
                    },
                ],
            }
        ],
        "decision_summary": {"total_clusters": 1, "build_now_count": 1, "monitor_count": 0, "discard_count": 0},
        "source_health": {
            "status": "ok",
            "raw_count": 4,
            "unique_count": 4,
            "candidate_count": 2,
            "error_count": 0,
            "errors": [],
            "source_counts": {"Reddit r/SaaS": 1, "Hacker News": 1},
        },
        "source_stats": {},
        "category_counts": {},
        "repeated_signals_7d": [],
        "label_counts": {},
        "analysis_metadata": {"analysis_provider": "codex", "analysis_status": "ok"},
        "markdown_report": "# Report",
    }


class SnapshotUpgradeTest(unittest.TestCase):
    def test_migrate_snapshot_adds_current_architecture_fields_without_mutating_input(self):
        snapshot = old_snapshot()
        before = copy.deepcopy(snapshot)

        upgraded = migrate_snapshot_to_current_contract(snapshot)

        self.assertEqual(snapshot, before)
        self.assertEqual(validate_snapshot_contract(upgraded)["status"], "ok")
        self.assertIn("source_metrics", upgraded)
        self.assertGreaterEqual(len(upgraded["source_metrics"]), 2)
        self.assertEqual(upgraded["container_summary"]["total_containers"], 0)
        self.assertEqual(upgraded["pain_signal_summary"]["total_pain_signals"], 0)

        cluster = upgraded["opportunity_clusters"][0]
        self.assertIn("funnel_score", cluster)
        self.assertIn("funnel_verdict", cluster)
        self.assertIn("funnel_next_step", cluster)
        self.assertNotIn("signal_evidence_chain", cluster)
        self.assertNotIn("experiment_summary", cluster)
        self.assertNotIn("pain_signals", cluster)

    def test_migrate_snapshot_rebuilds_empty_source_metrics(self):
        snapshot = old_snapshot()
        snapshot["source_metrics"] = []

        upgraded = migrate_snapshot_to_current_contract(snapshot)

        self.assertGreaterEqual(len(upgraded["source_metrics"]), 2)
        sources = {row["source"] for row in upgraded["source_metrics"]}
        self.assertIn("Reddit r/SaaS", sources)
        self.assertIn("Hacker News", sources)

    def test_upgrade_snapshot_file_writes_upgraded_payload(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "snapshot.json"
            path.write_text(json.dumps(old_snapshot(), ensure_ascii=False), encoding="utf-8")

            upgraded = upgrade_snapshot_file(path)

            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload, upgraded)
            self.assertEqual(validate_snapshot_contract(payload)["status"], "ok")


if __name__ == "__main__":
    unittest.main()
