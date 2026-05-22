import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from delivery_check import (
    PHASE1_DELIVERY_COMMANDS,
    check_dashboard_snapshot_ready,
    check_runtime_dependencies,
    run_delivery_check,
)


class DeliveryCheckTest(unittest.TestCase):
    def test_check_dashboard_snapshot_ready_requires_funnel_score(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            data = root / "data"
            data.mkdir()
            snapshot = {
                "summary": {"candidate_count": 1},
                "opportunity_clusters": [
                    {
                        "cluster_id": "cluster-1",
                        "funnel_score": {"total_score": 80},
                    }
                ],
            }
            (data / "dashboard_snapshot.json").write_text(json.dumps(snapshot), encoding="utf-8")

            result = check_dashboard_snapshot_ready(root)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["candidate_count"], 1)
        self.assertEqual(result["cluster_count"], 1)
        self.assertTrue(result["has_funnel_score"])

    def test_check_dashboard_snapshot_ready_reports_missing_funnel_score(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            data = root / "data"
            data.mkdir()
            snapshot = {
                "summary": {"candidate_count": 1},
                "opportunity_clusters": [{"cluster_id": "cluster-1"}],
            }
            (data / "dashboard_snapshot.json").write_text(json.dumps(snapshot), encoding="utf-8")

            result = check_dashboard_snapshot_ready(root)

        self.assertEqual(result["status"], "error")
        self.assertFalse(result["has_funnel_score"])
        self.assertIn("funnel_score", result["message"])

    def test_run_delivery_check_runs_phase1_commands_and_snapshot_check(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            data = root / "data"
            data.mkdir()
            snapshot = {
                "summary": {"candidate_count": 2},
                "opportunity_clusters": [
                    {
                        "cluster_id": "cluster-1",
                        "funnel_score": {"total_score": 82},
                    }
                ],
            }
            (data / "dashboard_snapshot.json").write_text(json.dumps(snapshot), encoding="utf-8")
            commands = []

            def fake_runner(command, cwd):
                commands.append(command)
                return {"name": " ".join(command), "status": "ok", "returncode": 0}

            result = run_delivery_check(
                root,
                command_runner=fake_runner,
                dependency_checker=lambda: {"status": "ok", "dependencies": {"streamlit": "ok"}},
            )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(commands, PHASE1_DELIVERY_COMMANDS)
        self.assertEqual(result["snapshot"]["status"], "ok")
        self.assertEqual(result["runtime"]["status"], "ok")

    def test_check_runtime_dependencies_reports_missing_streamlit(self):
        with patch("importlib.util.find_spec", return_value=None):
            result = check_runtime_dependencies()

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["dependencies"]["streamlit"], "missing")


if __name__ == "__main__":
    unittest.main()
