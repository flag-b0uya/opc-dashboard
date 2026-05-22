import json
import tempfile
import unittest
from pathlib import Path

import manual_intake
from demand_engine import RawItem


class ManualIntakeTest(unittest.TestCase):
    def test_add_load_and_convert_manual_items_to_raw_items(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manual_intake.MANUAL_INTAKE_FILE = Path(tmpdir) / "manual_intake.json"

            item = manual_intake.add_manual_item(
                source="xiaohongshu",
                text="每次导出报表都要手动复制到 Excel 太麻烦了",
                url="https://example.com/post",
                note="from user group",
            )
            loaded = manual_intake.load_manual_items()
            raw_items = manual_intake.manual_items_to_raw_items(loaded)

        self.assertEqual(item["source"], "xiaohongshu")
        self.assertEqual(len(loaded), 1)
        self.assertEqual(len(raw_items), 1)
        self.assertIsInstance(raw_items[0], RawItem)
        self.assertEqual(raw_items[0].source, "Manual xiaohongshu")
        self.assertEqual(raw_items[0].source_url, "https://example.com/post")
        self.assertIn("手动复制", raw_items[0].body)
        self.assertEqual(raw_items[0].metadata["note"], "from user group")

    def test_load_manual_items_handles_missing_or_invalid_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manual_intake.MANUAL_INTAKE_FILE = Path(tmpdir) / "missing.json"
            self.assertEqual(manual_intake.load_manual_items(), [])

            manual_intake.MANUAL_INTAKE_FILE.write_text("{bad json", encoding="utf-8")
            self.assertEqual(manual_intake.load_manual_items(), [])

            manual_intake.MANUAL_INTAKE_FILE.write_text(json.dumps({"not": "a list"}), encoding="utf-8")
            self.assertEqual(manual_intake.load_manual_items(), [])

    def test_add_manual_item_dedupes_by_url_when_url_is_present(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manual_intake.MANUAL_INTAKE_FILE = Path(tmpdir) / "manual_intake.json"

            first = manual_intake.add_manual_item("xiaohongshu", "old text", url="https://example.com/post")
            second = manual_intake.add_manual_item("xiaohongshu", "new text", url="https://example.com/post")
            loaded = manual_intake.load_manual_items()

        self.assertEqual(first["id"], second["id"])
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0]["text"], "old text")

    def test_delete_manual_item_removes_item_by_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manual_intake.MANUAL_INTAKE_FILE = Path(tmpdir) / "manual_intake.json"
            item = manual_intake.add_manual_item("x", "manual workflow pain")

            deleted = manual_intake.delete_manual_item(item["id"])
            loaded = manual_intake.load_manual_items()

        self.assertTrue(deleted)
        self.assertEqual(loaded, [])


if __name__ == "__main__":
    unittest.main()
