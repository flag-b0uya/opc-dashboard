import json
import tempfile
import unittest
from pathlib import Path

from local_runner import (
    DEFAULT_RUNNER_APP_IDS,
    DEFAULT_RUNNER_HN_QUERIES,
    DEFAULT_RUNNER_SUBREDDITS,
    DEFAULT_SOURCE_CACHE_PATH,
    parse_args,
    resolve_scan_options,
)


class LocalRunnerConfigTest(unittest.TestCase):
    def test_defaults_without_config(self):
        args = parse_args([])

        options = resolve_scan_options(args)

        self.assertEqual(options["hn_queries"], DEFAULT_RUNNER_HN_QUERIES)
        self.assertEqual(options["subreddits"], DEFAULT_RUNNER_SUBREDDITS)
        self.assertEqual(options["subreddits"], [])
        self.assertEqual(options["reddit_query"], "alternative OR expensive OR manual OR missing feature")
        self.assertEqual(options["app_ids"], DEFAULT_RUNNER_APP_IDS)
        self.assertEqual(options["app_store_country"], "us")
        self.assertEqual(options["limit_per_source"], 10)
        self.assertEqual(options["history_max_records"], 10000)
        self.assertEqual(options["output"], "data/dashboard_snapshot.json")
        self.assertEqual(options["analysis_provider"], "heuristic")
        self.assertEqual(options["source_cache_path"], str(DEFAULT_SOURCE_CACHE_PATH))

    def test_config_file_is_used_and_cli_overrides_it(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "dashboard_config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "hn_queries": ["too expensive crm"],
                        "subreddits": ["SaaS"],
                        "reddit_query": "manual workflow",
                        "app_ids": ["123", "456"],
                        "app_store_country": "cn",
                        "limit_per_source": 7,
                        "history_max_records": 12000,
                        "output": "tmp/snapshot.json",
                        "analysis_provider": "codex",
                        "source_cache_path": "tmp/source-cache.json",
                    }
                ),
                encoding="utf-8",
            )

            args = parse_args(
                [
                    "--config",
                    str(config_path),
                    "--hn-query",
                    "override query",
                    "--limit-per-source",
                    "3",
                    "--source-cache",
                    "override/cache.json",
                ]
            )
            options = resolve_scan_options(args)

        self.assertEqual(options["hn_queries"], ["override query"])
        self.assertEqual(options["subreddits"], ["SaaS"])
        self.assertEqual(options["reddit_query"], "manual workflow")
        self.assertEqual(options["app_ids"], ["123", "456"])
        self.assertEqual(options["app_store_country"], "cn")
        self.assertEqual(options["limit_per_source"], 3)
        self.assertEqual(options["history_max_records"], 12000)
        self.assertEqual(options["output"], "tmp/snapshot.json")
        self.assertEqual(options["analysis_provider"], "codex")
        self.assertEqual(options["source_cache_path"], "override/cache.json")

    def test_empty_lists_in_config_disable_sources(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "dashboard_config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "hn_queries": [],
                        "subreddits": [],
                        "app_ids": [],
                    }
                ),
                encoding="utf-8",
            )

            args = parse_args(["--config", str(config_path)])
            options = resolve_scan_options(args)

        self.assertEqual(options["hn_queries"], [])
        self.assertEqual(options["subreddits"], [])
        self.assertEqual(options["app_ids"], [])


if __name__ == "__main__":
    unittest.main()
