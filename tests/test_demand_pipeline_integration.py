import unittest
from unittest.mock import patch

from demand_engine import RawItem, filter_candidates, run_demand_scan


def raw_item(item_id: str, title: str, body: str = "", source: str = "Manual x") -> RawItem:
    return RawItem(
        id=item_id,
        source=source,
        title=title,
        body=body,
        source_url=f"https://example.com/{item_id}",
        published_at="",
        metadata={},
    )


class DemandPipelineIntegrationTest(unittest.TestCase):
    def test_filter_candidates_discards_promotional_noise_even_with_pain_terms(self):
        items = [
            raw_item("noise", "I built a newsletter about manual workflow startup advice. Subscribe now."),
            raw_item("pain", "Manual invoice export workflow takes too long and costs $99."),
        ]

        candidates = filter_candidates(items, min_chars=10)

        self.assertEqual([item.id for item, _rules in candidates], ["pain"])

    def test_run_demand_scan_accepts_manual_extra_items_and_reports_source_counts(self):
        extra = [
            raw_item(
                "manual-1",
                "每次导出报表都要手动复制到 Excel 太麻烦了",
                source="Manual xiaohongshu",
            )
        ]

        with patch("demand_engine.fetch_hn_items", return_value=([], [])), \
            patch("demand_engine.fetch_reddit_items", return_value=([], [])), \
            patch("demand_engine.fetch_app_store_reviews", return_value=([], [])), \
            patch("demand_engine.get_repeat_counts", return_value={}):
            ideas, summary = run_demand_scan([], [], "", [], "us", extra_items=extra)

        self.assertEqual(len(ideas), 1)
        self.assertEqual(summary["raw_source_counts"]["Manual xiaohongshu"], 1)
        self.assertEqual(summary["candidate_source_counts"]["Manual xiaohongshu"], 1)


if __name__ == "__main__":
    unittest.main()
