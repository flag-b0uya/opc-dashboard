import tempfile
import unittest
from pathlib import Path

from container_pipeline import collect_containers, load_containers, parse_args, save_containers


class ContainerPipelineTest(unittest.TestCase):
    def test_collect_containers_runs_enabled_sources_and_merges_errors(self):
        def fake_fetch(url, _headers=None):
            if "youtube" in url:
                return {
                    "items": [
                        {
                            "id": {"videoId": "vid-1"},
                            "snippet": {
                                "title": "Manual invoice workflow alternative",
                                "channelTitle": "Ops",
                                "publishedAt": "2026-05-20T00:00:00Z",
                            },
                        }
                    ]
                }
            if "reddit" in url:
                return {
                    "data": {
                        "children": [
                            {
                                "data": {
                                    "id": "abc",
                                    "title": "Need alternative to manual report export workflow",
                                    "author": "user1",
                                    "created_utc": 1779300000,
                                    "permalink": "/r/SaaS/comments/abc/test/",
                                    "num_comments": 48,
                                    "score": 31,
                                }
                            }
                        ]
                    }
                }
            if "github" in url:
                return {
                    "items": [
                        {
                            "id": 123,
                            "number": 42,
                            "title": "Missing export workflow for manual invoices",
                            "html_url": "https://github.com/acme/repo/issues/42",
                            "user": {"login": "octo"},
                            "created_at": "2026-05-19T00:00:00Z",
                            "comments": 12,
                            "repository_url": "https://api.github.com/repos/acme/repo",
                        }
                    ]
                }
            raise AssertionError(url)

        containers, errors = collect_containers(
            youtube_queries=["manual invoice workflow"],
            reddit_targets=[{"subreddit": "SaaS", "query": "manual report"}],
            github_queries=["manual invoice export"],
            youtube_api_key="test-key",
            fetch_json=fake_fetch,
        )

        self.assertEqual(errors, [])
        self.assertEqual({item["platform"] for item in containers}, {"youtube", "reddit", "github"})
        self.assertEqual(containers[0]["container_score"], max(item["container_score"] for item in containers))

    def test_collect_containers_can_skip_youtube_without_key(self):
        containers, errors = collect_containers(
            youtube_queries=["manual workflow"],
            reddit_targets=[],
            github_queries=[],
            youtube_api_key="",
        )

        self.assertEqual(containers, [])
        self.assertIn("YouTube API key missing", errors[0])

    def test_save_and_load_containers_handles_invalid_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "containers.json"
            rows = [{"container_id": "c1", "container_score": 42}]

            save_containers(rows, path)
            self.assertEqual(load_containers(path), rows)

            path.write_text("{bad json", encoding="utf-8")
            self.assertEqual(load_containers(path), [])

    def test_parse_args_supports_cli_sources(self):
        args = parse_args([
            "--youtube-query",
            "manual workflow",
            "--reddit",
            "SaaS:manual report",
            "--github-query",
            "missing export",
            "--limit",
            "3",
        ])

        self.assertEqual(args.youtube_query, ["manual workflow"])
        self.assertEqual(args.reddit, ["SaaS:manual report"])
        self.assertEqual(args.github_query, ["missing export"])
        self.assertEqual(args.limit, 3)


if __name__ == "__main__":
    unittest.main()
