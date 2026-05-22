import unittest

from noise_filter import analyze_text


class NoiseFilterTest(unittest.TestCase):
    def test_manual_workflow_with_payment_signal_is_kept(self):
        result = analyze_text("Every week we manually export Shopify reports to Excel. This costs $99 and takes too long.")

        self.assertEqual(result["decision"], "keep")
        self.assertGreaterEqual(result["candidate_score"], 40)
        self.assertIn("manual", result["pain_hits"])
        self.assertIn("export", result["workflow_hits"])
        self.assertIn("$", result["payment_hits"])
        self.assertEqual(result["noise_hits"], [])

    def test_low_value_or_promotional_text_is_discarded(self):
        result = analyze_text("Thanks, awesome post. Subscribe to my newsletter for startup advice.")

        self.assertEqual(result["decision"], "discard")
        self.assertLess(result["candidate_score"], 20)
        self.assertIn("newsletter", result["noise_hits"])
        self.assertTrue(result["filter_reason"])

    def test_unclear_but_relevant_text_is_watched(self):
        result = analyze_text("Looking for a tool to help with customer onboarding.")

        self.assertEqual(result["decision"], "watch")
        self.assertIn("looking for", result["pain_hits"])

    def test_short_chinese_workflow_pain_is_not_discarded(self):
        result = analyze_text("报表导出太麻烦")

        self.assertEqual(result["decision"], "watch")
        self.assertIn("麻烦", result["pain_hits"])
        self.assertIn("报表", result["workflow_hits"])

    def test_short_chinese_payment_workflow_pain_is_kept(self):
        result = analyze_text("每周手动对账太贵，愿意付费")

        self.assertEqual(result["decision"], "keep")
        self.assertIn("手动", result["pain_hits"])
        self.assertIn("对账", result["workflow_hits"])
        self.assertIn("付费", result["payment_hits"])

    def test_self_promotion_with_pain_terms_is_discarded(self):
        result = analyze_text("我做了一个 newsletter 分享 manual workflow 创业复盘，subscribe 获取模板。")

        self.assertEqual(result["decision"], "discard")
        self.assertIn("newsletter", result["noise_hits"])


if __name__ == "__main__":
    unittest.main()
