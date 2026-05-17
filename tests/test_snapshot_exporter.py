import json
import tempfile
import unittest
from pathlib import Path

from snapshot_exporter import build_dashboard_snapshot, load_dashboard_snapshot, write_dashboard_snapshot


class SnapshotExporterTest(unittest.TestCase):
    def test_build_dashboard_snapshot_has_stable_shape(self):
        ideas = [
            {
                "mvp_concept": "为小团队提供一个低成本报表自动化工具。",
                "category": "运营/内部流程",
                "total_score": 78,
                "verdict": "Build Now",
                "pain_summary": "Manual reporting takes too long.",
                "validation_step": "访谈 5 个有相同流程的人。",
                "source": "Hacker News",
                "title": "Manual reporting workflow",
                "source_url": "https://example.com/source",
                "repeat_7d": 3,
                "label": "好信号",
            },
            {
                "mvp_concept": "为客服团队整理重复问题。",
                "category": "客服/成功/留存",
                "total_score": 50,
                "verdict": "Monitor",
                "label": "非研发需求",
            }
        ]
        summary = {
            "raw_count": 10,
            "candidate_count": 1,
            "build_now_count": 1,
            "monitor_count": 0,
            "saved_count": 1,
            "generated_at": "2026-05-17 20:00:00",
        }
        history_summary = {
            "category_counts": {"运营/内部流程": 4},
            "repeated_signals": [
                {
                    "category": "运营/内部流程",
                    "count": 3,
                    "top_score": 78,
                    "sample_concept": "为小团队提供一个低成本报表自动化工具。",
                    "sample_url": "https://example.com/source",
                }
            ],
        }

        snapshot = build_dashboard_snapshot(
            ideas=ideas,
            summary=summary,
            history_summary=history_summary,
            markdown_report="# Report",
        )

        self.assertEqual(snapshot["generated_at"], "2026-05-17 20:00:00")
        self.assertEqual(snapshot["summary"]["candidate_count"], 1)
        self.assertEqual(snapshot["top_ideas"][0]["category"], "运营/内部流程")
        self.assertEqual(snapshot["category_counts"]["运营/内部流程"], 4)
        self.assertEqual(snapshot["repeated_signals_7d"][0]["count"], 3)
        self.assertEqual(snapshot["label_counts"]["好信号"], 1)
        self.assertEqual(snapshot["label_counts"]["非研发需求"], 1)
        self.assertEqual(snapshot["markdown_report"], "# Report")

    def test_load_dashboard_snapshot_handles_missing_and_invalid_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            missing_path = Path(tmpdir) / "missing.json"
            self.assertIsNone(load_dashboard_snapshot(missing_path))

            invalid_path = Path(tmpdir) / "invalid.json"
            invalid_path.write_text("{not-json", encoding="utf-8")
            self.assertIsNone(load_dashboard_snapshot(invalid_path))

    def test_write_dashboard_snapshot_creates_parent_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "data" / "dashboard_snapshot.json"
            write_dashboard_snapshot({"generated_at": "2026-05-17"}, output_path)

            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["generated_at"], "2026-05-17")


if __name__ == "__main__":
    unittest.main()
