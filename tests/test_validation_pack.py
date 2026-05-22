import unittest

from validation_pack import generate_validation_pack


class ValidationPackTest(unittest.TestCase):
    def test_generate_validation_pack_contains_action_assets_and_decision_rules(self):
        cluster = {
            "cluster_id": "cluster-shopify-export",
            "title": "报表与数据导出工作流",
            "category": "运营/内部流程",
            "sample_ideas": [
                {
                    "pain_summary": "Shopify teams manually export reports to Excel every week and waste hours.",
                    "source": "Reddit r/shopify",
                }
            ],
        }

        pack = generate_validation_pack(cluster)

        self.assertIn("Shopify", pack["one_sentence_pitch"])
        self.assertTrue(pack["landing_page_headline"])
        self.assertIn("reddit_post", pack)
        self.assertIn("cold_dm", pack)
        self.assertGreaterEqual(len(pack["interview_questions"]), 5)
        self.assertGreaterEqual(len(pack["success_metrics"]), 3)
        self.assertGreaterEqual(len(pack["kill_criteria"]), 3)


if __name__ == "__main__":
    unittest.main()
