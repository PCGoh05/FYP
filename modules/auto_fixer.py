"""
Auto-Fixer Module
Automatically fixes formatting issues while preserving special formatting
"""

from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_COLOR_INDEX
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from copy import deepcopy
import re
from io import BytesIO

from .utils import (
    load_document, get_paragraph_text, get_paragraph_font_info,
    get_paragraph_alignment, set_margins, truncate_text, is_font_equivalent,
    get_run_font_info
)
from .paragraph_classifier import (
    ParagraphClassifier, ParagraphType, ClassifiedParagraph
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
        """Build a paragraph-to-category map from detected issues."""
        self._issue_map = {}
        for category, issues in self.issues_by_category.items():
            for issue in issues:
                para_index = getattr(issue, "paragraph_index", -1)
                if para_index is None or para_index < 0:
                    continue
                self._issue_map.setdefault(para_index, set()).add(category)

    def _should_fix_category(self, index: int, categories: List[str]) -> bool:
        """Return True when a paragraph has a detected issue for the target categories."""
        if not self._has_explicit_issues:
            return True
        found_categories = self._issue_map.get(index, set())
        return any(category in found_categories for category in categories)

    def _has_category_issue(self, category: str) -> bool:
        """Return True when the checker reported at least one issue in a category."""
        if not self._has_explicit_issues:
            return True
        return bool(self.issues_by_category.get(category))
    
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
        
        # Fix paragraphs based on their classification
        for i, para in enumerate(self.document.paragraphs):
            classification = self._classification_map.get(i)
            
            if not classification or not classification.should_fix:
                continue
            
            para_type = classification.paragraph_type
            
            if para_type == ParagraphType.JOURNAL_HEADER and self._is_journal_title_header(classification.text):
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
        """Fix page margins"""
        expected_margins = self.rules.get("margins", {})
        
        for section in self.document.sections:
            changes_made = []
            
            # Check and fix each margin
            if section.left_margin:
                current_left = section.left_margin.inches
                expected_left = expected_margins.get("left", 1.0)
                if abs(current_left - expected_left) > 0.05:
                    section.left_margin = Inches(expected_left)
                    changes_made.append(f"Left: {current_left:.2f}in → {expected_left:.2f}in")
            
            if section.right_margin:
                current_right = section.right_margin.inches
                expected_right = expected_margins.get("right", 1.0)
                if abs(current_right - expected_right) > 0.05:
                    section.right_margin = Inches(expected_right)
                    changes_made.append(f"Right: {current_right:.2f}in → {expected_right:.2f}in")
            
            if section.top_margin:
                current_top = section.top_margin.inches
                expected_top = expected_margins.get("top", 1.0)
                if abs(current_top - expected_top) > 0.05:
                    section.top_margin = Inches(expected_top)
                    changes_made.append(f"Top: {current_top:.2f}in → {expected_top:.2f}in")
            
            if section.bottom_margin:
                current_bottom = section.bottom_margin.inches
                expected_bottom = expected_margins.get("bottom", 1.0)
                if abs(current_bottom - expected_bottom) > 0.05:
                    section.bottom_margin = Inches(expected_bottom)
                    changes_made.append(f"Bottom: {current_bottom:.2f}in → {expected_bottom:.2f}in")
            
            if changes_made:
                self.changes.append(ChangeRecord(
                    paragraph_index=-1,
                    location="Page Margins",
                    change_type="margins",
                    before=", ".join([c.split(" → ")[0] for c in changes_made]),
                    after=", ".join([c.split(" → ")[1] for c in changes_made]),
                    text_preview="Document margins adjusted"
                ))
    
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

        expected_font = header_rules.get("font_name", "Palatino Linotype")
        expected_size = header_rules.get("font_size", 24)
        expected_bold = header_rules.get("bold", True)
        expected_alignment = header_rules.get("alignment", "CENTER")

        if current_alignment != expected_alignment:
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

    def _fix_title(self, paragraph, index: int):
        """Fix paper title formatting"""
        title_rules = self.rules.get("title", {})
        changes = []
        
        # Get current formatting
        current_info = get_paragraph_font_info(paragraph)
        current_alignment = get_paragraph_alignment(paragraph)
        
        expected_font = title_rules.get("font_name", "Times New Roman")
        expected_size = title_rules.get("font_size", 24)
        # Only apply bold if EXPLICITLY set in template rules
        expected_bold = title_rules.get("bold", None)
        expected_alignment = title_rules.get("alignment", "CENTER")
        
        # Fix alignment
        if current_alignment != expected_alignment:
            alignment_value = ALIGNMENT_REVERSE_MAP.get(expected_alignment, 1)
            paragraph.alignment = WD_ALIGN_PARAGRAPH(alignment_value)
            changes.append(f"Alignment: {current_alignment} → {expected_alignment}")
        
        # Fix runs while preserving special formatting
        for run in paragraph.runs:
            if run.text.strip():
                run_changes = self._fix_run_formatting(
                    run, expected_font, expected_size, expected_bold,
                    expected_strike=False  # Explicitly remove strikethrough
                )
                changes.extend(run_changes)
        
        if changes:
            self.changes.append(ChangeRecord(
                paragraph_index=index,
                location="Paper Title",
                change_type="title",
                before=current_info.get("font_name", "Unknown") + f" {current_info.get('font_size', '?')}pt",
                after=f"{expected_font} {expected_size}pt Bold",
                text_preview=truncate_text(get_paragraph_text(paragraph), 50)
            ))
    
    def _fix_heading(self, paragraph, index: int):
        """Fix section heading formatting"""
        heading_rules = self.rules.get("heading", {})
        changes = []
        
        current_info = get_paragraph_font_info(paragraph)
        
        expected_font = heading_rules.get("font_name", "Times New Roman")
        expected_size = heading_rules.get("font_size", 14)
        # Only apply bold if EXPLICITLY set in template rules, don't assume
        expected_bold = heading_rules.get("bold", None)
        
        for run in paragraph.runs:
            if run.text.strip():
                run_changes = self._fix_run_formatting(
                    run, expected_font, expected_size, expected_bold,
                    expected_strike=False  # Explicitly remove strikethrough
                )
                changes.extend(run_changes)
        
        if changes:
            self.changes.append(ChangeRecord(
                paragraph_index=index,
                location=f"Section Heading",
                change_type="heading",
                before=f"{current_info.get('font_name', 'Unknown')} {current_info.get('font_size', '?')}pt",
                after=f"{expected_font} {expected_size}pt Bold",
                text_preview=truncate_text(get_paragraph_text(paragraph), 40)
            ))
    
    def _fix_body_text(self, paragraph, index: int):
        """Fix body text formatting"""
        body_rules = self.rules.get("body", {})
        changes = []
        
        current_info = get_paragraph_font_info(paragraph)
        
        expected_font = body_rules.get("font_name", "Times New Roman")
        expected_size = body_rules.get("font_size", 12)
        
        for run in paragraph.runs:
            if run.text.strip():
                run_changes = self._fix_run_formatting(
                    run, expected_font, expected_size, None  # Don't force bold for body
                )
                changes.extend(run_changes)
        
        # Fix line spacing if specified
        expected_spacing = body_rules.get("line_spacing")
        if expected_spacing:
            pf = paragraph.paragraph_format
            if pf.line_spacing != expected_spacing:
                pf.line_spacing = expected_spacing
                changes.append(f"Line spacing adjusted")
        
        if changes:
            self.changes.append(ChangeRecord(
                paragraph_index=index,
                location=f"Body Text (Para {index + 1})",
                change_type="body",
                before=f"{current_info.get('font_name', 'Unknown')} {current_info.get('font_size', '?')}pt",
                after=f"{expected_font} {expected_size}pt",
                text_preview=truncate_text(get_paragraph_text(paragraph), 40)
            ))
    
    def _fix_abstract(self, paragraph, index: int):
        """Fix abstract content formatting - uses ABSTRACT rules (not body)"""
        abstract_rules = self.rules.get("abstract", {})
        changes = []
        
        current_info = get_paragraph_font_info(paragraph)
        
        expected_font = abstract_rules.get("font_name", "Times New Roman")
        expected_size = abstract_rules.get("font_size", 9)  # Abstract is typically 9pt
        
        for run in paragraph.runs:
            if run.text.strip():
                run_changes = self._fix_run_formatting(
                    run, expected_font, expected_size, None
                )
                changes.extend(run_changes)
        
        if changes:
            self.changes.append(ChangeRecord(
                paragraph_index=index,
                location=f"Abstract",
                change_type="abstract",
                before=f"{current_info.get('font_name', 'Unknown')} {current_info.get('font_size', '?')}pt",
                after=f"{expected_font} {expected_size}pt",
                text_preview=truncate_text(get_paragraph_text(paragraph), 40)
            ))
    
    def _fix_keywords(self, paragraph, index: int):
        """Fix keywords content formatting - uses KEYWORDS rules"""
        # Keywords typically use same format as abstract
        keywords_rules = self.rules.get("keywords", self.rules.get("abstract", {}))
        changes = []
        
        current_info = get_paragraph_font_info(paragraph)
        
        expected_font = keywords_rules.get("font_name", "Times New Roman")
        expected_size = keywords_rules.get("font_size", 9)  # Keywords is typically 9pt
        
        for run in paragraph.runs:
            if run.text.strip():
                run_changes = self._fix_run_formatting(
                    run, expected_font, expected_size, None
                )
                changes.extend(run_changes)
        
        if changes:
            self.changes.append(ChangeRecord(
                paragraph_index=index,
                location=f"Keywords",
                change_type="keywords",
                before=f"{current_info.get('font_name', 'Unknown')} {current_info.get('font_size', '?')}pt",
                after=f"{expected_font} {expected_size}pt",
                text_preview=truncate_text(get_paragraph_text(paragraph), 40)
            ))
    
    def _fix_caption(self, paragraph, index: int):
        """Fix figure/table caption formatting"""
        caption_rules = self.rules.get("caption", {})
        changes = []
        
        current_info = get_paragraph_font_info(paragraph)
        
        expected_font = caption_rules.get("font_name", "Times New Roman")
        expected_size = caption_rules.get("font_size", 10)
        # Only apply italic if EXPLICITLY set in template rules
        expected_italic = caption_rules.get("italic", None)
        
        for run in paragraph.runs:
            if run.text.strip():
                run_changes = self._fix_run_formatting(
                    run, expected_font, expected_size, None, expected_italic
                )
                changes.extend(run_changes)
        
        if changes:
            self.changes.append(ChangeRecord(
                paragraph_index=index,
                location="Caption",
                change_type="caption",
                before=f"{current_info.get('font_name', 'Unknown')} {current_info.get('font_size', '?')}pt",
                after=f"{expected_font} {expected_size}pt Italic",
                text_preview=truncate_text(get_paragraph_text(paragraph), 40)
            ))
    
    def _fix_reference(self, paragraph, index: int):
        """Fix reference entry formatting"""
        ref_rules = self.rules.get("reference", {})
        changes = []
        
        current_info = get_paragraph_font_info(paragraph)
        
        expected_font = ref_rules.get("font_name", "Times New Roman")
        expected_size = ref_rules.get("font_size", 10)
        
        for run in paragraph.runs:
            if run.text.strip():
                run_changes = self._fix_run_formatting(
                    run, expected_font, expected_size, None
                )
                changes.extend(run_changes)
        
        if changes:
            self.changes.append(ChangeRecord(
                paragraph_index=index,
                location="Reference",
                change_type="reference",
                before=f"{current_info.get('font_name', 'Unknown')} {current_info.get('font_size', '?')}pt",
                after=f"{expected_font} {expected_size}pt",
                text_preview=truncate_text(get_paragraph_text(paragraph), 40)
            ))
    
    def _fix_run_formatting(self, run, expected_font: str, expected_size: float,
                           expected_bold: Optional[bool] = None,
                           expected_italic: Optional[bool] = None,
                           expected_strike: Optional[bool] = None) -> List[str]:
        """
        Fix formatting of a single run while preserving special formatting
        
        Preserves: italic (unless overridden), underline, subscript, superscript, strikethrough (unless overridden)
        
        IMPROVED: Only applies corrections when there's a real difference and values are known
        """
        changes = []
        font = run.font
        
        # Store special formatting to preserve
        preserve_italic = font.italic if expected_italic is None else None
        preserve_underline = font.underline
        preserve_subscript = font.subscript
        preserve_superscript = font.superscript
        preserve_strike = font.strike if expected_strike is None else None
        
        # Fix font name - ALWAYS apply if expected is set
        # Previously: skipped if current was None (inherited), causing many paragraphs to be missed
        current_font = font.name
        if expected_font is not None:
            if current_font is None or not is_font_equivalent(current_font, expected_font):
                font.name = expected_font
                if current_font is not None:
                    changes.append(f"Font: {current_font} → {expected_font}")
                else:
                    changes.append(f"Font: (inherited) → {expected_font}")
        
        # Fix font size - ALWAYS apply if expected is set
        # Previously: skipped if current was None (inherited), causing many paragraphs to be missed
        current_size = font.size.pt if font.size else None
        if expected_size is not None:
            if current_size is None or abs(current_size - expected_size) > 0.5:
                font.size = Pt(expected_size)
                if current_size is not None:
                    changes.append(f"Size: {current_size}pt → {expected_size}pt")
                else:
                    changes.append(f"Size: (inherited) → {expected_size}pt")
        
        # Fix bold if specified
        if expected_bold is not None:
            current_bold = font.bold
            # Only change if explicitly different (treat None as False for comparison)
            current_bold_val = bool(current_bold) if current_bold is not None else False
            if current_bold_val != expected_bold:
                font.bold = expected_bold
                changes.append(f"Bold: {current_bold} → {expected_bold}")
        
        # Fix italic if specified
        if expected_italic is not None:
            current_italic = font.italic
            current_italic_val = bool(current_italic) if current_italic is not None else False
            if current_italic_val != expected_italic:
                font.italic = expected_italic
                changes.append(f"Italic: {current_italic} → {expected_italic}")
        else:
            # Preserve original italic
            font.italic = preserve_italic
        
        # Fix strike if specified (to force remove it)
        if expected_strike is not None:
            if font.strike != expected_strike:
                font.strike = expected_strike
        else:
            font.strike = preserve_strike
            
        # Restore preserved special formatting
        font.underline = preserve_underline
        font.subscript = preserve_subscript
        font.superscript = preserve_superscript
        
        return changes
    
    def _fix_run_formatting(self, run, expected_font: str, expected_size: float,
                           expected_bold: Optional[bool] = None,
                           expected_italic: Optional[bool] = None,
                           expected_strike: Optional[bool] = None) -> List[Dict[str, str]]:
        """Fix a run and return structured property changes."""
        changes = []
        font = run.font

        preserve_italic = font.italic if expected_italic is None else None
        preserve_underline = font.underline
        preserve_subscript = font.subscript
        preserve_superscript = font.superscript
        preserve_strike = font.strike if expected_strike is None else None

        current_font = font.name
        if expected_font is not None:
            if current_font is None or not is_font_equivalent(current_font, expected_font):
                font.name = expected_font
                changes.append({
                    "property_name": "font_name",
                    "current_value": current_font or "(inherited)",
                    "target_value": expected_font,
                    "evidence": "Run font did not match target rule",
                })

        current_size = font.size.pt if font.size else None
        if expected_size is not None:
            if current_size is None or abs(current_size - expected_size) > 0.5:
                font.size = Pt(expected_size)
                changes.append({
                    "property_name": "font_size",
                    "current_value": f"{current_size} pt" if current_size is not None else "(inherited)",
                    "target_value": f"{expected_size} pt",
                    "evidence": "Run font size did not match target rule",
                })

        if expected_bold is not None:
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

        if expected_italic is not None:
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

        if expected_strike is not None:
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

        expected_font = title_rules.get("font_name", "Times New Roman")
        expected_size = title_rules.get("font_size", 24)
        expected_bold = title_rules.get("bold", None)
        expected_alignment = title_rules.get("alignment", "CENTER")

        if current_alignment != expected_alignment:
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
                    expected_strike=False,
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
        heading_rules = self.rules.get("heading", {})
        changes = []

        expected_font = heading_rules.get("font_name", "Times New Roman")
        expected_size = heading_rules.get("font_size", 14)
        expected_bold = heading_rules.get("bold", None)

        for run in paragraph.runs:
            if run.text.strip():
                changes.extend(self._fix_run_formatting(
                    run,
                    expected_font,
                    expected_size,
                    expected_bold,
                    expected_strike=False,
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

    def _fix_body_text(self, paragraph, index: int):
        """Fix body text formatting with structured change records."""
        body_rules = self.rules.get("body", {})
        changes = []

        expected_font = body_rules.get("font_name", "Times New Roman")
        expected_size = body_rules.get("font_size", 12)

        for run in paragraph.runs:
            if run.text.strip():
                changes.extend(self._fix_run_formatting(run, expected_font, expected_size, None))

        expected_spacing = body_rules.get("line_spacing")
        if expected_spacing:
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

        expected_font = abstract_rules.get("font_name", "Times New Roman")
        expected_size = abstract_rules.get("font_size", 9)

        for run in paragraph.runs:
            if run.text.strip():
                changes.extend(self._fix_run_formatting(run, expected_font, expected_size, None))

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

        expected_font = keywords_rules.get("font_name", "Times New Roman")
        expected_size = keywords_rules.get("font_size", 9)

        for run in paragraph.runs:
            if run.text.strip():
                changes.extend(self._fix_run_formatting(run, expected_font, expected_size, None))

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

        expected_font = reference_rules.get("font_name", "Times New Roman")
        expected_size = reference_rules.get("font_size", 10)

        for run in paragraph.runs:
            if run.text.strip():
                changes.extend(self._fix_run_formatting(run, expected_font, expected_size, None))

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
