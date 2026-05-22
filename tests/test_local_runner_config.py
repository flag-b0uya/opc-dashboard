import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from demand_engine import RawItem
from local_runner import (
    DEFAULT_RUNNER_APP_IDS,
    DEFAULT_RUNNER_HN_QUERIES,
    DEFAULT_RUNNER_SUBREDDITS,
    DEFAULT_SOURCE_CACHE_PATH,
    main,
    parse_args,
    resolve_scan_options,
)
from source_reliability import SourceReliabilityReport


def _raw_item(source: str = "Manual xiaohongshu") -> RawItem:
    return RawItem(
        id="raw-1",
        source=source,
        title="手动导出报表太麻烦",
        body="手动导出报表太麻烦，而且每周都要重复做。",
        source_url="https://example.com/source",
        published_at="2026-05-22T00:00:00",
        metadata={},
    )


def _report(status: str = "ok", count: int = 1, errors=None) -> SourceReliabilityReport:
    return SourceReliabilityReport([
        {
            "source": "Manual intake",
            "status": status,
            "count": count,
            "errors": list(errors or []),
            "used_cache": False,
            "cache_age_hours": None,
        }
    ])


class LocalRunnerConfigTest(unittest.TestCase):
    def test_defaults_without_config(self):
        args = parse_args([])

        options = resolve_scan_options(args)

        self.assertEqual(options["hn_queries"], DEFAULT_RUNNER_HN_QUERIES)
        self.assertEqual(options["subreddits"], DEFAULT_RUNNER_SUBREDDITS)
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

    def test_main_enriches_clusters_with_funnel_fields_before_snapshot(self):
        raw = _raw_item("Manual xiaohongshu")
        cluster = {
            "cluster_id": "cluster-reporting",
            "title": "报表与数据导出工作流",
            "category": "运营/内部流程",
            "decision_score": 70,
            "decision_verdict": "Monitor",
            "source_count": 2,
            "count_7d": 3,
            "top_score": 76,
            "evidence_chain": {"passed_count": 4, "total_count": 5},
            "sample_ideas": [{"pain_summary": "Manual export is too expensive.", "source": "Manual xiaohongshu"}],
        }
        captured = {}

        def fake_snapshot(**kwargs):
            captured.update(kwargs)
            return {"summary": {}}

        with patch("local_runner.fetch_items_with_reliability", return_value=([raw], _report())), \
            patch("local_runner.score_items", return_value=([raw], [(raw, ["manual"])], [])), \
            patch("local_runner.save_scan_to_history", return_value=0), \
            patch("local_runner.format_markdown_report", return_value="report"), \
            patch("local_runner.ideas_to_dicts", return_value=[]), \
            patch("local_runner.get_history_summary", return_value={"records": []}), \
            patch("local_runner.build_opportunity_clusters", return_value=[cluster]), \
            patch("local_runner.build_dashboard_snapshot", side_effect=fake_snapshot), \
            patch("local_runner.save_source_metrics"), \
            patch("local_runner.append_source_metrics_history"), \
            patch("local_runner.write_dashboard_snapshot"), \
            contextlib.redirect_stdout(io.StringIO()):
            exit_code = main(["--analysis-provider", "heuristic", "--output", "data/test_snapshot.json"])

        self.assertEqual(exit_code, 0)
        enriched = captured["opportunity_clusters"][0]
        self.assertIn("funnel_score", enriched)
        self.assertIn("funnel_verdict", enriched)
        self.assertIn("funnel_next_step", enriched)

    def test_main_passes_manual_intake_items_and_snapshot_source_metrics(self):
        raw = _raw_item("Manual xiaohongshu")
        captured = {}

        def fake_fetch(options, extra_items=None):
            captured["extra_items"] = extra_items
            return [raw], _report()

        def fake_snapshot(**kwargs):
            captured.update(kwargs)
            return {"summary": {}}

        with patch("local_runner.load_manual_items", return_value=[{"id": "m1", "source": "xiaohongshu", "text": "手动导出报表太麻烦"}]), \
            patch("local_runner.manual_items_to_raw_items", return_value=["manual-raw"]), \
            patch("local_runner.fetch_items_with_reliability", side_effect=fake_fetch), \
            patch("local_runner.score_items", return_value=([raw], [(raw, ["manual"])], [])), \
            patch("local_runner.save_scan_to_history", return_value=0), \
            patch("local_runner.format_markdown_report", return_value="report"), \
            patch("local_runner.ideas_to_dicts", return_value=[]), \
            patch("local_runner.get_history_summary", return_value={"records": []}), \
            patch("local_runner.build_opportunity_clusters", return_value=[]), \
            patch("local_runner.build_dashboard_snapshot", side_effect=fake_snapshot), \
            patch("local_runner.write_dashboard_snapshot"), \
            patch("local_runner.save_source_metrics"), \
            patch("local_runner.append_source_metrics_history") as append_history, \
            contextlib.redirect_stdout(io.StringIO()):
            exit_code = main(["--analysis-provider", "heuristic", "--output", "data/test_snapshot.json"])

        self.assertEqual(exit_code, 0)
        self.assertEqual(captured["extra_items"], ["manual-raw"])
        self.assertEqual(captured["source_metrics"][0]["source"], "Manual xiaohongshu")
        self.assertEqual(captured["source_metrics"][0]["candidate_rate"], 1.0)
        self.assertNotIn("container_summary", captured)
        self.assertNotIn("pain_signal_summary", captured)
        append_history.assert_called_once()

    def test_main_preserves_existing_snapshot_when_scan_has_only_source_errors(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "dashboard_snapshot.json"
            output_path.write_text('{"kept": true}', encoding="utf-8")

            with patch("local_runner.fetch_items_with_reliability", return_value=([], _report("failed", 0, ["HN failed", "Reddit failed"]))), \
                patch("local_runner.score_items", return_value=([], [], [])), \
                patch("local_runner.save_scan_to_history", return_value=0) as save_scan_to_history, \
                patch("local_runner.format_markdown_report", return_value="report"), \
                patch("local_runner.ideas_to_dicts", return_value=[]), \
                patch("local_runner.get_history_summary", return_value={"records": []}), \
                patch("local_runner.build_opportunity_clusters", return_value=[]), \
                patch("local_runner.save_source_metrics") as save_source_metrics, \
                patch("local_runner.append_source_metrics_history") as append_history, \
                contextlib.redirect_stdout(io.StringIO()):
                exit_code = main([
                    "--analysis-provider",
                    "heuristic",
                    "--output",
                    str(output_path),
                ])

            failed_path = output_path.parent / "failed_snapshot.json"
            self.assertEqual(exit_code, 0)
            self.assertEqual(output_path.read_text(encoding="utf-8"), '{"kept": true}')
            self.assertTrue(failed_path.exists())
            self.assertIn("HN failed", failed_path.read_text(encoding="utf-8"))
            save_scan_to_history.assert_not_called()
            save_source_metrics.assert_not_called()
            append_history.assert_not_called()

    def test_main_does_not_create_official_snapshot_when_first_scan_only_has_source_errors(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "dashboard_snapshot.json"

            with patch("local_runner.fetch_items_with_reliability", return_value=([], _report("failed", 0, ["HN failed", "Reddit failed"]))), \
                patch("local_runner.score_items", return_value=([], [], [])), \
                patch("local_runner.save_scan_to_history", return_value=0) as save_scan_to_history, \
                patch("local_runner.format_markdown_report", return_value="report"), \
                patch("local_runner.ideas_to_dicts", return_value=[]), \
                patch("local_runner.get_history_summary", return_value={"records": []}), \
                patch("local_runner.build_opportunity_clusters", return_value=[]), \
                patch("local_runner.save_source_metrics") as save_source_metrics, \
                patch("local_runner.append_source_metrics_history") as append_history, \
                contextlib.redirect_stdout(io.StringIO()):
                exit_code = main([
                    "--analysis-provider",
                    "heuristic",
                    "--output",
                    str(output_path),
                ])

            failed_path = output_path.parent / "failed_snapshot.json"
            self.assertEqual(exit_code, 1)
            self.assertFalse(output_path.exists())
            self.assertTrue(failed_path.exists())
            self.assertIn("HN failed", failed_path.read_text(encoding="utf-8"))
            save_scan_to_history.assert_not_called()
            save_source_metrics.assert_not_called()
            append_history.assert_not_called()


if __name__ == "__main__":
    unittest.main()
