import tempfile
import unittest
from pathlib import Path

from docx import Document

from modules.manuscript_checker import ManuscriptChecker


def _rules():
    return {
        "_profile": {
            "name": "JIWE",
            "required_sections": ["abstract", "keywords", "introduction", "conclusion", "references"],
            "required_declarations": [
                "funding_statement",
                "author_contributions",
                "conflict_of_interests",
                "data_availability",
            ],
        },
        "margins": {"left": 1.0, "right": 1.0, "top": 1.0, "bottom": 1.0},
        "journal_header": {"font_name": "Palatino Linotype", "font_size": 24, "bold": True, "alignment": "CENTER"},
        "title": {"font_name": "Times New Roman", "font_size": 24, "alignment": "CENTER"},
        "body": {"font_name": "Times New Roman", "font_size": 10},
        "heading": {"font_name": "Times New Roman", "font_size": 10},
        "abstract": {"font_name": "Times New Roman", "font_size": 9},
        "keywords": {"font_name": "Times New Roman", "font_size": 9},
        "reference": {"font_name": "Times New Roman", "font_size": 9},
    }


class DeclarationSectionsTest(unittest.TestCase):
    def test_checker_reports_missing_required_jiwe_declarations(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "missing_declarations.docx"
            document = Document()
            for text in [
                "Journal of Informatics and",
                "Web Engineering",
                "A Test Paper Title",
                "Abstract - This is the abstract.",
                "Keywords - Testing, Rules, Sections, Format, Checker",
                "INTRODUCTION",
                "Body text.",
                "CONCLUSION",
                "Conclusion text.",
                "REFERENCES",
                "[1] Reference text.",
            ]:
                document.add_paragraph(text)
            document.save(path)
            result = ManuscriptChecker(_rules()).load_manuscript(str(path)).check_all()

        descriptions = [
            issue.description
            for issue in result.issues_by_category.get("structure", [])
        ]
        self.assertIn("Missing required declaration section: Funding Statement", descriptions)
        self.assertIn("Missing required declaration section: Author Contributions", descriptions)
        self.assertIn("Missing required declaration section: Conflict Of Interests", descriptions)
        self.assertIn("Missing required declaration section: Data Availability", descriptions)
        self.assertNotIn("Missing required declaration section: Acknowledgement", descriptions)
        self.assertNotIn("Missing required declaration section: Ethics Statements", descriptions)


if __name__ == "__main__":
    unittest.main()
