import unittest
from unittest.mock import patch
import json
import tempfile
from pathlib import Path

from demand_engine import RawItem
from source_health_check import run_checks


def make_item(source: str) -> RawItem:
    return RawItem(
        id=f"{source}-1",
        source=source,
        title=f"{source} title",
        body="manual workflow pain",
        source_url="https://example.com",
        published_at="2026-05-17T00:00:00Z",
        metadata={},
    )


class SourceHealthCheckTest(unittest.TestCase):
    def make_config(self) -> str:
        tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(tmpdir.cleanup)
        config_path = Path(tmpdir.name) / "dashboard_config.json"
        config_path.write_text(
            json.dumps(
                {
                    "hn_queries": ["alternative to", "too expensive", "manual workflow"],
                    "subreddits": ["SaaS", "Entrepreneur", "startups"],
                    "reddit_query": "manual workflow",
                    "app_ids": ["123", "456", "789"],
                }
            ),
            encoding="utf-8",
        )
        return str(config_path)

    @patch("source_health_check.fetch_app_store_reviews")
    @patch("source_health_check.fetch_reddit_items")
    @patch("source_health_check.fetch_hn_items")
    def test_run_checks_reports_success_when_all_sources_return_items(self, hn, reddit, app_store):
        hn.return_value = ([make_item("Hacker News")], [])
        reddit.return_value = ([make_item("Reddit")], [])
        app_store.return_value = ([make_item("App Store")], [])

        results, exit_code = run_checks(config_path=self.make_config(), limit=2)

        self.assertEqual(exit_code, 0)
        self.assertEqual([item["source"] for item in results], ["Hacker News", "Reddit", "App Store"])
        self.assertTrue(all(item["ok"] for item in results))
        self.assertEqual(hn.call_count, 2)
        self.assertEqual(len(results[0]["targets"]), 2)

    @patch("source_health_check.fetch_app_store_reviews")
    @patch("source_health_check.fetch_reddit_items")
    @patch("source_health_check.fetch_hn_items")
    def test_run_checks_reports_failure_when_a_source_has_errors(self, hn, reddit, app_store):
        hn.return_value = ([make_item("Hacker News")], [])
        reddit.return_value = ([], ["rate limited"])
        app_store.return_value = ([make_item("App Store")], [])

        results, exit_code = run_checks(config_path=self.make_config(), limit=2)

        self.assertEqual(exit_code, 1)
        self.assertFalse(results[1]["ok"])
        self.assertEqual(results[1]["errors"], ["rate limited", "rate limited"])

    @patch("source_health_check.fetch_app_store_reviews")
    @patch("source_health_check.fetch_reddit_items")
    @patch("source_health_check.fetch_hn_items")
    def test_run_checks_can_cover_all_configured_sources(self, hn, reddit, app_store):
        hn.return_value = ([make_item("Hacker News")], [])
        reddit.return_value = ([make_item("Reddit")], [])
        app_store.return_value = ([make_item("App Store")], [])

        _results, exit_code = run_checks(config_path=self.make_config(), limit=2, all_configured=True)

        self.assertEqual(exit_code, 0)
        self.assertGreater(hn.call_count, 2)
        self.assertGreater(reddit.call_count, 2)


if __name__ == "__main__":
    unittest.main()
