import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from demand_engine import RawItem
from local_runner import fetch_items_with_reliability


def make_item(item_id: str, source: str = "Hacker News") -> RawItem:
    return RawItem(
        id=item_id,
        source=source,
        title=f"{item_id} manual workflow alternative",
        body="Teams need a tool because this manual workflow takes too long.",
        source_url="https://example.com",
        published_at="2026-05-19T00:00:00Z",
        metadata={"points": 50, "comments": 10},
    )


class LocalRunnerReliabilityTest(unittest.TestCase):
    def base_options(self, cache_path: Path) -> dict:
        return {
            "hn_queries": ["manual workflow"],
            "subreddits": [],
            "reddit_query": "",
            "app_ids": ["123"],
            "app_store_country": "us",
            "limit_per_source": 2,
            "source_cache_path": str(cache_path),
        }

    @patch("local_runner.fetch_app_store_reviews")
    @patch("local_runner.fetch_hn_items")
    def test_fetch_items_with_reliability_uses_cache_for_failed_source(self, hn, app_store):
        with tempfile.TemporaryDirectory() as tmpdir:
            options = self.base_options(Path(tmpdir) / "source_cache.json")
            hn.return_value = ([make_item("hn-1")], [])
            app_store.return_value = ([make_item("app-1", "App Store US")], [])

            first_items, first_report = fetch_items_with_reliability(options)

            app_store.return_value = ([], ["App Store HTTP 500"])
            second_items, second_report = fetch_items_with_reliability(options)

        self.assertEqual([item.id for item in first_items], ["hn-1", "app-1"])
        self.assertEqual([item.id for item in second_items], ["hn-1", "app-1"])
        statuses = {status["source"]: status for status in second_report.statuses}
        self.assertEqual(statuses["App Store"]["status"], "fallback")
        self.assertTrue(statuses["App Store"]["used_cache"])

    @patch("local_runner.fetch_reddit_items")
    @patch("local_runner.fetch_app_store_reviews")
    @patch("local_runner.fetch_hn_items")
    def test_fetch_items_with_reliability_skips_disabled_sources(self, hn, app_store, reddit):
        with tempfile.TemporaryDirectory() as tmpdir:
            options = self.base_options(Path(tmpdir) / "source_cache.json")
            hn.return_value = ([make_item("hn-1")], [])
            app_store.return_value = ([make_item("app-1", "App Store US")], [])

            _items, report = fetch_items_with_reliability(options)

        reddit.assert_not_called()
        statuses = {status["source"]: status for status in report.statuses}
        self.assertEqual(statuses["Reddit"]["status"], "disabled")


if __name__ == "__main__":
    unittest.main()
