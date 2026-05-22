import unittest

from evidence_chain import build_signal_evidence_chain


def signal(**overrides):
    row = {
        "signal_id": "sig-1",
        "source_item_id": "item-1",
        "source": "Reddit r/shopify",
        "user_segment": "finance team",
        "pain_statement": "manual invoice export is slow",
        "job_to_be_done": "export weekly invoice reports",
        "workflow": "invoice export",
        "current_solution": "Excel",
        "competitor_names": ["Expensify"],
        "complaint_type": ["too expensive"],
        "frequency": "weekly",
        "payment_signal": True,
        "distribution_hint": ["reddit"],
        "confidence": 0.8,
    }
    row.update(overrides)
    return row


class EvidenceChainModuleTest(unittest.TestCase):
    def test_build_signal_evidence_chain_marks_complete_cluster(self):
        signals = [
            signal(signal_id="s1", source_item_id="a", source="Reddit r/shopify"),
            signal(signal_id="s2", source_item_id="b", source="Hacker News"),
            signal(signal_id="s3", source_item_id="c", source="Manual xiaohongshu"),
        ]

        chain = build_signal_evidence_chain(signals)

        labels = {item["label"]: item for item in chain["items"]}
        self.assertTrue(labels["7 天内重复信号"]["passed"])
        self.assertTrue(labels["独立来源"]["passed"])
        self.assertTrue(labels["明确用户群"]["passed"])
        self.assertTrue(labels["预算/付费信号"]["passed"])
        self.assertEqual(chain["status"], "strong")

    def test_build_signal_evidence_chain_surfaces_missing_gates(self):
        chain = build_signal_evidence_chain([
            signal(
                signal_id="s1",
                source_item_id="a",
                source="Reddit r/startups",
                user_segment="",
                workflow="",
                current_solution="",
                competitor_names=[],
                complaint_type=[],
                payment_signal=False,
                distribution_hint=[],
            )
        ])

        labels = {item["label"]: item for item in chain["items"]}
        self.assertFalse(labels["7 天内重复信号"]["passed"])
        self.assertFalse(labels["明确用户群"]["passed"])
        self.assertFalse(labels["明确 workflow"]["passed"])
        self.assertFalse(labels["当前解决方案"]["passed"])
        self.assertEqual(chain["status"], "weak")


if __name__ == "__main__":
    unittest.main()
