import unittest

from artifact_summaries import summarize_containers, summarize_pain_signal_rows


class ArtifactSummariesTest(unittest.TestCase):
    def test_summarize_containers_counts_selected_and_platforms(self):
        summary = summarize_containers([
            {
                "container_id": "reddit-a",
                "platform": "reddit",
                "title": "Manual workflow",
                "container_score": 72,
                "selected_for_sampling": True,
            },
            {
                "container_id": "youtube-a",
                "platform": "youtube",
                "title": "Startup advice",
                "container_score": 12,
                "selected_for_sampling": False,
            },
        ])

        self.assertEqual(summary["total_containers"], 2)
        self.assertEqual(summary["selected_for_sampling"], 1)
        self.assertEqual(summary["platform_counts"]["reddit"], 1)
        self.assertEqual(summary["top_containers"][0]["container_id"], "reddit-a")

    def test_summarize_pain_signal_rows_counts_confidence_workflow_and_payment(self):
        summary = summarize_pain_signal_rows([
            {
                "pain_signal": {
                    "confidence": 0.8,
                    "workflow": "invoice / export",
                    "payment_signal": True,
                    "distribution_hint": ["reddit"],
                }
            },
            {
                "pain_signal": {
                    "confidence": 0.2,
                    "workflow": "",
                    "payment_signal": False,
                    "distribution_hint": [],
                }
            },
        ])

        self.assertEqual(summary["total_pain_signals"], 2)
        self.assertEqual(summary["high_confidence_count"], 1)
        self.assertEqual(summary["payment_signal_count"], 1)
        self.assertEqual(summary["top_workflows"][0]["workflow"], "invoice / export")


if __name__ == "__main__":
    unittest.main()
