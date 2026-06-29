import unittest

from app import build_structure_summary_items, format_structure_evidence


class AppStructureSummaryTest(unittest.TestCase):
    def test_builds_user_friendly_structure_summary_items(self):
        structure = {
            "sections": {
                "abstract": {"found": True},
                "keywords": {"found": False},
            },
            "expected_order": ["abstract", "keywords"],
        }

        items = build_structure_summary_items(structure)

        self.assertEqual(
            items,
            [
                {"label": "Abstract", "status": "Found"},
                {"label": "Keywords", "status": "Missing"},
            ],
        )

    def test_formats_structure_evidence_for_users(self):
        self.assertEqual(format_structure_evidence("valid"), "Clear heading")
        self.assertEqual(format_structure_evidence("weak"), "Needs review")
        self.assertEqual(format_structure_evidence("not_checked"), "Not checked")


if __name__ == "__main__":
    unittest.main()
