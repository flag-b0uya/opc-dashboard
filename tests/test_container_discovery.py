import unittest

from container_discovery import rank_containers, score_container


class ContainerDiscoveryTest(unittest.TestCase):
    def test_score_container_selects_high_signal_workflow_container(self):
        container = {
            "container_id": "yt-1",
            "platform": "youtube",
            "container_type": "video",
            "title": "Shopify invoice export workflow is still manual and too expensive",
            "source_query": "manual invoice workflow alternative",
            "comment_count": 87,
            "like_count": 42,
            "view_count": 1800,
        }

        scored = score_container(container)

        self.assertGreaterEqual(scored["container_score"], 50)
        self.assertTrue(scored["selected_for_sampling"])
        self.assertEqual(scored["container_id"], "yt-1")

    def test_score_container_penalizes_marketing_noise(self):
        container = {
            "container_id": "spam-1",
            "platform": "reddit",
            "container_type": "thread",
            "title": "Subscribe to my newsletter about startup advice",
            "source_query": "startup advice newsletter",
            "comment_count": 2,
            "like_count": 1,
            "view_count": 30,
        }

        scored = score_container(container)

        self.assertLess(scored["container_score"], 35)
        self.assertFalse(scored["selected_for_sampling"])

    def test_rank_containers_orders_by_score_and_applies_limit(self):
        containers = [
            {"container_id": "low", "title": "nice post", "source_query": "startup advice", "comment_count": 1},
            {
                "container_id": "high",
                "title": "Need alternative to manual report export workflow",
                "source_query": "manual report alternative",
                "comment_count": 50,
            },
            {
                "container_id": "mid",
                "title": "Looking for support ticket automation",
                "source_query": "support workflow",
                "comment_count": 15,
            },
        ]

        ranked = rank_containers(containers, limit=2)

        self.assertEqual([item["container_id"] for item in ranked], ["high", "mid"])
        self.assertTrue(all("container_score" in item for item in ranked))


if __name__ == "__main__":
    unittest.main()
