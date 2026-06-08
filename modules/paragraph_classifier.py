"""
Paragraph classification module.

The checker uses deterministic rules as the primary classifier because
format validation and auto-fixing must be stable and explainable. LLM support
is intentionally kept out of the core classification path.
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List

from .utils import get_paragraph_alignment, get_paragraph_font_info, get_paragraph_text


class ParagraphType(Enum):
    """Paragraph type labels used by the checker and auto-fixer."""

    EMPTY = "empty"
    JOURNAL_HEADER = "journal_header"
    AUTHOR_INFO = "author_info"
    ABSTRACT_LABEL = "abstract_label"
    KEYWORDS_LABEL = "keywords_label"
    PAPER_TITLE = "paper_title"
    SECTION_HEADING = "section_heading"
    BODY = "body"
    ABSTRACT_CONTENT = "abstract_content"
    KEYWORDS_CONTENT = "keywords_content"
    CAPTION = "caption"
    REFERENCE = "reference"
    TABLE = "table"
    FIGURE = "figure"
    ALGORITHM = "algorithm"
    CODE_BLOCK = "code_block"
    EQUATION = "equation"
    TEMPLATE_INSTRUCTION = "template_instruction"
    UNKNOWN = "unknown"


@dataclass
class ClassifiedParagraph:
    """A paragraph classification with formatting metadata."""

    index: int
    text: str
    paragraph_type: ParagraphType
    confidence: float
    font_info: Dict[str, Any]
    alignment: str
    should_fix: bool
    classification_reason: str


class ParagraphClassifier:
    """
    Rule-first paragraph classifier.

    LLM classification is not used in the main path. The goal is to prevent
    repeated runs from producing different correction targets.
    """

    SKIP_TYPES = {
        ParagraphType.EMPTY,
        ParagraphType.AUTHOR_INFO,
        ParagraphType.ABSTRACT_LABEL,
        ParagraphType.KEYWORDS_LABEL,
        ParagraphType.ALGORITHM,
        ParagraphType.CODE_BLOCK,
        ParagraphType.EQUATION,
        ParagraphType.TEMPLATE_INSTRUCTION,
    }

    FIX_TYPES = {
        ParagraphType.PAPER_TITLE,
        ParagraphType.JOURNAL_HEADER,
        ParagraphType.SECTION_HEADING,
        ParagraphType.BODY,
        ParagraphType.ABSTRACT_CONTENT,
        ParagraphType.KEYWORDS_CONTENT,
        ParagraphType.CAPTION,
        ParagraphType.REFERENCE,
    }

    def __init__(self, llm_integration=None):
        self.llm = llm_integration
        self.classifications: List[ClassifiedParagraph] = []

    def classify_document(self, document) -> List[ClassifiedParagraph]:
        """Classify all paragraphs in a document."""
        para_data = []
        for index, paragraph in enumerate(document.paragraphs):
            para_data.append(
                {
                    "index": index,
                    "text": get_paragraph_text(paragraph),
                    "font_info": get_paragraph_font_info(paragraph),
                    "alignment": get_paragraph_alignment(paragraph),
                }
            )

        self.classifications = self._rule_classify_all(para_data)
        return self.classifications

    def _rule_classify_all(self, para_data: List[Dict]) -> List[ClassifiedParagraph]:
        """Classify every paragraph with deterministic rules."""
        classifications = []
        context = {
            "found_title": False,
            "in_abstract": False,
            "in_keywords": False,
            "in_references": False,
        }

        for data in para_data:
            classification = self._rule_classify_single(data, context)
            classifications.append(classification)
            self._update_context(context, classification)

        return classifications

    def _fallback_classify_all(self, para_data: List[Dict]) -> List[ClassifiedParagraph]:
        """Backward-compatible alias for older code."""
        return self._rule_classify_all(para_data)

    def _fallback_classify_single(self, data: Dict, context: Dict = None) -> ClassifiedParagraph:
        """Backward-compatible alias for older code."""
        return self._rule_classify_single(data, context)

    def _update_context(self, context: Dict, classification: ClassifiedParagraph) -> None:
        """Update section context after each paragraph."""
        paragraph_type = classification.paragraph_type
        text_lower = classification.text.lower()

        if paragraph_type == ParagraphType.PAPER_TITLE:
            context["found_title"] = True

        if paragraph_type == ParagraphType.ABSTRACT_LABEL:
            context["in_abstract"] = True
            context["in_keywords"] = False

        if paragraph_type == ParagraphType.ABSTRACT_CONTENT:
            context["in_abstract"] = True

        if paragraph_type in {ParagraphType.KEYWORDS_LABEL, ParagraphType.KEYWORDS_CONTENT}:
            context["in_abstract"] = False
            context["in_keywords"] = True

        if paragraph_type == ParagraphType.SECTION_HEADING:
            context["in_abstract"] = False
            context["in_keywords"] = False
            if "reference" in text_lower or "bibliography" in text_lower:
                context["in_references"] = True
            elif context.get("in_references"):
                context["in_references"] = False

    def _rule_classify_single(self, data: Dict, context: Dict = None) -> ClassifiedParagraph:
        """Classify one paragraph with deterministic rules."""
        if context is None:
            context = {
                "found_title": False,
                "in_abstract": False,
                "in_keywords": False,
                "in_references": False,
            }

        text = data["text"].strip()
        index = data["index"]
        font_info = data["font_info"]
        alignment = data["alignment"]
        text_lower = text.lower()

        if not text:
            return self._create_classification(data, ParagraphType.EMPTY, 1.0, "Empty paragraph")

        if self._is_template_instruction(text_lower):
            return self._create_classification(data, ParagraphType.TEMPLATE_INSTRUCTION, 0.95, "Template instruction")

        if self._is_journal_header(text_lower, index):
            return self._create_classification(data, ParagraphType.JOURNAL_HEADER, 0.95, "Journal header")

        if self._is_probable_title(text, font_info, alignment, index, context):
            return self._create_classification(data, ParagraphType.PAPER_TITLE, 0.92, "Paper title")

        if text_lower in {"abstract", "abstract:"}:
            return self._create_classification(data, ParagraphType.ABSTRACT_LABEL, 0.96, "Abstract label")

        if self._starts_with_label(text_lower, "abstract"):
            return self._create_classification(data, ParagraphType.ABSTRACT_CONTENT, 0.92, "Abstract content")

        if text_lower in {"keywords", "keywords:", "key words", "key words:"}:
            return self._create_classification(data, ParagraphType.KEYWORDS_LABEL, 0.96, "Keywords label")

        if self._starts_with_keywords(text_lower):
            return self._create_classification(data, ParagraphType.KEYWORDS_CONTENT, 0.92, "Keywords content")

        if self._is_author_info(text, text_lower, index, alignment, context):
            return self._create_classification(data, ParagraphType.AUTHOR_INFO, 0.90, "Author information")

        if self._is_section_heading(text):
            return self._create_classification(data, ParagraphType.SECTION_HEADING, 0.92, "Section heading")

        if self._is_caption(text_lower):
            return self._create_classification(data, ParagraphType.CAPTION, 0.90, "Caption")

        if self._is_reference_entry(text, context.get("in_references", False)):
            return self._create_classification(data, ParagraphType.REFERENCE, 0.86, "Reference entry")

        if self._is_algorithm(text, text_lower):
            return self._create_classification(data, ParagraphType.ALGORITHM, 0.88, "Algorithm or pseudocode")

        if self._is_equation(text):
            return self._create_classification(data, ParagraphType.EQUATION, 0.84, "Equation or formula")

        if self._is_code_block(text, font_info):
            return self._create_classification(data, ParagraphType.CODE_BLOCK, 0.82, "Code-like text")

        if context.get("in_abstract"):
            return self._create_classification(data, ParagraphType.ABSTRACT_CONTENT, 0.76, "Abstract continuation")

        if context.get("in_keywords"):
            return self._create_classification(data, ParagraphType.KEYWORDS_CONTENT, 0.74, "Keywords continuation")

        if len(text) > 30:
            return self._create_classification(data, ParagraphType.BODY, 0.66, "Body text")

        return self._create_classification(data, ParagraphType.UNKNOWN, 0.50, "Unknown short text")

    def _is_journal_header(self, text_lower: str, index: int) -> bool:
        """Return True for journal names and publication metadata."""
        if index > 8:
            return False

        patterns = [
            r"journal\s+of",
            r"web\s+engineering$",
            r"vol\.\s*\d+",
            r"volume\s*\d+",
            r"eissn|pissn|issn",
            r"doi[:\s]",
            r"https?://",
            r"www\.",
        ]
        return any(re.search(pattern, text_lower) for pattern in patterns)

    def _is_author_info(self, text: str, text_lower: str, index: int, alignment: str, context: Dict) -> bool:
        """Return True for author names, affiliations, emails, and ORCID lines."""
        if index > 25:
            return False

        if re.search(r"[\w\.-]+@[\w\.-]+\.\w+", text):
            return True

        if re.search(r"orcid|corresponding\s+author", text_lower):
            return True

        if re.search(
            r"university|universiti|faculty|fakulti|department|school|college|institute|centre|center",
            text_lower,
        ):
            return True

        if context.get("found_title") and not self._starts_with_label(text_lower, "abstract"):
            if index <= 12 and not text.isupper() and len(text) <= 180:
                if re.search(r"\d", text) and len(text.split()) >= 1:
                    return True
                if "," in text and len(text.split()) <= 20:
                    return True
                if text_lower in {"&", "and"}:
                    return True
                if alignment == "CENTER" and len(text.split()) <= 8:
                    return True

        return False

    def _is_probable_title(self, text: str, font_info: Dict, alignment: str, index: int, context: Dict) -> bool:
        """Return True for the actual paper title, not the journal title."""
        if context.get("found_title") or index > 12:
            return False

        text_lower = text.lower()
        if self._is_journal_header(text_lower, index):
            return False
        if self._is_section_heading(text):
            return False
        if self._starts_with_label(text_lower, "abstract") or self._starts_with_keywords(text_lower):
            return False
        if len(text) < 15 or len(text) > 240:
            return False

        font_size = font_info.get("font_size") or 0
        is_bold = bool(font_info.get("bold"))
        is_centered = alignment == "CENTER"

        if font_size >= 16 and is_centered:
            return True
        if font_size >= 14 and is_bold and is_centered:
            return True
        if index <= 6 and is_centered and len(text.split()) >= 4 and not text.endswith("."):
            return True

        return False

    def _is_section_heading(self, text: str) -> bool:
        """Return True for common academic section headings."""
        text_clean = re.sub(r"\s+", " ", text.strip())
        text_lower = text_clean.lower().strip(".")

        common = {
            "introduction",
            "background",
            "literature review",
            "related work",
            "methodology",
            "method",
            "methods",
            "materials and methods",
            "research methodology",
            "results",
            "discussion",
            "results and discussion",
            "results and discussions",
            "implementation",
            "evaluation",
            "experiment",
            "experiments",
            "experimental setup",
            "test configuration",
            "conclusion",
            "conclusions",
            "conclusion and future work",
            "future work",
            "acknowledgement",
            "acknowledgements",
            "acknowledgment",
            "acknowledgments",
            "funding statement",
            "author contributions",
            "conflict of interests",
            "conflict of interest",
            "ethics statements",
            "ethics statement",
            "references",
            "bibliography",
            "biographies of authors",
        }

        if text_lower in common:
            return True

        heading_words = (
            "introduction|background|literature review|related work|methodology|"
            "methods?|materials and methods|research methodology|results?|discussion|"
            "results and discussions?|implementation|evaluation|experiments?|"
            "experimental setup|test configuration|conclusions?|conclusion and future work|"
            "future work|references?|bibliography|"
            "acknowledgements?|funding statement|author contributions?|"
            "conflict of interests?|ethics statements?"
        )
        if re.match(rf"^(\d+(\.\d+)*\.?|[ivxlc]+\.?)\s+({heading_words})$", text_lower):
            return True

        if text_clean.isupper() and 4 <= len(text_clean) <= 80:
            return any(word in text_lower for word in common)

        return False

    def _is_template_instruction(self, text_lower: str) -> bool:
        """Return True for template-only formatting instructions."""
        return bool(re.match(r"^\(?\s*\d+(?:\.\d+)?\s*[-\s]*(?:font size|point|pt)", text_lower))

    def _is_caption(self, text_lower: str) -> bool:
        """Return True for figure and table captions."""
        return bool(re.match(r"^(figure|fig\.?|table|chart|diagram|image)\s*\d+", text_lower))

    def _is_reference_entry(self, text: str, in_references: bool) -> bool:
        """Return True for bibliography entries."""
        stripped = text.strip()
        if re.match(r"^\[\d+\]", stripped):
            return True
        if in_references and len(stripped) > 20:
            return True
        return False

    def _is_algorithm(self, text: str, text_lower: str) -> bool:
        """Return True for algorithm and pseudocode lines."""
        if re.match(r"^algorithm\s*\d*", text_lower):
            return True
        if re.match(r"^(input|output|begin|end|procedure|function)\s*:", text_lower):
            return True
        if re.match(r"^\d+\s*:\s+", text_lower):
            return True
        pseudocode_markers = [
            "for each ",
            "while ",
            "if ",
            "return ",
            "initialize ",
        ]
        return any(text_lower.startswith(marker) for marker in pseudocode_markers) and len(text.split()) <= 25

    def _is_equation(self, text: str) -> bool:
        """Return True for standalone equations or formula-like lines."""
        stripped = text.strip()
        if len(stripped) > 120 or len(stripped.split()) > 20:
            return False
        operator_count = sum(stripped.count(token) for token in ["=", "+", "-", "*", "/", "^", "_"])
        return operator_count >= 2 and bool(re.search(r"[A-Za-z0-9]\s*=", stripped))

    def _is_code_block(self, text: str, font_info: Dict) -> bool:
        """Return True for monospace code-like paragraphs."""
        font_name = (font_info.get("font_name") or "").lower()
        if any(name in font_name for name in ["courier", "consolas", "monaco"]):
            return True
        if re.search(r"[{};]|==|!=|<=|>=", text) and len(text.split()) <= 30:
            return True
        return False

    def _starts_with_label(self, text_lower: str, label: str) -> bool:
        """Return True when text begins with a named label."""
        return bool(re.match(rf"^{label}\s*[-–—:]", text_lower))

    def _starts_with_keywords(self, text_lower: str) -> bool:
        """Return True for keyword lines."""
        return bool(re.match(r"^(keywords?|key\s+words?)\s*[-–—:]", text_lower))

    def _create_classification(
        self,
        data: Dict,
        para_type: ParagraphType,
        confidence: float,
        reason: str,
    ) -> ClassifiedParagraph:
        """Create a classification record."""
        return ClassifiedParagraph(
            index=data["index"],
            text=data["text"],
            paragraph_type=para_type,
            confidence=confidence,
            font_info=data["font_info"],
            alignment=data["alignment"],
            should_fix=para_type in self.FIX_TYPES,
            classification_reason=reason,
        )

    def _string_to_paragraph_type(self, type_str: str) -> ParagraphType:
        """Convert a string label to a ParagraphType enum."""
        if not type_str:
            return ParagraphType.UNKNOWN

        type_mapping = {
            "journal_header": ParagraphType.JOURNAL_HEADER,
            "paper_title": ParagraphType.PAPER_TITLE,
            "author_info": ParagraphType.AUTHOR_INFO,
            "abstract_label": ParagraphType.ABSTRACT_LABEL,
            "abstract_content": ParagraphType.ABSTRACT_CONTENT,
            "keywords_label": ParagraphType.KEYWORDS_LABEL,
            "keywords_content": ParagraphType.KEYWORDS_CONTENT,
            "section_heading": ParagraphType.SECTION_HEADING,
            "body": ParagraphType.BODY,
            "caption": ParagraphType.CAPTION,
            "reference": ParagraphType.REFERENCE,
            "algorithm": ParagraphType.ALGORITHM,
            "code_block": ParagraphType.CODE_BLOCK,
            "equation": ParagraphType.EQUATION,
        }
        return type_mapping.get(type_str.lower().strip(), ParagraphType.UNKNOWN)

    def get_paragraphs_to_fix(self) -> List[ClassifiedParagraph]:
        """Return paragraphs that may be auto-fixed."""
        return [cp for cp in self.classifications if cp.should_fix]

    def get_paragraphs_to_skip(self) -> List[ClassifiedParagraph]:
        """Return paragraphs that should be preserved."""
        return [cp for cp in self.classifications if not cp.should_fix]

    def get_classification_summary(self) -> Dict[str, int]:
        """Return counts by paragraph type."""
        summary = {}
        for cp in self.classifications:
            type_name = cp.paragraph_type.value
            summary[type_name] = summary.get(type_name, 0) + 1
        return summary
