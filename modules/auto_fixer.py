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
    get_paragraph_alignment, set_margins, truncate_text
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


class AutoFixer:
    """
    Automatically fixes formatting issues in a manuscript
    while preserving special formatting (italic, underline, subscript, etc.)
    """
    
    def __init__(self, rules: Dict[str, Any], classifications: List[ClassifiedParagraph]):
        """
        Initialize auto-fixer with template rules and paragraph classifications
        
        Args:
            rules: Template formatting rules
            classifications: List of classified paragraphs from ParagraphClassifier
        """
        self.rules = rules
        self.classifications = classifications
        self.changes: List[ChangeRecord] = []
        self.document = None
        self._classification_map: Dict[int, ClassifiedParagraph] = {}
    
    def load_manuscript(self, file_path_or_bytes):
        """Load the manuscript to fix"""
        self.document = load_document(file_path_or_bytes)
        # Create index map for quick lookup
        self._classification_map = {cp.index: cp for cp in self.classifications}
        return self
    
    def fix_all(self) -> Tuple[Document, List[ChangeRecord]]:
        """
        Apply all formatting fixes to the document
        
        Returns:
            Tuple of (fixed document, list of changes made)
        """
        if not self.document:
            raise ValueError("No document loaded. Call load_manuscript() first.")
        
        self.changes = []
        
        # Fix margins first (affects entire document)
        self._fix_margins()
        
        # Fix paragraphs based on their classification
        for i, para in enumerate(self.document.paragraphs):
            classification = self._classification_map.get(i)
            
            if not classification or not classification.should_fix:
                continue
            
            para_type = classification.paragraph_type
            
            if para_type == ParagraphType.PAPER_TITLE:
                self._fix_title(para, i)
            elif para_type == ParagraphType.SECTION_HEADING:
                self._fix_heading(para, i)
            elif para_type == ParagraphType.BODY:
                self._fix_body_text(para, i)
            elif para_type == ParagraphType.ABSTRACT_CONTENT:
                self._fix_abstract(para, i)  # Use abstract rules (9pt)
            elif para_type == ParagraphType.KEYWORDS_CONTENT:
                self._fix_keywords(para, i)  # Use keywords rules
            elif para_type == ParagraphType.CAPTION:
                self._fix_caption(para, i)
            elif para_type == ParagraphType.REFERENCE:
                self._fix_reference(para, i)
        
        return self.document, self.changes
    
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
    
    def _fix_title(self, paragraph, index: int):
        """Fix paper title formatting"""
        title_rules = self.rules.get("title", {})
        changes = []
        
        # Get current formatting
        current_info = get_paragraph_font_info(paragraph)
        current_alignment = get_paragraph_alignment(paragraph)
        
        expected_font = title_rules.get("font_name", "Times New Roman")
        expected_size = title_rules.get("font_size", 24)
        expected_bold = title_rules.get("bold", True)
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
        expected_bold = heading_rules.get("bold", True)
        
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
        expected_italic = caption_rules.get("italic", True)
        
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
        
        # Fix font name - only if current is known and different
        current_font = font.name
        if current_font is not None and expected_font is not None:
            # Normalize for comparison (case-insensitive, trim spaces)
            current_normalized = current_font.lower().strip()
            expected_normalized = expected_font.lower().strip()
            if current_normalized != expected_normalized:
                font.name = expected_font
                changes.append(f"Font: {current_font} → {expected_font}")
        elif current_font is None and expected_font is not None:
            # Apply expected font if current is unknown
            font.name = expected_font
            changes.append(f"Font: (inherited) → {expected_font}")
        
        # Fix font size - only if current is known and different
        current_size = font.size.pt if font.size else None
        if current_size is not None and expected_size is not None:
            # Allow 0.5pt tolerance
            if abs(current_size - expected_size) > 0.5:
                font.size = Pt(expected_size)
                changes.append(f"Size: {current_size}pt → {expected_size}pt")
        elif current_size is None and expected_size is not None:
            # Apply expected size if current is unknown
            font.size = Pt(expected_size)
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
                "preview": change.text_preview
            })
        
        return summary
    
    def get_change_records(self) -> List[ChangeRecord]:
        """Get list of all change records"""
        return self.changes
    
    def get_highlighted_document_bytes(self) -> bytes:
        """
        Get the fixed document with highlighted changes.
        Changed paragraphs are highlighted in yellow for easy identification.
        
        Returns:
            Document bytes with yellow highlighting on changed paragraphs
        """
        if not self.document:
            raise ValueError("No document to export")
        
        from docx.oxml.ns import qn
        from docx.oxml import OxmlElement
        
        # Get indices of changed paragraphs
        changed_indices = {change.paragraph_index for change in self.changes if change.paragraph_index >= 0}
        
        # Apply yellow highlight to changed paragraphs
        for idx in changed_indices:
            if idx < len(self.document.paragraphs):
                para = self.document.paragraphs[idx]
                for run in para.runs:
                    # Set yellow highlight
                    run.font.highlight_color = WD_COLOR_INDEX.YELLOW
        
        buffer = BytesIO()
        self.document.save(buffer)
        buffer.seek(0)
        return buffer.getvalue()
