import unittest

from dashboard_presenter import (
    build_action_view,
    build_artifact_summary_rows,
    build_quality_notices,
    build_source_metric_rows,
    evidence_chain_summary,
)


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

    def test_quality_notices_surface_source_cache_fallback(self):
        notices = build_quality_notices({
            "summary": {"candidate_count": 5, "errors": []},
            "source_health": {
                "coverage_status": "degraded",
                "error_count": 1,
                "cache_fallback_count": 1,
                "sources": [
                    {"source": "Hacker News", "status": "ok", "count": 3},
                    {"source": "App Store", "status": "fallback", "count": 2, "used_cache": True},
                ],
            },
            "analysis_metadata": {"analysis_provider": "codex", "analysis_status": "ok"},
            "opportunity_clusters": [],
        })

        titles = [notice["title"] for notice in notices]
        self.assertIn("部分数据沿用缓存", titles)

    def test_build_action_view_surfaces_first_phase_funnel_only(self):
        action = build_action_view({
            "funnel_score": {
                "total_score": 68,
                "verdict": "Validate Manually",
                "competitor_score": 10,
                "distribution_score": 8,
                "risk_penalty": 0,
                "blockers": ["needs a second source"],
            },
            "funnel_next_step": "Send 10 targeted DMs.",
        })

        self.assertEqual(action["funnel"]["verdict"], "Validate Manually")
        self.assertEqual(action["funnel"]["total_score"], 68)
        self.assertEqual(action["funnel"]["competitor_score"], 10)
        self.assertIn("Send 10", action["next_step"])
        self.assertNotIn("validation_assets", action)
        self.assertNotIn("experiment_summary", action)
        self.assertNotIn("signal_evidence", action)

    def test_build_source_metric_rows_formats_rates_and_actions(self):
        rows = build_source_metric_rows([
            {
                "source": "Reddit r/SaaS",
                "raw_count": 20,
                "candidate_count": 8,
                "candidate_rate": 0.4,
                "signal_count": 8,
                "cluster_count": 3,
                "validation_candidate_count": 2,
                "error_count": 0,
                "recommended_action": "increase",
            },
            {
                "source": "Hacker News",
                "raw_count": 10,
                "candidate_count": 0,
                "candidate_rate": 0,
                "signal_count": 0,
                "cluster_count": 0,
                "validation_candidate_count": 0,
                "error_count": 2,
                "recommended_action": "pause",
            },
        ])

        self.assertEqual(rows[0]["来源"], "Reddit r/SaaS")
        self.assertEqual(rows[0]["候选率"], "40%")
        self.assertEqual(rows[0]["建议"], "increase")
        self.assertEqual(rows[1]["错误"], 2)

    def test_build_artifact_summary_rows_formats_container_and_pain_signal_summaries(self):
        rows = build_artifact_summary_rows(
            {"total_containers": 4, "selected_for_sampling": 2, "platform_counts": {"reddit": 3}},
            {"total_pain_signals": 5, "high_confidence_count": 2, "payment_signal_count": 1, "average_confidence": 0.56},
        )

        labels = {row["指标"]: row["值"] for row in rows}
        self.assertEqual(labels["Containers"], 4)
        self.assertEqual(labels["Selected Containers"], 2)
        self.assertEqual(labels["Pain Signals"], 5)
        self.assertEqual(labels["High Confidence Signals"], 2)


if __name__ == "__main__":
    unittest.main()
