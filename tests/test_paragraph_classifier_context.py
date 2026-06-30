import unittest

from modules.paragraph_classifier import ParagraphClassifier, ParagraphType


def _paragraph(index, text, font_size=10, bold=False, alignment="LEFT"):
    return {
        "index": index,
        "text": text,
        "font_info": {
            "font_name": "Times New Roman",
            "font_size": font_size,
            "bold": bold,
            "italic": False,
        },
        "alignment": alignment,
    }


class ParagraphClassifierContextTest(unittest.TestCase):
    def test_keywords_context_stops_after_keywords_content(self):
        classifier = ParagraphClassifier()
        classifications = classifier._rule_classify_all([
            _paragraph(0, "Journal of Informatics and", font_size=24, bold=True, alignment="CENTER"),
            _paragraph(1, "Web Engineering", font_size=24, bold=True, alignment="CENTER"),
            _paragraph(2, "A Test Paper Title for Classification", font_size=24, alignment="CENTER"),
            _paragraph(3, "Abstract - This is the abstract.", font_size=9),
            _paragraph(4, "Keywords - checking, template", font_size=9),
            _paragraph(5, "INTRODUCTION 1.1 Background", font_size=10, bold=True),
            _paragraph(6, "This paragraph is body text after the introduction.", font_size=10),
        ])

        self.assertEqual(classifications[4].paragraph_type, ParagraphType.KEYWORDS_CONTENT)
        self.assertNotEqual(classifications[5].paragraph_type, ParagraphType.KEYWORDS_CONTENT)
        self.assertNotEqual(classifications[6].paragraph_type, ParagraphType.KEYWORDS_CONTENT)

    def test_numbered_short_subheading_is_not_classified_as_body(self):
        classifier = ParagraphClassifier()
        classifications = classifier._rule_classify_all([
            _paragraph(0, "Journal of Informatics and", font_size=24, bold=True, alignment="CENTER"),
            _paragraph(1, "Web Engineering", font_size=24, bold=True, alignment="CENTER"),
            _paragraph(2, "A Test Paper Title for Classification", font_size=24, alignment="CENTER"),
            _paragraph(3, "Abstract - This is the abstract.", font_size=9),
            _paragraph(4, "Keywords - checking, template", font_size=9),
            _paragraph(5, "INTRODUCTION", font_size=10, bold=True),
            _paragraph(6, "1.2 Motivation and Problem Statement", font_size=10, bold=True),
            _paragraph(7, "This paragraph is body text after the numbered subheading.", font_size=10),
        ])

        self.assertEqual(classifications[6].paragraph_type, ParagraphType.SECTION_HEADING)
        self.assertEqual(classifications[7].paragraph_type, ParagraphType.BODY)

    def test_custom_all_caps_section_heading_is_not_classified_as_body(self):
        classifier = ParagraphClassifier()
        classifications = classifier._rule_classify_all([
            _paragraph(0, "Journal of Informatics and", font_size=24, bold=True, alignment="CENTER"),
            _paragraph(1, "Web Engineering", font_size=24, bold=True, alignment="CENTER"),
            _paragraph(2, "A Test Paper Title for Classification", font_size=24, alignment="CENTER"),
            _paragraph(3, "Abstract - This is the abstract.", font_size=9),
            _paragraph(4, "Keywords - checking, template", font_size=9),
            _paragraph(5, "INTRODUCTION", font_size=10, bold=True),
            _paragraph(6, "This paragraph is body text before a custom section heading.", font_size=10),
            _paragraph(7, "DOMAIN-SPECIFIC SYNTHETIC DATASET EXAMPLES", font_size=10, bold=True),
            _paragraph(8, "This paragraph is body text after the custom heading.", font_size=10),
        ])

        self.assertEqual(classifications[7].paragraph_type, ParagraphType.SECTION_HEADING)
        self.assertEqual(classifications[8].paragraph_type, ParagraphType.BODY)

    def test_abstract_content_is_not_misclassified_as_journal_header(self):
        classifier = ParagraphClassifier()
        classifications = classifier._rule_classify_all([
            _paragraph(0, "Journal of Informatics and", font_size=24, bold=True, alignment="CENTER"),
            _paragraph(1, "Web Engineering", font_size=24, bold=True, alignment="CENTER"),
            _paragraph(2, "Vol. 5 No. 1 (February 2026)", font_size=10, alignment="CENTER"),
            _paragraph(3, "A Test Paper Title for Classification", font_size=24, alignment="CENTER"),
            _paragraph(4, "Author One, Author Two", font_size=11, bold=True, alignment="CENTER"),
            _paragraph(5, "Department of Computer Science, Example University", font_size=9, alignment="CENTER"),
            _paragraph(6, "corresponding author: author@example.edu", font_size=9, alignment="CENTER"),
            _paragraph(7, "Abstract - This paper studies formatting issues in the Journal of Testing.", font_size=9),
            _paragraph(8, "Keywords - checking, template", font_size=9),
        ])

        self.assertEqual(classifications[7].paragraph_type, ParagraphType.ABSTRACT_CONTENT)
        self.assertEqual(classifications[8].paragraph_type, ParagraphType.KEYWORDS_CONTENT)


if __name__ == "__main__":
    unittest.main()
