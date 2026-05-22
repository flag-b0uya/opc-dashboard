import tempfile
import unittest
from pathlib import Path

from comment_pipeline import (
    build_comment_pain_signals,
    load_comments_by_container,
    load_pain_signals,
    parse_args,
    save_pain_signals,
)


def comment(comment_id: str, text: str, score: int = 1, created_at: str = "2026-05-20T00:00:00") -> dict:
    return {
        "comment_id": comment_id,
        "text": text,
        "score": score,
        "created_at": created_at,
    }


class CommentPipelineTest(unittest.TestCase):
    def test_build_comment_pain_signals_samples_selected_containers_and_extracts_signals(self):
        containers = [
            {
                "container_id": "reddit-SaaS-abc",
                "platform": "reddit",
                "title": "Need alternative to manual report export workflow",
                "url": "https://reddit.example/thread",
                "selected_for_sampling": True,
            },
            {
                "container_id": "reddit-SaaS-skip",
                "platform": "reddit",
                "title": "Nice post",
                "selected_for_sampling": False,
            },
        ]
        comments_by_container = {
            "reddit-SaaS-abc": [
                comment("c1", "Our finance team manually exports invoices to Excel every week. Expensify is too expensive.", score=10),
                comment("c2", "Thanks for sharing", score=1),
            ],
            "reddit-SaaS-skip": [
                comment("x1", "Manual workflow is painful", score=99),
            ],
        }

        rows = build_comment_pain_signals(containers, comments_by_container, max_per_container=2)

        self.assertEqual([row["comment_id"] for row in rows], ["c1", "c2"])
        self.assertTrue(all(row["container_id"] == "reddit-SaaS-abc" for row in rows))
        high_signal = rows[0]["pain_signal"]
        self.assertEqual(high_signal["source_item_id"], "c1")
        self.assertTrue(high_signal["payment_signal"])
        self.assertGreater(high_signal["confidence"], rows[1]["pain_signal"]["confidence"])

    def test_save_and_load_pain_signals_handles_invalid_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "pain_signals.json"
            rows = [{"comment_id": "c1", "pain_signal": {"confidence": 0.8}}]

            save_pain_signals(rows, path)
            self.assertEqual(load_pain_signals(path), rows)

            path.write_text("{bad json", encoding="utf-8")
            self.assertEqual(load_pain_signals(path), [])

    def test_load_comments_by_container_and_parse_args(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            comments_path = Path(tmpdir) / "comments.json"
            comments_path.write_text('{"container-a": [{"comment_id": "c1"}]}', encoding="utf-8")

            comments = load_comments_by_container(comments_path)
            args = parse_args(["--comments", str(comments_path), "--max-per-container", "3"])

        self.assertEqual(comments["container-a"][0]["comment_id"], "c1")
        self.assertEqual(args.max_per_container, 3)


if __name__ == "__main__":
    unittest.main()
