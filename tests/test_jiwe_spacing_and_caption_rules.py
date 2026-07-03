import tempfile
import unittest
from io import BytesIO
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml.ns import qn
from docx.shared import Inches, Pt

from modules.auto_fixer import AutoFixer
from modules.manuscript_checker import ManuscriptChecker
from modules.profile_loader import ProfileLoader
from modules.utils import paragraph_has_manual_line_breaks


def _jiwe_rules():
    return ProfileLoader().default_rules(ProfileLoader().load("jiwe"))


def _add_paragraph(document, text, size=10, alignment=WD_ALIGN_PARAGRAPH.JUSTIFY, bold=False):
    paragraph = document.add_paragraph()
    paragraph.alignment = alignment
    run = paragraph.add_run(text)
    run.font.name = "Times New Roman"
    run.font.size = Pt(size)
    run.font.bold = bold
    paragraph.paragraph_format.line_spacing = 1.0
    paragraph.paragraph_format.space_after = Pt(7.5)
    return paragraph


def _add_drawing_paragraph(document):
    from docx.oxml import OxmlElement

    paragraph = document.add_paragraph()
    run = paragraph.add_run()
    run._r.append(OxmlElement("w:drawing"))
    return paragraph


def _save_spacing_issue_document(path: Path):
    document = Document()
    _add_paragraph(document, "Journal of Informatics and", 24, WD_ALIGN_PARAGRAPH.CENTER, True)
    _add_paragraph(document, "Web Engineering", 24, WD_ALIGN_PARAGRAPH.CENTER, True)
    _add_paragraph(document, "Vol. 5 No. 2 (June 2026) eISSN: 2821-370X", 10, WD_ALIGN_PARAGRAPH.CENTER)
    _add_paragraph(document, "A Test Paper Title for Spacing Validation", 24, WD_ALIGN_PARAGRAPH.CENTER)
    _add_paragraph(document, "Abstract - " + "word " * 210, 9)
    _add_paragraph(document, "Keywords - Template, Checking, Rules, References, Formatting", 9)
    _add_paragraph(document, "1. INTRODUCTION", 10, WD_ALIGN_PARAGRAPH.LEFT, True)
    body = _add_paragraph(
        document,
        "This body paragraph cites reference [1] and intentionally has wrong paragraph spacing after.",
    )
    body.paragraph_format.space_after = Pt(0)
    _add_paragraph(document, "4. CONCLUSION", 10, WD_ALIGN_PARAGRAPH.LEFT, True)
    _add_paragraph(document, "Conclusion text for the manuscript.")
    _add_paragraph(document, "5. REFERENCES", 10, WD_ALIGN_PARAGRAPH.LEFT, True)
    reference = _add_paragraph(
        document,
        '[1]\tA. Author, "Article title," Journal of Testing, vol. 1, no. 1, pp. 1-5, 2026.',
        9,
    )
    reference.paragraph_format.line_spacing = 1.0
    reference.paragraph_format.space_after = Pt(0)
    reference.paragraph_format.first_line_indent = Inches(-0.5)
    document.save(path)


