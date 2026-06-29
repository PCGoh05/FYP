import unittest

from app import build_structure_summary_items


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


if __name__ == "__main__":
    unittest.main()
