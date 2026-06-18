"""
Auto-Fixer Module
Automatically fixes formatting issues while preserving special formatting
"""

from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_COLOR_INDEX, WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from copy import deepcopy
import re
from io import BytesIO

from .utils import (
    load_document, get_paragraph_text, get_paragraph_alignment, truncate_text,
    is_font_equivalent, get_run_font_info
)
from .paragraph_classifier import (
    ParagraphType, ClassifiedParagraph
)
from config import ALIGNMENT_REVERSE_MAP


@dataclass
class ChangeRecord:
    """Record of a change made during auto-fix"""
    paragraph_index: int
    location: str
    change_type: str
    before: str
    after: str
    text_preview: str
    property_name: str = "formatting"
    current_value: str = ""
    target_value: str = ""
    paragraph_type: str = ""
    evidence: str = ""


class AutoFixer:
    """
    Automatically fixes formatting issues in a manuscript
    while preserving special formatting (italic, underline, subscript, etc.)
    """
    
    def __init__(
        self,
        rules: Dict[str, Any],
        classifications: List[ClassifiedParagraph],
        issues_by_category: Optional[Dict[str, List[Any]]] = None,
    ):
        """
        Initialize auto-fixer with template rules and paragraph classifications
        
        Args:
            rules: Template formatting rules
            classifications: List of classified paragraphs from ParagraphClassifier
        """
        self.rules = rules
        self.classifications = classifications
        self.issues_by_category = issues_by_category or {}
        self.changes: List[ChangeRecord] = []
        self.document = None
        self.original_document = None
        self._classification_map: Dict[int, ClassifiedParagraph] = {}
        self._issue_map: Dict[int, set] = {}
        self._issue_property_map: Dict[int, set] = {}
        self._global_issue_categories: set = set()
        self._global_issue_property_map: Dict[str, set] = {}
        self._has_explicit_issues = bool(issues_by_category)
        self._build_issue_map()
    
    def load_manuscript(self, file_path_or_bytes):
        """Load the manuscript to fix"""
        self.document = load_document(file_path_or_bytes)
        self.original_document = deepcopy(self.document)
        # Create index map for quick lookup
        self._classification_map = {cp.index: cp for cp in self.classifications}
        return self

    def _build_issue_map(self):
        """Build paragraph-to-category and paragraph-to-property maps from detected issues."""
        self._issue_map = {}
        self._issue_property_map = {}
        self._global_issue_categories = set()
        self._global_issue_property_map = {}
        for category, issues in self.issues_by_category.items():
            for issue in issues:
                para_index = getattr(issue, "paragraph_index", -1)
                if para_index is None or para_index < 0:
                    self._global_issue_categories.add(category)
                    properties = self._infer_global_issue_properties(category, issue)
                    if properties:
                        self._global_issue_property_map.setdefault(category, set()).update(properties)
                    continue
                self._issue_map.setdefault(para_index, set()).add(category)
                property_name = self._infer_issue_property(issue)
                if property_name:
                    self._issue_property_map.setdefault(para_index, set()).add(property_name)

    def _infer_issue_property(self, issue: Any) -> Optional[str]:
        """Infer the affected formatting property from a checker issue."""
        description = (getattr(issue, "description", "") or "").lower()
        location = (getattr(issue, "location", "") or "").lower()

        if "number" in description or "heading number" in location:
            if "bold" in description:
                return "number_bold"
            if "font size" in description or "size" in description:
                return "number_font_size"
            if "font" in description:
                return "number_font_name"

        if "line spacing" in description:
            return "line_spacing"
        if "manual tab" in description or "manual tabs" in description:
            return "manual_tabs"
        if "alignment" in description:
            return "alignment"
        if "font size" in description or " size " in f" {description} ":
            return "font_size"
        if "font" in description:
            return "font_name"
        if "bold" in description:
            return "bold"
        if "italic" in description:
            return "italic"
        return None

    def _infer_global_issue_properties(self, category: str, issue: Any) -> set:
        """Infer properties represented by an aggregate category-level issue."""
        property_name = self._infer_issue_property(issue)
        if property_name:
            return {property_name}

        if category == "body_text":
            return {"font_name", "font_size"}
        if category in {"references", "figures", "tables"}:
            return {"font_name", "font_size"}
        if category == "line_spacing":
            return {"line_spacing"}
        if category == "other" and "manual tab" in (getattr(issue, "description", "") or "").lower():
            return {"manual_tabs"}
        return set()

    def _should_fix_category(self, index: int, categories: List[str]) -> bool:
        """Return True when a paragraph has a detected issue for the target categories."""
        if not self._has_explicit_issues:
            return True
        found_categories = self._issue_map.get(index, set())
        return any(
            category in found_categories or category in self._global_issue_categories
            for category in categories
        )

    def _allowed_properties_for(
        self,
        index: int,
        categories: Optional[List[str]] = None,
        fallback: Optional[List[str]] = None,
    ) -> Optional[set]:
        """Return properties that may be fixed for a paragraph."""
        if not self._has_explicit_issues:
            return None
        properties = set(self._issue_property_map.get(index, set()))
        for category in categories or []:
            properties.update(self._global_issue_property_map.get(category, set()))
        if properties:
            return properties
        return set(fallback or [])

    def _property_allowed(self, property_name: str, allowed_properties: Optional[set]) -> bool:
        """Return True when a property can be changed under the current issue filter."""
        return allowed_properties is None or property_name in allowed_properties

    def _has_category_issue(self, category: str) -> bool:
        """Return True when the checker reported at least one issue in a category."""
        if not self._has_explicit_issues:
            return True
        return bool(self.issues_by_category.get(category))

    def _category_allows_global_property(self, category: str, property_name: str) -> bool:
        """Return True when a category-level issue permits a document-level fix."""
        if not self._has_explicit_issues:
            return True
        return property_name in self._global_issue_property_map.get(category, set())
    
    def fix_all(self) -> Tuple[Document, List[ChangeRecord]]:
        """
        Apply all formatting fixes to the document
        
        Returns:
            Tuple of (fixed document, list of changes made)
        """
        if not self.document:
            raise ValueError("No document loaded. Call load_manuscript() first.")
        
        self.changes = []
        
        # Fix margins first only when margin issues were detected.
        if self._has_category_issue("margins"):
            self._fix_margins()
        if self._category_allows_global_property("other", "manual_tabs"):
            self._fix_page_header_layout()
        
        # Fix paragraphs based on their classification
        for i, para in enumerate(self.document.paragraphs):
            classification = self._classification_map.get(i)
            
            if not classification or not classification.should_fix:
                continue
            
            para_type = classification.paragraph_type
            
            if para_type == ParagraphType.JOURNAL_HEADER and self._is_journal_title_header(classification.text):
                if not self._should_fix_category(i, ["journal_header"]):
                    continue
                self._fix_journal_header(para, i)
            elif para_type == ParagraphType.PAPER_TITLE:
                if self._should_fix_category(i, ["title"]):
                    self._fix_title(para, i)
            elif para_type == ParagraphType.SECTION_HEADING:
                if self._should_fix_category(i, ["headings"]):
                    self._fix_heading(para, i)
            elif para_type == ParagraphType.BODY:
                if self._should_fix_category(i, ["body_text", "line_spacing"]):
                    self._fix_body_text(para, i)
            elif para_type == ParagraphType.ABSTRACT_CONTENT:
                if self._should_fix_category(i, ["body_text", "line_spacing"]):
                    self._fix_abstract(para, i)
            elif para_type == ParagraphType.KEYWORDS_CONTENT:
                if self._should_fix_category(i, ["body_text"]):
                    self._fix_keywords(para, i)
            elif para_type == ParagraphType.CAPTION:
                if self._should_fix_category(i, ["figures", "tables"]):
                    self._fix_caption(para, i)
            elif para_type == ParagraphType.REFERENCE:
                if self._should_fix_category(i, ["references"]):
                    self._fix_reference(para, i)
        
        return self.document, self.changes

    def _is_journal_title_header(self, text: str) -> bool:
        """Return True for journal title lines, excluding volume and ISSN metadata."""
        text_lower = text.lower()
        return "journal of informatics" in text_lower or text_lower.strip() == "web engineering"
    
    def _fix_margins(self):
        """Fix page margins with structured change records."""
        expected_margins = self.rules.get("margins", {})

        for section in self.document.sections:
            margin_specs = [
                ("left_margin", "left", "Left Margin"),
                ("right_margin", "right", "Right Margin"),
                ("top_margin", "top", "Top Margin"),
                ("bottom_margin", "bottom", "Bottom Margin"),
            ]

            for attr_name, rule_name, label in margin_specs:
                current_margin = getattr(section, attr_name)
                if not current_margin:
                    continue

                current_value = current_margin.inches
                expected_value = expected_margins.get(rule_name, 1.0)
                if abs(current_value - expected_value) <= 0.05:
                    continue

                setattr(section, attr_name, Inches(expected_value))
                self._add_change_record(
                    paragraph_index=-1,
                    location=label,
                    change_type="margins",
                    property_name=rule_name,
                    current_value=f"{current_value:.2f} in",
                    target_value=f"{expected_value:.2f} in",
                    text_preview="Document margins adjusted",
                    paragraph_type="document",
                    evidence="Detected margin issue"
                )

    def _fix_page_header_layout(self):
        """Normalize page header tab spacing to reduce Word wrapping."""
        for section_index, section in enumerate(self.document.sections):
            headers = [
                ("Page Header", section.header),
                ("First Page Header", section.first_page_header),
                ("Even Page Header", section.even_page_header),
            ]
            usable_width = section.page_width - section.left_margin - section.right_margin

            for label, header in headers:
                for paragraph in header.paragraphs:
                    original_text = paragraph.text
                    if not self._has_unstable_header_tabs(original_text):
                        continue
                    normalized_text = self._normalize_tabbed_header_text(original_text)
                    if normalized_text == original_text:
                        continue

                    paragraph.text = normalized_text
                    try:
                        tab_stops = paragraph.paragraph_format.tab_stops
                        tab_stops.clear_all()
                        tab_stops.add_tab_stop(usable_width, WD_TAB_ALIGNMENT.RIGHT)
                    except Exception:
                        pass

                    self._add_change_record(
                        paragraph_index=-1,
                        location=f"{label} (Section {section_index + 1})",
                        change_type="page_header",
                        property_name="manual_tabs",
                        current_value=truncate_text(original_text, 80),
                        target_value=truncate_text(normalized_text, 80),
                        text_preview=truncate_text(normalized_text, 80),
                        paragraph_type="document_header",
                        evidence="Detected page header manual tabs/spaces that may wrap in Word",
                    )

    def _has_unstable_header_tabs(self, text: str) -> bool:
        """Return True for tab spacing patterns that are likely to wrap in Word."""
        return "\t\t" in text or bool(re.search(r"\t\s{2,}", text))

    def _normalize_tabbed_header_text(self, text: str) -> str:
        """Collapse unstable tab runs into one left/right tab-separated header line."""
        if "\t" not in text:
            return text
        parts = [re.sub(r"\s+", " ", part).strip() for part in text.split("\t") if part.strip()]
        if len(parts) < 2:
            return text
        return f"{parts[0]}\t{parts[-1]}"

    def _add_change_record(
        self,
        paragraph_index: int,
        location: str,
        change_type: str,
        property_name: str,
        current_value: str,
        target_value: str,
        text_preview: str,
        paragraph_type: str,
        evidence: str,
    ):
        """Append one structured change record."""
        self.changes.append(ChangeRecord(
            paragraph_index=paragraph_index,
            location=location,
            change_type=change_type,
            before=f"{property_name}: {current_value}",
            after=f"{property_name}: {target_value}",
            text_preview=text_preview,
            property_name=property_name,
            current_value=current_value,
            target_value=target_value,
            paragraph_type=paragraph_type,
            evidence=evidence,
        ))

    def _add_property_changes(
        self,
        paragraph_index: int,
        location: str,
        change_type: str,
        details: List[Dict[str, str]],
        text_preview: str,
        paragraph_type: str,
    ):
        """Add de-duplicated property changes for one paragraph."""
        seen = set()
        for detail in details:
            key = (
                detail.get("property_name", "formatting"),
                detail.get("current_value", ""),
                detail.get("target_value", ""),
            )
            if key in seen:
                continue
            seen.add(key)
            self._add_change_record(
                paragraph_index=paragraph_index,
                location=location,
                change_type=change_type,
                property_name=detail.get("property_name", "formatting"),
                current_value=detail.get("current_value", ""),
                target_value=detail.get("target_value", ""),
                text_preview=text_preview,
                paragraph_type=paragraph_type,
                evidence=detail.get("evidence", "Detected formatting difference"),
            )

    def _fix_journal_header(self, paragraph, index: int):
        """Fix journal title/header formatting without using paper title rules."""
        header_rules = self.rules.get("journal_header", {})
        changes = []
        current_alignment = get_paragraph_alignment(paragraph)
        allowed_properties = self._allowed_properties_for(
            index,
            categories=["journal_header"],
            fallback=["font_name", "font_size", "bold", "alignment", "manual_tabs"],
        )

        expected_font = header_rules.get("font_name", "Palatino Linotype")
        expected_size = header_rules.get("font_size", 24)
        expected_bold = header_rules.get("bold", True)
        expected_alignment = header_rules.get("alignment", "CENTER")

        original_text = paragraph.text
        cleaned_text = original_text.strip(" \t")
        if (
            self._property_allowed("manual_tabs", allowed_properties)
            and cleaned_text
            and cleaned_text != original_text
        ):
            paragraph.text = cleaned_text
            changes.append({
                "property_name": "manual_tabs",
                "current_value": "Manual tabs/spaces",
                "target_value": "No leading/trailing manual tabs/spaces",
                "evidence": "Journal header contained manual indentation that can shift layout",
            })

        if self._property_allowed("alignment", allowed_properties) and current_alignment != expected_alignment:
            paragraph.alignment = WD_ALIGN_PARAGRAPH(
                ALIGNMENT_REVERSE_MAP.get(expected_alignment, 1)
            )
            changes.append({
                "property_name": "alignment",
                "current_value": current_alignment,
                "target_value": expected_alignment,
                "evidence": "Journal header alignment did not match target rule",
            })

        for run in paragraph.runs:
            if run.text.strip():
                changes.extend(self._fix_run_formatting(
                    run,
                    expected_font,
                    expected_size,
                    expected_bold,
                    expected_strike=False,
                    allowed_properties=allowed_properties,
                ))

        if changes:
            self._add_property_changes(
                paragraph_index=index,
                location="Journal Header",
                change_type="journal_header",
                details=changes,
                text_preview=truncate_text(get_paragraph_text(paragraph), 50),
                paragraph_type=ParagraphType.JOURNAL_HEADER.value,
            )

    def _fix_run_formatting(self, run, expected_font: str, expected_size: float,
                           expected_bold: Optional[bool] = None,
                           expected_italic: Optional[bool] = None,
                           expected_strike: Optional[bool] = None,
                           allowed_properties: Optional[set] = None) -> List[Dict[str, str]]:
        """Fix a run and return structured property changes."""
        changes = []
        font = run.font

        preserve_italic = font.italic
        preserve_underline = font.underline
        preserve_subscript = font.subscript
        preserve_superscript = font.superscript
        preserve_strike = font.strike

        current_font = font.name
        if expected_font is not None and self._property_allowed("font_name", allowed_properties):
            if current_font is None or not is_font_equivalent(current_font, expected_font):
                font.name = expected_font
                changes.append({
                    "property_name": "font_name",
                    "current_value": current_font or "(inherited)",
                    "target_value": expected_font,
                    "evidence": "Run font did not match target rule",
                })

        current_size = font.size.pt if font.size else None
        if expected_size is not None and self._property_allowed("font_size", allowed_properties):
            if current_size is None or abs(current_size - expected_size) > 0.5:
                font.size = Pt(expected_size)
                changes.append({
                    "property_name": "font_size",
                    "current_value": f"{current_size} pt" if current_size is not None else "(inherited)",
                    "target_value": f"{expected_size} pt",
                    "evidence": "Run font size did not match target rule",
                })

        if expected_bold is not None and self._property_allowed("bold", allowed_properties):
            current_bold = font.bold
            current_bold_value = bool(current_bold) if current_bold is not None else False
            if current_bold_value != expected_bold:
                font.bold = expected_bold
                changes.append({
                    "property_name": "bold",
                    "current_value": "Bold" if current_bold_value else "Not Bold",
                    "target_value": "Bold" if expected_bold else "Not Bold",
                    "evidence": "Run bold setting did not match target rule",
                })

        if expected_italic is not None and self._property_allowed("italic", allowed_properties):
            current_italic = font.italic
            current_italic_value = bool(current_italic) if current_italic is not None else False
            if current_italic_value != expected_italic:
                font.italic = expected_italic
                changes.append({
                    "property_name": "italic",
                    "current_value": "Italic" if current_italic_value else "Not Italic",
                    "target_value": "Italic" if expected_italic else "Not Italic",
                    "evidence": "Run italic setting did not match target rule",
                })
        else:
            font.italic = preserve_italic

        if expected_strike is not None and self._property_allowed("strike", allowed_properties):
            if font.strike != expected_strike:
                font.strike = expected_strike
        else:
            font.strike = preserve_strike

        font.underline = preserve_underline
        font.subscript = preserve_subscript
        font.superscript = preserve_superscript

        return changes

    def _fix_title(self, paragraph, index: int):
        """Fix paper title formatting with structured change records."""
        title_rules = self.rules.get("title", {})
        changes = []
        current_alignment = get_paragraph_alignment(paragraph)
        allowed_properties = self._allowed_properties_for(
            index,
            categories=["title"],
            fallback=["font_name", "font_size", "bold", "italic", "alignment"],
        )

        expected_font = title_rules.get("font_name", "Times New Roman")
        expected_size = title_rules.get("font_size", 24)
        expected_bold = title_rules.get("bold", None)
        expected_italic = title_rules.get("italic", None)
        expected_alignment = title_rules.get("alignment", "CENTER")

        if self._property_allowed("alignment", allowed_properties) and current_alignment != expected_alignment:
            paragraph.alignment = WD_ALIGN_PARAGRAPH(
                ALIGNMENT_REVERSE_MAP.get(expected_alignment, 1)
            )
            changes.append({
                "property_name": "alignment",
                "current_value": current_alignment,
                "target_value": expected_alignment,
                "evidence": "Paragraph alignment did not match target rule",
            })

        for run in paragraph.runs:
            if run.text.strip():
                changes.extend(self._fix_run_formatting(
                    run,
                    expected_font,
                    expected_size,
                    expected_bold,
                    expected_italic,
                    expected_strike=False,
                    allowed_properties=allowed_properties,
                ))

        if changes:
            self._add_property_changes(
                paragraph_index=index,
                location="Paper Title",
                change_type="title",
                details=changes,
                text_preview=truncate_text(get_paragraph_text(paragraph), 50),
                paragraph_type=ParagraphType.PAPER_TITLE.value,
            )

    def _fix_heading(self, paragraph, index: int):
        """Fix section heading formatting with structured change records."""
        heading_rules = self._heading_rules_for_text(get_paragraph_text(paragraph))
        changes = []
        allowed_properties = self._allowed_properties_for(
            index,
            categories=["headings"],
            fallback=["font_name", "font_size", "bold", "italic", "number_font_name", "number_font_size", "number_bold"],
        )

        expected_font = heading_rules.get("font_name", "Times New Roman")
        expected_size = heading_rules.get("font_size", 10)
        expected_bold = heading_rules.get("bold", None)
        expected_italic = heading_rules.get("italic", None)

        changes.extend(self._fix_numbering_formatting(
            paragraph,
            expected_font,
            expected_size,
            expected_bold,
            allowed_properties,
        ))

        for run in paragraph.runs:
            if run.text.strip():
                changes.extend(self._fix_run_formatting(
                    run,
                    expected_font,
                    expected_size,
                    expected_bold,
                    expected_italic,
                    expected_strike=False,
                    allowed_properties=allowed_properties,
                ))

        if changes:
            self._add_property_changes(
                paragraph_index=index,
                location="Section Heading",
                change_type="heading",
                details=changes,
                text_preview=truncate_text(get_paragraph_text(paragraph), 40),
                paragraph_type=ParagraphType.SECTION_HEADING.value,
            )

    def _heading_rules_for_text(self, text: str) -> Dict[str, Any]:
        """Return the correct heading rule for main headings or subheadings."""
        stripped = re.sub(r"\s+", " ", text.strip())
        if re.match(r"^\d+\.\d+", stripped):
            return self.rules.get("subheading", self.rules.get("heading", {}))
        return self.rules.get("heading", {})

    def _get_numbering_level(self, paragraph):
        """Return the numbering level XML element for a numbered paragraph."""
        p_pr = paragraph._p.pPr
        if p_pr is None or p_pr.numPr is None:
            return None

        num_id_element = p_pr.numPr.numId
        ilvl_element = p_pr.numPr.ilvl
        if num_id_element is None:
            return None

        num_id = num_id_element.val
        ilvl = str(ilvl_element.val if ilvl_element is not None else 0)
        numbering = self.document.part.numbering_part.element

        abstract_num_id = None
        for num in numbering.findall(qn("w:num")):
            if num.get(qn("w:numId")) == str(num_id):
                abstract_node = num.find(qn("w:abstractNumId"))
                if abstract_node is not None:
                    abstract_num_id = abstract_node.get(qn("w:val"))
                break

        if abstract_num_id is None:
            return None

        for abstract_num in numbering.findall(qn("w:abstractNum")):
            if abstract_num.get(qn("w:abstractNumId")) != str(abstract_num_id):
                continue
            for level in abstract_num.findall(qn("w:lvl")):
                if level.get(qn("w:ilvl")) == ilvl:
                    return level

        return None

    def _get_or_create_child(self, parent, tag_name: str):
        """Return a child XML node, creating it when missing."""
        child = parent.find(qn(tag_name))
        if child is None:
            child = OxmlElement(tag_name)
            parent.append(child)
        return child

    def _numbering_bold_value(self, r_pr) -> Optional[bool]:
        """Read numbering bold value from a numbering rPr node."""
        bold = r_pr.find(qn("w:b")) if r_pr is not None else None
        if bold is None:
            return None
        value = bold.get(qn("w:val"))
        return value not in {"0", "false", "False", "off"}

    def _fix_numbering_formatting(
        self,
        paragraph,
        expected_font: str,
        expected_size: float,
        expected_bold: Optional[bool],
        allowed_properties: Optional[set] = None,
    ) -> List[Dict[str, str]]:
        """Fix Word list numbering formatting for numbered headings."""
        level = self._get_numbering_level(paragraph)
        if level is None:
            return []

        changes = []
        r_pr = self._get_or_create_child(level, "w:rPr")

        if expected_font and self._property_allowed("number_font_name", allowed_properties):
            r_fonts = self._get_or_create_child(r_pr, "w:rFonts")
            current_font = r_fonts.get(qn("w:ascii")) or r_fonts.get(qn("w:hAnsi"))
            if current_font and not is_font_equivalent(current_font, expected_font):
                changes.append({
                    "property_name": "number_font_name",
                    "current_value": current_font,
                    "target_value": expected_font,
                    "evidence": "Heading number font did not match target rule",
                })
            r_fonts.set(qn("w:ascii"), expected_font)
            r_fonts.set(qn("w:hAnsi"), expected_font)

        if expected_size and self._property_allowed("number_font_size", allowed_properties):
            size_node = self._get_or_create_child(r_pr, "w:sz")
            current_size = None
            if size_node.get(qn("w:val")):
                current_size = int(size_node.get(qn("w:val"))) / 2
            if current_size is not None and abs(current_size - expected_size) > 0.5:
                changes.append({
                    "property_name": "number_font_size",
                    "current_value": f"{current_size:.1f} pt",
                    "target_value": f"{expected_size} pt",
                    "evidence": "Heading number font size did not match target rule",
                })
            size_node.set(qn("w:val"), str(int(float(expected_size) * 2)))

        if expected_bold is not None and self._property_allowed("number_bold", allowed_properties):
            current_bold = self._numbering_bold_value(r_pr)
            if current_bold != expected_bold:
                changes.append({
                    "property_name": "number_bold",
                    "current_value": "Bold" if current_bold else "Not Bold",
                    "target_value": "Bold" if expected_bold else "Not Bold",
                    "evidence": "Heading number bold setting did not match target rule",
                })
            bold_node = self._get_or_create_child(r_pr, "w:b")
            bold_node.set(qn("w:val"), "1" if expected_bold else "0")

        return changes

    def _fix_body_text(self, paragraph, index: int):
        """Fix body text formatting with structured change records."""
        body_rules = self.rules.get("body", {})
        changes = []
        allowed_properties = self._allowed_properties_for(
            index,
            categories=["body_text", "line_spacing"],
            fallback=["font_name", "font_size", "line_spacing"],
        )

        expected_font = body_rules.get("font_name", "Times New Roman")
        expected_size = body_rules.get("font_size", 12)

        for run in paragraph.runs:
            if run.text.strip():
                changes.extend(self._fix_run_formatting(
                    run,
                    expected_font,
                    expected_size,
                    None,
                    allowed_properties=allowed_properties,
                ))

        expected_spacing = body_rules.get("line_spacing")
        if expected_spacing and self._property_allowed("line_spacing", allowed_properties):
            paragraph_format = paragraph.paragraph_format
            if paragraph_format.line_spacing != expected_spacing:
                current_spacing = paragraph_format.line_spacing
                paragraph_format.line_spacing = expected_spacing
                changes.append({
                    "property_name": "line_spacing",
                    "current_value": str(current_spacing) if current_spacing is not None else "(inherited)",
                    "target_value": str(expected_spacing),
                    "evidence": "Paragraph line spacing did not match target rule",
                })

        if changes:
            self._add_property_changes(
                paragraph_index=index,
                location=f"Body Text (Para {index + 1})",
                change_type="body",
                details=changes,
                text_preview=truncate_text(get_paragraph_text(paragraph), 40),
                paragraph_type=ParagraphType.BODY.value,
            )

    def _fix_abstract(self, paragraph, index: int):
        """Fix abstract formatting with structured change records."""
        abstract_rules = self.rules.get("abstract", {})
        changes = []
        allowed_properties = self._allowed_properties_for(
            index,
            categories=["body_text", "line_spacing"],
            fallback=["font_name", "font_size", "line_spacing"],
        )

        expected_font = abstract_rules.get("font_name", "Times New Roman")
        expected_size = abstract_rules.get("font_size", 9)

        for run in paragraph.runs:
            if run.text.strip():
                changes.extend(self._fix_run_formatting(
                    run,
                    expected_font,
                    expected_size,
                    None,
                    allowed_properties=allowed_properties,
                ))

        expected_spacing = abstract_rules.get("line_spacing", self.rules.get("body", {}).get("line_spacing"))
        if expected_spacing and self._property_allowed("line_spacing", allowed_properties):
            paragraph_format = paragraph.paragraph_format
            if paragraph_format.line_spacing != expected_spacing:
                current_spacing = paragraph_format.line_spacing
                paragraph_format.line_spacing = expected_spacing
                changes.append({
                    "property_name": "line_spacing",
                    "current_value": str(current_spacing) if current_spacing is not None else "(inherited)",
                    "target_value": str(expected_spacing),
                    "evidence": "Abstract line spacing did not match target rule",
                })

        if changes:
            self._add_property_changes(
                paragraph_index=index,
                location="Abstract",
                change_type="abstract",
                details=changes,
                text_preview=truncate_text(get_paragraph_text(paragraph), 40),
                paragraph_type=ParagraphType.ABSTRACT_CONTENT.value,
            )

    def _fix_keywords(self, paragraph, index: int):
        """Fix keyword formatting with structured change records."""
        keywords_rules = self.rules.get("keywords", self.rules.get("abstract", {}))
        changes = []
        allowed_properties = self._allowed_properties_for(
            index,
            categories=["body_text"],
            fallback=["font_name", "font_size"],
        )

        expected_font = keywords_rules.get("font_name", "Times New Roman")
        expected_size = keywords_rules.get("font_size", 9)

        for run in paragraph.runs:
            if run.text.strip():
                changes.extend(self._fix_run_formatting(
                    run,
                    expected_font,
                    expected_size,
                    None,
                    allowed_properties=allowed_properties,
                ))

        if changes:
            self._add_property_changes(
                paragraph_index=index,
                location="Keywords",
                change_type="keywords",
                details=changes,
                text_preview=truncate_text(get_paragraph_text(paragraph), 40),
                paragraph_type=ParagraphType.KEYWORDS_CONTENT.value,
            )

    def _fix_caption(self, paragraph, index: int):
        """Fix caption formatting with structured change records."""
        caption_rules = self.rules.get("caption", {})
        changes = []
        allowed_properties = self._allowed_properties_for(
            index,
            categories=["figures", "tables"],
            fallback=["font_name", "font_size", "italic"],
        )

        expected_font = caption_rules.get("font_name", "Times New Roman")
        expected_size = caption_rules.get("font_size", 10)
        expected_italic = caption_rules.get("italic", None)

        for run in paragraph.runs:
            if run.text.strip():
                changes.extend(self._fix_run_formatting(
                    run,
                    expected_font,
                    expected_size,
                    None,
                    expected_italic,
                    allowed_properties=allowed_properties,
                ))

        if changes:
            self._add_property_changes(
                paragraph_index=index,
                location="Caption",
                change_type="caption",
                details=changes,
                text_preview=truncate_text(get_paragraph_text(paragraph), 40),
                paragraph_type=ParagraphType.CAPTION.value,
            )

    def _fix_reference(self, paragraph, index: int):
        """Fix reference formatting with structured change records."""
        reference_rules = self.rules.get("reference", {})
        changes = []
        allowed_properties = self._allowed_properties_for(
            index,
            categories=["references"],
            fallback=["font_name", "font_size"],
        )

        expected_font = reference_rules.get("font_name", "Times New Roman")
        expected_size = reference_rules.get("font_size", 9)

        for run in paragraph.runs:
            if run.text.strip():
                changes.extend(self._fix_run_formatting(
                    run,
                    expected_font,
                    expected_size,
                    None,
                    allowed_properties=allowed_properties,
                ))

        if changes:
            self._add_property_changes(
                paragraph_index=index,
                location="Reference",
                change_type="reference",
                details=changes,
                text_preview=truncate_text(get_paragraph_text(paragraph), 40),
                paragraph_type=ParagraphType.REFERENCE.value,
            )

    def get_fixed_document_bytes(self) -> bytes:
        """Get the fixed document as bytes for download"""
        if not self.document:
            raise ValueError("No document to export")
        
        buffer = BytesIO()
        self.document.save(buffer)
        buffer.seek(0)
        return buffer.getvalue()
    
    def get_changes_summary(self) -> Dict[str, Any]:
        """Get summary of all changes made"""
        summary = {
            "total_changes": len(self.changes),
            "changes_by_type": {},
            "changes_list": []
        }
        
        for change in self.changes:
            change_type = change.change_type
            summary["changes_by_type"][change_type] = \
                summary["changes_by_type"].get(change_type, 0) + 1
            
            summary["changes_list"].append({
                "location": change.location,
                "type": change.change_type,
                "before": change.before,
                "after": change.after,
                "property_name": change.property_name,
                "current_value": change.current_value,
                "target_value": change.target_value,
                "paragraph_type": change.paragraph_type,
                "evidence": change.evidence,
                "preview": change.text_preview
            })
        
        return summary
    
    def get_change_records(self) -> List[ChangeRecord]:
        """Get list of all change records"""
        return self.changes

    def _prepend_highlight_summary(self, document: Document):
        """Add a compact summary at the start of the highlighted document."""
        if not self.changes:
            return

        first_element = document.paragraphs[0]._p if document.paragraphs else None
        summary_lines = [
            "Highlighted Formatting Changes",
            "Yellow highlight marks original text that was changed by the formatter.",
            f"Total formatting properties changed: {len(self.changes)}",
        ]
        for change in self.changes[:20]:
            if change.paragraph_index < 0:
                summary_lines.append(
                    f"- {change.location}: {change.property_name} changed from "
                    f"{change.current_value} to {change.target_value}"
                )
            else:
                summary_lines.append(
                    f"- Paragraph {change.paragraph_index + 1}: {change.property_name} "
                    f"changed from {change.current_value} to {change.target_value}"
                )
        if len(self.changes) > 20:
            summary_lines.append(f"- {len(self.changes) - 20} more changes are listed in the report.")

        for line in reversed(summary_lines):
            paragraph = document.add_paragraph(line)
            if first_element is not None:
                first_element.addprevious(paragraph._p)

    def _run_matches_change(self, run, change: ChangeRecord) -> bool:
        """Return True when a run likely contains the changed property."""
        property_name = change.property_name
        info = get_run_font_info(run)

        if property_name == "font_name":
            current_font = info.get("font_name")
            target_font = change.target_value
            return current_font is None or not is_font_equivalent(current_font, target_font)

        if property_name == "font_size":
            current_size = info.get("font_size")
            target_match = re.search(r"([\d.]+)", change.target_value)
            if not target_match:
                return True
            target_size = float(target_match.group(1))
            return current_size is None or abs(current_size - target_size) > 0.5

        if property_name == "bold":
            target_bold = change.target_value.lower() == "bold"
            return bool(info.get("bold")) != target_bold

        if property_name == "italic":
            target_italic = change.target_value.lower() == "italic"
            return bool(info.get("italic")) != target_italic

        return True

    def get_highlighted_document_bytes(self) -> bytes:
        """
        Get the original document with highlighted changed locations.
        A summary is inserted at the beginning, and changed runs are highlighted in yellow.
        
        Returns:
            Document bytes with yellow highlighting on original changed locations
        """
        if not self.original_document:
            raise ValueError("No document to export")

        highlighted_document = deepcopy(self.original_document)

        for change in self.changes:
            index = change.paragraph_index
            if index < 0 or index >= len(highlighted_document.paragraphs):
                continue

            paragraph = highlighted_document.paragraphs[index]
            matched_any_run = False
            for run in paragraph.runs:
                if not run.text.strip():
                    continue
                if self._run_matches_change(run, change):
                    run.font.highlight_color = WD_COLOR_INDEX.YELLOW
                    matched_any_run = True

            if not matched_any_run:
                for run in paragraph.runs:
                    if run.text.strip():
                        run.font.highlight_color = WD_COLOR_INDEX.YELLOW

        self._prepend_highlight_summary(highlighted_document)

        buffer = BytesIO()
        highlighted_document.save(buffer)
        buffer.seek(0)
        return buffer.getvalue()
