import unittest

from pipeline_enricher import enrich_clusters_with_pipeline


class PipelineEnricherTest(unittest.TestCase):
    def test_enrich_clusters_adds_funnel_fields_without_mutating_input(self):
        clusters = [
            {
                "cluster_id": "cluster-shopify-reconcile",
                "title": "报表与数据导出工作流",
                "category": "运营/内部流程",
                "decision_score": 76,
                "decision_verdict": "Monitor",
                "source_count": 2,
                "count_7d": 3,
                "top_score": 81,
                "evidence_chain": {"passed_count": 4, "total_count": 5},
                "sample_ideas": [
                    {
                        "idea_id": "idea-1",
                        "title": "Need alternative to Expensify for Shopify invoice export",
                        "pain_summary": "Manually exporting Shopify reports to Excel takes too long and costs $99.",
                        "source": "Reddit r/shopify",
                        "source_url": "https://example.com/reddit-1",
                    }
                ],
            }
        ]

        enriched = enrich_clusters_with_pipeline(clusters)

        self.assertNotIn("funnel_score", clusters[0])
        self.assertIn("funnel_score", enriched[0])
        self.assertIn("total_score", enriched[0]["funnel_score"])
        self.assertIn(enriched[0]["funnel_verdict"], {"Build Now", "Validate Manually", "Monitor", "Discard"})
        self.assertTrue(enriched[0]["funnel_next_step"])
        self.assertNotIn("validation_pack", enriched[0])
        self.assertNotIn("pain_signals", enriched[0])
        self.assertNotIn("signal_evidence_chain", enriched[0])
        self.assertNotIn("experiment_summary", enriched[0])


if __name__ == "__main__":
    unittest.main()
