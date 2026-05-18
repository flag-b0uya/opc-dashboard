import unittest

from dashboard_presenter import build_quality_notices, evidence_chain_summary


class DashboardPresenterTest(unittest.TestCase):
    def test_evidence_chain_summary_labels_complete_and_incomplete_chains(self):
        strong = evidence_chain_summary({"evidence_chain": {"passed_count": 5, "total_count": 5}})
        weak = evidence_chain_summary({"evidence_chain": {"passed_count": 2, "total_count": 5}})

        self.assertEqual(strong["status"], "strong")
        self.assertEqual(strong["label"], "证据较完整")
        self.assertEqual(weak["status"], "weak")
        self.assertEqual(weak["label"], "证据不足")

    def test_quality_notices_surface_codex_fallback_and_source_errors(self):
        notices = build_quality_notices({
            "summary": {"candidate_count": 3, "errors": ["Reddit failed"]},
            "source_health": {"error_count": 1},
            "analysis_metadata": {"analysis_provider": "codex", "analysis_status": "fallback"},
            "opportunity_clusters": [
                {"evidence_chain": {"passed_count": 2, "total_count": 5}},
            ],
        })

        titles = [notice["title"] for notice in notices]
        self.assertIn("Codex 分析已降级", titles)
        self.assertIn("部分数据源降级", titles)
        self.assertIn("存在证据链缺口", titles)

    def test_quality_notices_confirm_successful_codex_analysis(self):
        notices = build_quality_notices({
            "summary": {"candidate_count": 1, "errors": []},
            "source_health": {"error_count": 0},
            "analysis_metadata": {"analysis_provider": "codex", "analysis_status": "ok"},
            "opportunity_clusters": [
                {"evidence_chain": {"passed_count": 5, "total_count": 5}},
            ],
        })

        self.assertEqual([notice["title"] for notice in notices], ["Codex 深度分析已完成"])


if __name__ == "__main__":
    unittest.main()
