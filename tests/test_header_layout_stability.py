import tempfile
import unittest
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH

from modules.auto_fixer import AutoFixer
from modules.manuscript_checker import ManuscriptChecker


def _rules():
    return {
        "_profile": {"name": "JIWE"},
        "margins": {"left": 1.0, "right": 1.0, "top": 1.0, "bottom": 1.0},
        "journal_header": {
            "font_name": "Palatino Linotype",
            "font_size": 24,
            "bold": True,
            "alignment": "CENTER",
        },
        "title": {
            "font_name": "Times New Roman",
            "font_size": 24,
            "bold": None,
            "italic": False,
            "alignment": "CENTER",
        },
        "body": {"font_name": "Times New Roman", "font_size": 10, "line_spacing": 1.0},
        "heading": {"font_name": "Times New Roman", "font_size": 10, "bold": True},
        "references": {"font_name": "Times New Roman", "font_size": 9},
        "caption": {"font_name": "Times New Roman", "font_size": 10},
    }


def _save_unstable_docx(path: Path):
    document = Document()
    header = document.sections[0].header.paragraphs[0]
    header.text = (
        "Journal of Informatics and Web Engineering "
        "\t\t\t\t             Vol. 3 No. 3 (January 2026)"
    )

    p = document.add_paragraph("Journal of Informatics and")
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run()
    p = document.add_paragraph("\t\tWeb Engineering")
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    document.add_paragraph("Vol. 3 No. 3 (January 2026)\teISSN: 2821-370X")
    document.add_paragraph("Practicality Study of Hybrid Voice Generation Model Based on Meta-LoRA and VoxCPM")
    document.add_paragraph("Abstract - This is an abstract.")
    document.add_paragraph("Keywords - template, checking")
    document.add_paragraph("INTRODUCTION")
    document.add_paragraph("Body text.")
    document.add_paragraph("CONCLUSION")
    document.add_paragraph("Conclusion text.")
    document.add_paragraph("REFERENCES")
    document.add_paragraph("[1] Reference text.")
    document.save(path)


class HeaderLayoutStabilityTest(unittest.TestCase):
    def test_checker_flags_manual_tabs_that_can_shift_template_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "unstable.docx"
            _save_unstable_docx(path)

            checker = ManuscriptChecker(_rules()).load_manuscript(str(path))
            result = checker.check_all()
            descriptions = [
                issue.description
                for issues in result.issues_by_category.values()
                for issue in issues
            ]

        self.assertIn(
            "Journal header contains manual tab indentation that can shift layout",
            descriptions,
        )
        self.assertIn(
            "Page header uses multiple manual tabs/spaces that can wrap in Word",
            descriptions,
        )

    def test_auto_fixer_normalizes_manual_tabs_in_journal_and_page_header(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "unstable.docx"
            _save_unstable_docx(path)

            checker = ManuscriptChecker(_rules()).load_manuscript(str(path))
            result = checker.check_all()
            fixer = AutoFixer(_rules(), result.classifications, result.issues_by_category)
            fixer.load_manuscript(str(path))
            fixed_doc, changes = fixer.fix_all()

            self.assertEqual(fixed_doc.paragraphs[1].text, "Web Engineering")
            self.assertEqual(
                fixed_doc.sections[0].header.paragraphs[0].text,
                "Journal of Informatics and Web Engineering\tVol. 3 No. 3 (January 2026)",
            )
            self.assertTrue(
                any(change.property_name == "manual_tabs" for change in changes)
            )

    def test_auto_fixer_preserves_stable_single_tab_page_headers(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mixed_headers.docx"
            _save_unstable_docx(path)

            document = Document(path)
            document.sections[0].first_page_header.paragraphs[0].text = "Left\tMiddle\tRight"
            document.save(path)

            checker = ManuscriptChecker(_rules()).load_manuscript(str(path))
            result = checker.check_all()
            fixer = AutoFixer(_rules(), result.classifications, result.issues_by_category)
            fixer.load_manuscript(str(path))
            fixed_doc, changes = fixer.fix_all()

            self.assertEqual(
                fixed_doc.sections[0].header.paragraphs[0].text,
                "Journal of Informatics and Web Engineering\tVol. 3 No. 3 (January 2026)",
            )
            self.assertEqual(
                fixed_doc.sections[0].first_page_header.paragraphs[0].text,
                "Left\tMiddle\tRight",
            )
            changed_locations = [
                change.location for change in changes if change.property_name == "manual_tabs"
            ]
            self.assertNotIn("First Page Header (Section 1)", changed_locations)


if __name__ == "__main__":
    unittest.main()
