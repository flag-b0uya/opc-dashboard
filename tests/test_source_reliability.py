import tempfile
import unittest
from pathlib import Path

from demand_engine import RawItem
from source_reliability import (
    SourceFetchResult,
    SourceReliabilityReport,
    load_source_cache,
    run_source_with_cache,
)


def make_item(item_id: str, source: str = "Hacker News") -> RawItem:
    return RawItem(
        id=item_id,
        source=source,
        title=f"{item_id} title",
        body="manual workflow pain",
        source_url="https://example.com",
        published_at="2026-05-19T00:00:00Z",
        metadata={"rank": 1},
    )


class SourceReliabilityTest(unittest.TestCase):
    def test_successful_fetch_updates_cache_and_reports_ok(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "source_cache.json"

            items, status = run_source_with_cache(
                cache_path,
                source_key="hn",
                source_label="Hacker News",
                enabled=True,
                fetcher=lambda: SourceFetchResult([make_item("hn-1")], []),
            )

            cache = load_source_cache(cache_path)

        self.assertEqual([item.id for item in items], ["hn-1"])
        self.assertEqual(status["status"], "ok")
        self.assertFalse(status["used_cache"])
        self.assertEqual(cache["sources"]["hn"]["item_count"], 1)
        self.assertEqual(cache["sources"]["hn"]["items"][0]["id"], "hn-1")

    def test_partial_fetch_with_items_is_usable_but_degraded(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            items, status = run_source_with_cache(
                Path(tmpdir) / "source_cache.json",
                source_key="hn",
                source_label="Hacker News",
                enabled=True,
                fetcher=lambda: SourceFetchResult([make_item("hn-1")], ["one query timed out"]),
            )

        report = SourceReliabilityReport([status])
        health = report.to_source_health(raw_count=len(items), unique_count=len(items), candidate_count=1)

        self.assertEqual(status["status"], "partial")
        self.assertTrue(health["publishable"])
        self.assertEqual(health["coverage_status"], "degraded")
        self.assertEqual(health["error_count"], 1)

    def test_failed_fetch_uses_fresh_cache_as_fallback(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "source_cache.json"
            run_source_with_cache(
                cache_path,
                source_key="app_store",
                source_label="App Store",
                enabled=True,
                fetcher=lambda: SourceFetchResult([make_item("app-1", "App Store US")], []),
            )

            items, status = run_source_with_cache(
                cache_path,
                source_key="app_store",
                source_label="App Store",
                enabled=True,
                fetcher=lambda: SourceFetchResult([], ["HTTP 500"]),
            )

        self.assertEqual([item.id for item in items], ["app-1"])
        self.assertEqual(status["status"], "fallback")
        self.assertTrue(status["used_cache"])
        self.assertEqual(status["errors"], ["HTTP 500"])

    def test_disabled_source_is_skipped_without_fetching(self):
        called = False

        def fetcher():
            nonlocal called
            called = True
            return SourceFetchResult([make_item("reddit-1", "Reddit r/SaaS")], [])

        with tempfile.TemporaryDirectory() as tmpdir:
            items, status = run_source_with_cache(
                Path(tmpdir) / "source_cache.json",
                source_key="reddit",
                source_label="Reddit",
                enabled=False,
                fetcher=fetcher,
            )

        self.assertEqual(items, [])
        self.assertFalse(called)
        self.assertEqual(status["status"], "disabled")

    def test_reliability_report_blocks_when_no_usable_source_has_data(self):
        report = SourceReliabilityReport([
            {"source": "Hacker News", "status": "failed", "count": 0, "errors": ["DNS"]},
            {"source": "Reddit", "status": "disabled", "count": 0, "errors": []},
        ])

        health = report.to_source_health(raw_count=0, unique_count=0, candidate_count=0)

        self.assertFalse(health["publishable"])
        self.assertEqual(health["status"], "blocked")
        self.assertEqual(health["coverage_status"], "blocked")
        self.assertEqual(health["usable_source_count"], 0)

    def test_reliability_report_degrades_when_cache_is_used(self):
        report = SourceReliabilityReport([
            {"source": "Hacker News", "status": "ok", "count": 4, "errors": []},
            {"source": "App Store", "status": "fallback", "count": 3, "errors": ["HTTP 500"], "used_cache": True},
        ])

        health = report.to_source_health(raw_count=7, unique_count=6, candidate_count=5)

        self.assertTrue(health["publishable"])
        self.assertEqual(health["status"], "degraded")
        self.assertEqual(health["coverage_status"], "degraded")
        self.assertEqual(health["usable_source_count"], 2)
        self.assertEqual(health["cache_fallback_count"], 1)


if __name__ == "__main__":
    unittest.main()
