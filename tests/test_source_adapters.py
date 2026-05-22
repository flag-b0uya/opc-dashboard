import unittest

from github_issues_source import search_github_issue_containers
from reddit_source import search_reddit_containers
from youtube_source import search_youtube_containers


class SourceAdapterTest(unittest.TestCase):
    def test_youtube_search_maps_videos_to_scored_containers(self):
        def fake_fetch(_url, _headers=None):
            return {
                "items": [
                    {
                        "id": {"videoId": "vid-1"},
                        "snippet": {
                            "title": "Manual invoice workflow alternative",
                            "channelTitle": "Ops Channel",
                            "publishedAt": "2026-05-20T00:00:00Z",
                        },
                    }
                ]
            }

        containers, errors = search_youtube_containers(
            "manual invoice workflow",
            api_key="test-key",
            fetch_json=fake_fetch,
        )

        self.assertEqual(errors, [])
        self.assertEqual(containers[0]["container_id"], "youtube-vid-1")
        self.assertEqual(containers[0]["platform"], "youtube")
        self.assertEqual(containers[0]["container_type"], "video")
        self.assertTrue(containers[0]["selected_for_sampling"])

    def test_youtube_search_without_key_returns_fallback_error(self):
        containers, errors = search_youtube_containers("manual workflow", api_key="")

        self.assertEqual(containers, [])
        self.assertIn("YouTube API key missing", errors[0])

    def test_reddit_search_maps_threads_to_scored_containers(self):
        def fake_fetch(_url, _headers=None):
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

        containers, errors = search_reddit_containers("SaaS", "manual report", fetch_json=fake_fetch)

        self.assertEqual(errors, [])
        self.assertEqual(containers[0]["container_id"], "reddit-SaaS-abc")
        self.assertEqual(containers[0]["platform"], "reddit")
        self.assertEqual(containers[0]["container_type"], "thread")
        self.assertTrue(containers[0]["selected_for_sampling"])

    def test_github_issue_search_maps_issues_to_scored_containers(self):
        def fake_fetch(_url, _headers=None):
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

        containers, errors = search_github_issue_containers("manual invoice export", fetch_json=fake_fetch)

        self.assertEqual(errors, [])
        self.assertEqual(containers[0]["container_id"], "github-123")
        self.assertEqual(containers[0]["platform"], "github")
        self.assertEqual(containers[0]["container_type"], "issue")
        self.assertTrue(containers[0]["selected_for_sampling"])


if __name__ == "__main__":
    unittest.main()
