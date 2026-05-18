import unittest
from unittest.mock import patch

from codex_analysis import CodexAnalysisError, analyze_clusters_with_codex


class CodexAnalysisTests(unittest.TestCase):
    def test_analyze_clusters_extracts_json_and_merges_cluster_fields(self):
        rows = [
            {
                "idea_id": "idea-1",
                "title": "Manual reports are slow",
                "pain_summary": "Manual reports are slow for client teams.",
                "source_url": "https://example.com/1",
                "total_score": 82,
            }
        ]
        clusters = [
            {
                "cluster_id": "ops-reporting-manual",
                "title": "报表与数据导出工作流",
                "decision_score": 78,
                "decision_verdict": "Monitor",
                "sample_ideas": [{"idea_id": "idea-1", "title": "Manual reports are slow"}],
            }
        ]

        class Completed:
            returncode = 0
            stdout = """
            {
              "clusters": [
                {
                  "cluster_id": "ops-reporting-manual",
                  "title": "Client reporting approval workflow",
                  "evidence_summary": "Two signals show agencies manually compile client reports.",
                  "decision_reason": "Repeated manual workflow with clear B2B buyer.",
                  "recommended_action": "Interview five agency operators this week.",
                  "decision_score": 86,
                  "decision_verdict": "Build Now",
                  "codex_opportunity_thesis": "Small agencies need a narrow report approval trail.",
                  "codex_anti_signals": ["Could be covered by project management exports."]
                }
              ]
            }
            """
            stderr = ""

        def runner(command, capture_output, text, timeout, cwd):
            self.assertEqual(command[0], "codex")
            self.assertIn("Return only JSON", command[2])
            return Completed()

        enhanced, meta = analyze_clusters_with_codex(rows, clusters, runner=runner)

        self.assertEqual(meta["analysis_provider"], "codex")
        self.assertEqual(meta["analysis_status"], "ok")
        self.assertEqual(enhanced[0]["decision_verdict"], "Build Now")
        self.assertEqual(enhanced[0]["title"], "Client reporting approval workflow")
        self.assertIn("codex_anti_signals", enhanced[0])

    def test_analyze_clusters_reports_bad_codex_json(self):
        class Completed:
            returncode = 0
            stdout = "not json"
            stderr = ""

        def runner(command, capture_output, text, timeout, cwd):
            return Completed()

        with self.assertRaises(CodexAnalysisError):
            analyze_clusters_with_codex([], [], runner=runner)

    def test_analyze_clusters_falls_back_when_path_codex_is_broken(self):
        class Failed:
            returncode = 1
            stdout = ""
            stderr = "missing vendor binary"

        class Completed:
            returncode = 0
            stdout = '{"clusters":[]}'
            stderr = ""

        calls = []

        def runner(command, capture_output, text, timeout, cwd):
            calls.append(command[0])
            if command[0] == "codex":
                return Failed()
            return Completed()

        with patch("codex_analysis._candidate_codex_bins", return_value=["codex", "/tmp/good-codex"]):
            _enhanced, meta = analyze_clusters_with_codex([], [], runner=runner)

        self.assertGreaterEqual(len(calls), 2)
        self.assertEqual(calls[0], "codex")
        self.assertEqual(meta["analysis_status"], "ok")
        self.assertNotEqual(meta["analysis_binary"], "codex")


if __name__ == "__main__":
    unittest.main()
