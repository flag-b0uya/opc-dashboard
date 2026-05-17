import copy
import unittest

from demand_engine import build_decision_summary, build_opportunity_clusters


def idea_row(**overrides):
    row = {
        "idea_id": "idea-1",
        "title": "Manual invoice reporting is slow",
        "source": "Hacker News",
        "source_url": "https://example.com/1",
        "category": "运营/内部流程",
        "signal_key": "sig-1",
        "mvp_concept": "为财务运营团队构建自动化发票报表工具。",
        "target_audience": "需要降低人工流程成本的小团队或 B2B 用户",
        "pain_summary": "Our team manually reconciles invoices and exports weekly reports.",
        "matched_rules": ["manual", "takes too long"],
        "category_signals": ["invoice", "report"],
        "total_score": 82,
        "repeat_7d": 1,
        "verdict": "Build Now",
        "validation_step": "今天访谈 5 个有相同流程的人，确认每周浪费的时间。",
        "label": "未标注",
    }
    row.update(overrides)
    return row


class OpportunityClusterTest(unittest.TestCase):
    def test_similar_pain_points_cluster_together(self):
        ideas = [
            idea_row(
                idea_id="invoice-a",
                title="Manual invoice reporting takes too long",
                pain_summary="We manually reconcile invoices and build reporting exports every week.",
                repeat_7d=2,
            ),
            idea_row(
                idea_id="invoice-b",
                title="Need invoice report automation",
                source="Reddit r/smallbusiness",
                source_url="https://example.com/2",
                pain_summary="Missing automation for invoice reporting and export workflow.",
                matched_rules=["manual", "missing"],
                repeat_7d=1,
                total_score=78,
            ),
        ]

        clusters = build_opportunity_clusters(ideas, {"records": []})

        self.assertEqual(len(clusters), 1)
        cluster = clusters[0]
        self.assertEqual(cluster["category"], "运营/内部流程")
        self.assertEqual(cluster["count_7d"], 2)
        self.assertEqual(cluster["source_count"], 2)
        self.assertEqual(len(cluster["sample_ideas"]), 2)
        self.assertIn("invoice", cluster["cluster_id"])

    def test_different_business_contexts_do_not_merge_on_generic_manual_terms(self):
        ideas = [
            idea_row(
                idea_id="invoice",
                title="Manual invoice reporting is slow",
                pain_summary="Manual invoice reconciliation and reporting blocks finance ops.",
                matched_rules=["manual"],
            ),
            idea_row(
                idea_id="support",
                title="Manual customer support triage is slow",
                pain_summary="Manual support ticket routing makes customer response time worse.",
                matched_rules=["manual"],
                category="客服/成功/留存",
                mvp_concept="为客服团队构建工单自动分流工具。",
            ),
        ]

        clusters = build_opportunity_clusters(ideas, {"records": []})

        self.assertEqual(len(clusters), 2)
        self.assertEqual({cluster["category"] for cluster in clusters}, {"运营/内部流程", "客服/成功/留存"})

    def test_build_now_requires_repeated_evidence_not_single_noisy_high_score(self):
        ideas = [
            idea_row(
                idea_id="generic-startup",
                title="What no one warns you about before building a startup",
                pain_summary="My reflection on founder life, distribution, and why most ideas fail.",
                mvp_concept="为独立创业者构建一个创业反思内容库。",
                total_score=95,
                repeat_7d=1,
                matched_rules=["hard", "fail"],
                validation_step="继续观察。",
            )
        ]

        clusters = build_opportunity_clusters(ideas, {"records": []})

        self.assertEqual(clusters[0]["decision_verdict"], "Monitor")
        self.assertLess(clusters[0]["decision_score"], 82)
        self.assertIn("重复", clusters[0]["decision_reason"])

    def test_repeated_noisy_discussion_is_capped_below_strong_opportunity(self):
        ideas = [
            idea_row(
                idea_id=f"noise-{index}",
                title="Maybe some startup advice is too universal, especially don't build just sell first",
                source="Reddit r/startups" if index % 2 else "Reddit r/SaaS",
                pain_summary="A founder reflection on startup advice and why ideas fail.",
                total_score=88 - index,
            )
            for index in range(6)
        ]

        cluster = build_opportunity_clusters(ideas, {"records": []})[0]

        self.assertEqual(cluster["decision_verdict"], "Monitor")
        self.assertLessEqual(cluster["decision_score"], 79)
        self.assertIn("噪音惩罚", cluster["decision_reason"])

    def test_history_duplicate_same_item_does_not_inflate_repeat_evidence(self):
        idea = idea_row(
            idea_id="pm-confusion",
            title="Confused how to work with a PM",
            pain_summary="One person asks how developers should collaborate with a product manager.",
            total_score=73,
        )
        history_summary = {
            "records": [
                {**idea, "scan_id": "scan-1"},
                {**idea, "scan_id": "scan-2"},
                {**idea, "scan_id": "scan-3"},
            ]
        }

        cluster = build_opportunity_clusters([idea], history_summary)[0]

        self.assertEqual(cluster["count_7d"], 1)
        self.assertEqual(cluster["decision_verdict"], "Monitor")

    def test_labels_adjust_cluster_decision_score(self):
        good = idea_row(idea_id="good-a", label="好信号", repeat_7d=2)
        noisy = copy.deepcopy(good)
        noisy["idea_id"] = "noise-a"
        noisy["label"] = "噪音"

        good_cluster = build_opportunity_clusters([good], {"records": []})[0]
        noisy_cluster = build_opportunity_clusters([noisy], {"records": []})[0]

        self.assertGreater(good_cluster["decision_score"], noisy_cluster["decision_score"])
        self.assertIn("人工标注", noisy_cluster["decision_reason"])

    def test_decision_summary_counts_cluster_verdicts(self):
        ideas = [
            idea_row(idea_id="a", repeat_7d=2, total_score=86),
            idea_row(idea_id="b", title="Manual support tickets", category="客服/成功/留存", repeat_7d=1, total_score=54),
        ]

        summary = build_decision_summary(build_opportunity_clusters(ideas, {"records": []}))

        self.assertEqual(summary["total_clusters"], 2)
        self.assertIn("build_now_count", summary)
        self.assertIn("monitor_count", summary)


if __name__ == "__main__":
    unittest.main()