class JIWESpacingAndCaptionRulesTest(unittest.TestCase):
    def test_jiwe_profile_contains_template_spacing_and_caption_case_rules(self):
        rules = _jiwe_rules()

        self.assertEqual(rules["body"]["space_after"], 7.5)
        self.assertEqual(rules["caption"]["space_after"], 7.5)
        self.assertTrue(rules["caption"]["title_case"])
        self.assertEqual(rules["reference"]["line_spacing"], 1.15)
        self.assertEqual(rules["reference"]["space_after"], 10.0)
        self.assertAlmostEqual(rules["reference"]["left_indent"], 0.4444444444444444)
        self.assertAlmostEqual(rules["reference"]["hanging_indent"], 0.4444444444444444)
        self.assertEqual(rules["heading"]["alignment"], "LEFT")
        self.assertEqual(rules["subheading"]["alignment"], "LEFT")
        self.assertTrue(rules["reference"]["number_tab_required"])

    def test_jiwe_heading_alignment_is_detected_and_fixed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "heading_alignment.docx"
            document = Document()
            _add_paragraph(document, "Journal of Informatics and", 24, WD_ALIGN_PARAGRAPH.CENTER, True)
            _add_paragraph(document, "Web Engineering", 24, WD_ALIGN_PARAGRAPH.CENTER, True)
            _add_paragraph(document, "Vol. 5 No. 2 (June 2026) eISSN: 2821-370X", 10, WD_ALIGN_PARAGRAPH.CENTER)
            _add_paragraph(document, "A Test Paper Title for Heading Alignment", 24, WD_ALIGN_PARAGRAPH.CENTER)
            _add_paragraph(document, "Abstract - " + "word " * 210, 9)
            _add_paragraph(document, "Keywords - Template, Checking, Rules, References, Formatting", 9)
            _add_paragraph(document, "1. INTRODUCTION", 10, WD_ALIGN_PARAGRAPH.CENTER, True)
            subheading = _add_paragraph(document, "1.1 Experimental Setup", 10, WD_ALIGN_PARAGRAPH.CENTER)
            for run in subheading.runs:
                run.font.italic = True
            _add_paragraph(document, "This body paragraph is correctly justified.")
            _add_paragraph(document, "4. CONCLUSION", 10, WD_ALIGN_PARAGRAPH.LEFT, True)
            _add_paragraph(document, "Conclusion text for the manuscript.")
            _add_paragraph(document, "5. REFERENCES", 10, WD_ALIGN_PARAGRAPH.LEFT, True)
            _add_paragraph(
                document,
                '[1]\tA. Author, "Article title," Journal of Testing, vol. 1, no. 1, pp. 1-5, 2026.',
                9,
            )
            document.save(path)

            rules = _jiwe_rules()
            before = ManuscriptChecker(rules).load_manuscript(str(path)).check_all()
            heading_descriptions = [
                issue.description
                for issue in before.issues_by_category.get("headings", [])
            ]

            fixer = AutoFixer(rules, before.classifications, before.issues_by_category)
            fixer.load_manuscript(str(path))
            fixer.fix_all()
            fixed = Document(BytesIO(fixer.get_fixed_document_bytes()))

        self.assertIn("Heading alignment does not match template", heading_descriptions)
        fixed_headings = {
            paragraph.text: paragraph.alignment
            for paragraph in fixed.paragraphs
            if paragraph.text in {"1. INTRODUCTION", "1.1 Experimental Setup"}
        }
        self.assertEqual(fixed_headings["1. INTRODUCTION"], WD_ALIGN_PARAGRAPH.LEFT)
        self.assertEqual(fixed_headings["1.1 Experimental Setup"], WD_ALIGN_PARAGRAPH.LEFT)

    def test_jiwe_declaration_left_content_is_not_body_alignment_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "declaration_alignment.docx"
            document = Document()
            _add_paragraph(document, "Journal of Informatics and", 24, WD_ALIGN_PARAGRAPH.CENTER, True)
            _add_paragraph(document, "Web Engineering", 24, WD_ALIGN_PARAGRAPH.CENTER, True)
            _add_paragraph(document, "Vol. 5 No. 2 (June 2026) eISSN: 2821-370X", 10, WD_ALIGN_PARAGRAPH.CENTER)
            _add_paragraph(document, "A Test Paper Title for Declaration Alignment", 24, WD_ALIGN_PARAGRAPH.CENTER)
            _add_paragraph(document, "Abstract - " + "word " * 210, 9)
            _add_paragraph(document, "Keywords - Template, Checking, Rules, References, Formatting", 9)
            _add_paragraph(document, "1. INTRODUCTION", 10, WD_ALIGN_PARAGRAPH.LEFT, True)
            _add_paragraph(document, "This body paragraph is correctly justified.", 10, WD_ALIGN_PARAGRAPH.JUSTIFY)
            _add_paragraph(document, "4. CONCLUSION", 10, WD_ALIGN_PARAGRAPH.LEFT, True)
            _add_paragraph(document, "Conclusion text for the manuscript.", 10, WD_ALIGN_PARAGRAPH.JUSTIFY)
            _add_paragraph(document, "FUNDING STATEMENT", 10, WD_ALIGN_PARAGRAPH.LEFT, True)
            _add_paragraph(
                document,
                "The authors received no funding from any party for the research and publication of this article.",
                10,
                WD_ALIGN_PARAGRAPH.LEFT,
            )
            _add_paragraph(document, "CONFLICT OF INTERESTS", 10, WD_ALIGN_PARAGRAPH.LEFT, True)
            _add_paragraph(document, "No conflict of interests were disclosed.", 10, WD_ALIGN_PARAGRAPH.JUSTIFY)
            _add_paragraph(document, "5. REFERENCES", 10, WD_ALIGN_PARAGRAPH.LEFT, True)
            _add_paragraph(
                document,
                '[1]\tA. Author, "Article title," Journal of Testing, vol. 1, no. 1, pp. 1-5, 2026.',
                9,
            )
            document.save(path)

            result = ManuscriptChecker(_jiwe_rules()).load_manuscript(str(path)).check_all()

        body_descriptions = [
            issue.description
            for issue in result.issues_by_category.get("body_text", [])
        ]
        self.assertNotIn("Body text alignment does not match template", body_descriptions)

    def test_jiwe_inline_font_instruction_does_not_break_heading_capitalization(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "heading_instruction.docx"
            document = Document()
            _add_paragraph(document, "Journal of Informatics and", 24, WD_ALIGN_PARAGRAPH.CENTER, True)
            _add_paragraph(document, "Web Engineering", 24, WD_ALIGN_PARAGRAPH.CENTER, True)
            _add_paragraph(document, "Vol. 5 No. 2 (June 2026) eISSN: 2821-370X", 10, WD_ALIGN_PARAGRAPH.CENTER)
            _add_paragraph(document, "A Test Paper Title for Heading Instruction", 24, WD_ALIGN_PARAGRAPH.CENTER)
            _add_paragraph(document, "Abstract - " + "word " * 210, 9)
            _add_paragraph(document, "Keywords - Template, Checking, Rules, References, Formatting", 9)
            _add_paragraph(document, "INTRODUCTION (10-Font size, Times New Roman)", 10, WD_ALIGN_PARAGRAPH.LEFT, True)
            _add_paragraph(document, "This body paragraph is correctly justified.", 10, WD_ALIGN_PARAGRAPH.JUSTIFY)
            _add_paragraph(document, "CONCLUSION (10-Font size, Times New Roman)", 10, WD_ALIGN_PARAGRAPH.LEFT, True)
            _add_paragraph(document, "Conclusion text for the manuscript.", 10, WD_ALIGN_PARAGRAPH.JUSTIFY)
            _add_paragraph(document, "REFERENCES", 10, WD_ALIGN_PARAGRAPH.LEFT, True)
            _add_paragraph(
                document,
                '[1]\tA. Author, "Article title," Journal of Testing, vol. 1, no. 1, pp. 1-5, 2026.',
                9,
            )
            document.save(path)

            result = ManuscriptChecker(_jiwe_rules()).load_manuscript(str(path)).check_all()

        heading_descriptions = [
            issue.description
            for issue in result.issues_by_category.get("headings", [])
        ]
        self.assertNotIn("Heading capitalization does not match template", heading_descriptions)

    def test_checker_reports_body_spacing_and_reference_indent_mismatches(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "spacing_issues.docx"
            _save_spacing_issue_document(path)

            result = ManuscriptChecker(_jiwe_rules()).load_manuscript(str(path)).check_all()

        body_descriptions = [
            issue.description
            for issue in result.issues_by_category.get("body_text", [])
        ]
        reference_descriptions = [
            issue.description
            for issue in result.issues_by_category.get("references", [])
        ]

        self.assertIn("Body paragraph spacing after does not match template", body_descriptions)
        self.assertIn("Reference paragraph spacing after does not match template", reference_descriptions)
        self.assertIn("Reference hanging indent does not match template", reference_descriptions)

    def test_auto_fix_applies_body_spacing_and_reference_indent(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "spacing_fix.docx"
            _save_spacing_issue_document(path)

            result = ManuscriptChecker(_jiwe_rules()).load_manuscript(str(path)).check_all()
            fixer = AutoFixer(_jiwe_rules(), result.classifications, result.issues_by_category)
            fixer.load_manuscript(str(path))
            fixer.fix_all()
            fixed = Document(BytesIO(fixer.get_fixed_document_bytes()))

        body = fixed.paragraphs[7]
        reference = fixed.paragraphs[11]
        self.assertAlmostEqual(body.paragraph_format.space_after.pt, 7.5)
        self.assertAlmostEqual(reference.paragraph_format.line_spacing, 1.15)
        self.assertAlmostEqual(reference.paragraph_format.space_after.pt, 10.0)
        self.assertAlmostEqual(abs(reference.paragraph_format.first_line_indent.inches), 0.44, places=2)
        self.assertEqual(reference._p.pPr.ind.get(qn("w:hanging")), "640")

    def test_auto_fix_replaces_body_manual_line_breaks_before_justifying(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manual_line_breaks.docx"
            _save_spacing_issue_document(path)
            document = Document(path)
            body = document.paragraphs[7]
            body.clear()
            run = body.add_run("This sentence should wrap naturally,")
            run.add_break(WD_BREAK.LINE)
            body.add_run("not be forced onto a stretched justified line.")
            body.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            document.save(path)

            result = ManuscriptChecker(_jiwe_rules()).load_manuscript(str(path)).check_all()
            descriptions = [
                issue.description
                for issue in result.issues_by_category.get("body_text", [])
            ]
            self.assertIn(
                "Body paragraph contains manual line breaks that can stretch justified text",
                descriptions,
            )

            fixer = AutoFixer(_jiwe_rules(), result.classifications, result.issues_by_category)
            fixer.load_manuscript(str(path))
            fixer.fix_all()
            fixed = Document(BytesIO(fixer.get_fixed_document_bytes()))

        self.assertFalse(paragraph_has_manual_line_breaks(fixed.paragraphs[7]))
        self.assertIn("naturally, not be forced", fixed.paragraphs[7].text)

    def test_auto_fix_normalizes_reference_block_indent(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "reference_left_indent_fix.docx"
            _save_spacing_issue_document(path)
            document = Document(path)
            reference = document.paragraphs[11]
            reference.paragraph_format.left_indent = Inches(0.89)
            reference.paragraph_format.first_line_indent = Inches(-0.44)
            document.save(path)

            result = ManuscriptChecker(_jiwe_rules()).load_manuscript(str(path)).check_all()
            descriptions = [
                issue.description
                for issue in result.issues_by_category.get("references", [])
            ]
            self.assertIn("Reference left indent does not match template", descriptions)

            fixer = AutoFixer(_jiwe_rules(), result.classifications, result.issues_by_category)
            fixer.load_manuscript(str(path))
            fixer.fix_all()
            fixed = Document(BytesIO(fixer.get_fixed_document_bytes()))

        fixed_reference = fixed.paragraphs[11]
        self.assertAlmostEqual(fixed_reference.paragraph_format.left_indent.inches, 0.44, places=2)
        indentation = fixed_reference._p.pPr.ind
        self.assertEqual(indentation.get(qn("w:left")), "640")
        self.assertAlmostEqual(abs(fixed_reference.paragraph_format.first_line_indent.inches), 0.44, places=2)

    def test_checker_reports_reference_number_space_instead_of_tab(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "reference_number_tab.docx"
            _save_spacing_issue_document(path)
            document = Document(path)
            reference = document.paragraphs[11]
            reference.runs[0].text = reference.runs[0].text.replace("[1]\t", "[1] ", 1)
            document.save(path)

            result = ManuscriptChecker(_jiwe_rules()).load_manuscript(str(path)).check_all()

        descriptions = [
            issue.description
            for issue in result.issues_by_category.get("references", [])
        ]
        self.assertIn("Reference number should be followed by a tab", descriptions)

    def test_auto_fix_replaces_reference_number_spaces_with_tab(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "reference_number_tab_fix.docx"
            _save_spacing_issue_document(path)
            document = Document(path)
            reference = document.paragraphs[11]
            reference.runs[0].text = reference.runs[0].text.replace("[1]\t", "[1] ", 1)
            document.save(path)

            result = ManuscriptChecker(_jiwe_rules()).load_manuscript(str(path)).check_all()
            fixer = AutoFixer(_jiwe_rules(), result.classifications, result.issues_by_category)
            fixer.load_manuscript(str(path))
            fixer.fix_all()
            fixed = Document(BytesIO(fixer.get_fixed_document_bytes()))

        self.assertTrue(fixed.paragraphs[11].text.startswith("[1]\t"))

    def test_auto_fix_collapses_duplicate_tabs_after_reference_number(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "reference_number_duplicate_tab_fix.docx"
            _save_spacing_issue_document(path)
            document = Document(path)
            reference = document.paragraphs[11]
            reference.runs[0].text = "[1]\t"
            reference.add_run("\t")
            reference.add_run('A. Author, "Article title," Journal of Testing, 2026.')
            document.save(path)

            result = ManuscriptChecker(_jiwe_rules()).load_manuscript(str(path)).check_all()
            descriptions = [
                issue.description
                for issue in result.issues_by_category.get("references", [])
            ]
            fixer = AutoFixer(_jiwe_rules(), result.classifications, result.issues_by_category)
            fixer.load_manuscript(str(path))
            fixer.fix_all()
            fixed = Document(BytesIO(fixer.get_fixed_document_bytes()))

        self.assertIn("Reference number should be followed by a tab", descriptions)
        self.assertTrue(fixed.paragraphs[11].text.startswith("[1]\t"))
        self.assertFalse(fixed.paragraphs[11].text.startswith("[1]\t\t"))

    def test_checker_reports_caption_title_case_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "caption_case.docx"
            document = Document()
            _add_drawing_paragraph(document)
            caption = _add_paragraph(
                document,
                "Figure 3. top 20 features ranked by their chi-squared scores with the target variable",
            )
            caption.alignment = WD_ALIGN_PARAGRAPH.CENTER
            document.save(path)

            result = ManuscriptChecker(_jiwe_rules()).load_manuscript(str(path)).check_all()

        descriptions = [
            issue.description
            for issue in result.issues_by_category.get("figures", [])
        ]
        self.assertIn("Figure caption capitalization does not match template", descriptions)

    def test_auto_fix_applies_caption_title_case(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "caption_case_fix.docx"
            document = Document()
            _add_drawing_paragraph(document)
            _add_paragraph(
                document,
                "Figure 3. top 20 features ranked by their chi-squared scores with the target variable",
            )
            document.save(path)

            result = ManuscriptChecker(_jiwe_rules()).load_manuscript(str(path)).check_all()
            fixer = AutoFixer(_jiwe_rules(), result.classifications, result.issues_by_category)
            fixer.load_manuscript(str(path))
            fixer.fix_all()
            fixed = Document(BytesIO(fixer.get_fixed_document_bytes()))

        self.assertEqual(
            fixed.paragraphs[1].text,
            "Figure 3. Top 20 Features Ranked by Their Chi-Squared Scores with the Target Variable",
        )

    def test_caption_title_case_preserves_acronyms(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "caption_acronyms.docx"
            document = Document()
            _add_drawing_paragraph(document)
            _add_paragraph(
                document,
                "Figure 1. AI-Based OWASP WCSS rPPG and ROI Results",
            )
            document.save(path)

            result = ManuscriptChecker(_jiwe_rules()).load_manuscript(str(path)).check_all()
            fixer = AutoFixer(_jiwe_rules(), result.classifications, result.issues_by_category)
            fixer.load_manuscript(str(path))
            fixer.fix_all()
            fixed = Document(BytesIO(fixer.get_fixed_document_bytes()))

        self.assertEqual(
            fixed.paragraphs[1].text,
            "Figure 1. AI-Based OWASP WCSS rPPG and ROI Results",
        )

    def test_caption_title_case_preserves_numeric_expressions_and_vs(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "caption_numeric_expression.docx"
            document = Document()
            _add_drawing_paragraph(document)
            _add_paragraph(
                document,
                "Figure 1. Visualization of the 36x36 ROI preprocessing pipeline vs. baseline",
            )
            document.save(path)

            result = ManuscriptChecker(_jiwe_rules()).load_manuscript(str(path)).check_all()
            fixer = AutoFixer(_jiwe_rules(), result.classifications, result.issues_by_category)
            fixer.load_manuscript(str(path))
            fixer.fix_all()
            fixed = Document(BytesIO(fixer.get_fixed_document_bytes()))

        self.assertEqual(
            fixed.paragraphs[1].text,
            "Figure 1. Visualization of the 36x36 ROI Preprocessing Pipeline vs. Baseline",
        )


if __name__ == "__main__":
    unittest.main()
