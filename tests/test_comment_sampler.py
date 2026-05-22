import unittest

from comment_sampler import sample_comments, sample_from_containers


def comment(comment_id: str, score: int, created_at: str, text: str) -> dict:
    return {
        "comment_id": comment_id,
        "score": score,
        "created_at": created_at,
        "text": text,
    }


class CommentSamplerTest(unittest.TestCase):
    def test_sample_comments_mixes_top_newest_and_relevant_without_duplicates(self):
        comments = [
            comment("old-top", 100, "2026-05-01T00:00:00", "Great thread"),
            comment("new-low", 1, "2026-05-20T00:00:00", "Following"),
            comment("relevant", 5, "2026-05-10T00:00:00", "Manual invoice export takes too long"),
            comment("another", 4, "2026-05-11T00:00:00", "Alternative workflow needed"),
        ]

        sampled = sample_comments(comments, max_comments=3)
        ids = [item["comment_id"] for item in sampled]

        self.assertEqual(len(sampled), 3)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertIn("old-top", ids)
        self.assertIn("new-low", ids)
        self.assertIn("relevant", ids)

    def test_sample_from_containers_only_uses_selected_containers_and_limits_each_container(self):
        containers = [
            {"container_id": "selected", "selected_for_sampling": True},
            {"container_id": "skipped", "selected_for_sampling": False},
        ]
        comments_by_container = {
            "selected": [
                comment("s1", 10, "2026-05-20T00:00:00", "manual workflow"),
                comment("s2", 8, "2026-05-19T00:00:00", "too expensive"),
                comment("s3", 1, "2026-05-18T00:00:00", "thanks"),
            ],
            "skipped": [comment("x1", 99, "2026-05-20T00:00:00", "manual workflow")],
        }

        sampled = sample_from_containers(containers, comments_by_container, max_per_container=2)

        self.assertEqual(len(sampled), 2)
        self.assertTrue(all(item["container_id"] == "selected" for item in sampled))
        self.assertNotIn("x1", [item["comment_id"] for item in sampled])


if __name__ == "__main__":
    unittest.main()
