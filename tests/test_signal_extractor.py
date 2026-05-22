import unittest

from signal_extractor import extract_pain_signal


class SignalExtractorTest(unittest.TestCase):
    def test_extract_pain_signal_structures_workflow_payment_and_competitor(self):
        item = {
            "source_item_id": "reddit-1",
            "source": "Reddit r/shopify",
            "title": "Need alternative to Expensify for invoice export",
            "text": "Our finance team manually exports Shopify invoices to Excel every week. Expensify is too expensive and missing the report workflow we need.",
            "source_url": "https://example.com/reddit-1",
        }

        signal = extract_pain_signal(item)

        self.assertEqual(signal["source_item_id"], "reddit-1")
        self.assertEqual(signal["user_segment"], "finance team")
        self.assertIn("manually exports", signal["pain_statement"])
        self.assertIn("export", signal["workflow"])
        self.assertIn("Expensify", signal["competitor_names"])
        self.assertIn("too expensive", signal["complaint_type"])
        self.assertTrue(signal["payment_signal"])
        self.assertIn("reddit", signal["distribution_hint"])
        self.assertGreater(signal["confidence"], 0.5)

    def test_extract_pain_signal_handles_generic_low_confidence_text(self):
        signal = extract_pain_signal({
            "source_item_id": "generic",
            "source": "Unknown",
            "title": "Nice post",
            "text": "Thanks for sharing this.",
        })

        self.assertEqual(signal["source_item_id"], "generic")
        self.assertFalse(signal["payment_signal"])
        self.assertLess(signal["confidence"], 0.5)


if __name__ == "__main__":
    unittest.main()
