"""
Manuscript Checker Module
Checks manuscript formatting against template rules
"""

from docx import Document
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
import re

from .utils import (
    load_document, get_paragraph_text, get_paragraph_font_info,
    get_paragraph_alignment, get_margins, get_line_spacing,
    detect_reference_style, calculate_compliance_score,
    truncate_text
)
from .paragraph_classifier import ParagraphClassifier, ParagraphType, ClassifiedParagraph
from config import REQUIRED_SECTIONS, CAPTION_PATTERNS


@dataclass
class FormatIssue:
    """Represents a formatting issue found in the manuscript"""
    category: str
    location: str
    paragraph_index: int
    description: str
    current_value: str
    expected_value: str
    severity: str = "warning"  # "error", "warning", "info"
    text_preview: str = ""


@dataclass
class CheckResult:
    """Result of manuscript check"""
    is_compliant: bool
    compliance_score: float
    total_issues: int
    issues_by_category: Dict[str, List[FormatIssue]]
    classifications: List[ClassifiedParagraph]
    document_structure: Dict[str, bool]
    statistics: Dict[str, Any]


class ManuscriptChecker:
    """
    Checks manuscript formatting against extracted template rules
    Performs 10 category checks and calculates compliance score
    """
    
    CATEGORIES = [
        "margins",
        "title",
        "body_text",
        "headings",
        "structure",
        "tables",
        "figures",
        "references",
        "line_spacing",
        "other"
    ]
    
    def __init__(self, rules: Dict[str, Any], llm_integration=None):
        """Initialize checker with template rules"""
        self.rules = rules
        self.llm = llm_integration
        self.document = None
        self.classifier = ParagraphClassifier(llm_integration)
        self.issues: Dict[str, List[FormatIssue]] = {cat: [] for cat in self.CATEGORIES}
        self.classifications: List[ClassifiedParagraph] = []
    
    def load_manuscript(self, file_path_or_bytes):
        """Load the manuscript to check"""
        self.document = load_document(file_path_or_bytes)
        return self
    
    def check_all(self) -> CheckResult:
        """Perform all format checks"""
        if not self.document:
            raise ValueError("No manuscript loaded. Call load_manuscript() first.")
        
        # Reset issues
        self.issues = {cat: [] for cat in self.CATEGORIES}
        
        # Classify paragraphs first
        self.classifications = self.classifier.classify_document(self.document)
        
        # Run all checks
        self._check_margins()
        self._check_title()
        self._check_body_text()
        self._check_headings()
        structure = self._check_document_structure()
        self._check_tables()
        self._check_figures()
        self._check_references()
        self._check_line_spacing()
        
        # Calculate compliance score
        score = calculate_compliance_score(self.issues)
        total_issues = sum(len(issues) for issues in self.issues.values())
        
        # Gather statistics
        stats = self._gather_statistics()
        
        return CheckResult(
            is_compliant=total_issues == 0,
            compliance_score=score,
            total_issues=total_issues,
            issues_by_category=self.issues,
            classifications=self.classifications,
            document_structure=structure,
            statistics=stats
        )
    
    def _add_issue(self, category: str, location: str, para_index: int,
                   description: str, current: str, expected: str,
                   severity: str = "warning", text_preview: str = ""):
        """Add a formatting issue"""
        issue = FormatIssue(
            category=category,
            location=location,
            paragraph_index=para_index,
            description=description,
            current_value=current,
            expected_value=expected,
            severity=severity,
            text_preview=text_preview
        )
        self.issues[category].append(issue)
    
    def _check_margins(self):
        """Check page margins against template"""
        current_margins = get_margins(self.document)
        expected_margins = self.rules.get("margins", {})
        
        margin_names = ["left", "right", "top", "bottom"]
        
        for margin in margin_names:
            current = current_margins.get(margin, 1.0)
            expected = expected_margins.get(margin, 1.0)
            
            # Allow small tolerance (0.05 inches)
            if abs(current - expected) > 0.05:
                self._add_issue(
                    category="margins",
                    location=f"{margin.capitalize()} Margin",
                    para_index=-1,
                    description=f"{margin.capitalize()} margin does not match template",
                    current=f"{current:.2f} inches",
                    expected=f"{expected:.2f} inches",
                    severity="error"
                )
    
    def _check_title(self):
        """Check paper title formatting"""
        title_rules = self.rules.get("title", {})
        
        # Find the paper title
        for cp in self.classifications:
            if cp.paragraph_type == ParagraphType.PAPER_TITLE:
                font_info = cp.font_info
                alignment = cp.alignment
                
                # Check font name (case-insensitive comparison)
                expected_font = title_rules.get("font_name", "Times New Roman")
                current_font = font_info.get("font_name")
                if current_font:
                    # Normalize for comparison
                    current_normalized = current_font.lower().strip()
                    expected_normalized = expected_font.lower().strip()
                    if current_normalized != expected_normalized:
                        self._add_issue(
                            category="title",
                            location="Paper Title",
                            para_index=cp.index,
                            description="Title font does not match template",
                            current=current_font,
                            expected=expected_font,
                            severity="error",
                            text_preview=truncate_text(cp.text, 60)
                        )
                
                # Check font size (with 0.5pt tolerance)
                expected_size = title_rules.get("font_size", 24)
                current_size = font_info.get("font_size")
                if current_size and abs(current_size - expected_size) > 0.5:
                    self._add_issue(
                        category="title",
                        location="Paper Title",
                        para_index=cp.index,
                        description="Title font size does not match template",
                        current=f"{current_size}pt",
                        expected=f"{expected_size}pt",
                        severity="error",
                        text_preview=truncate_text(cp.text, 60)
                    )
                
                # Check bold
                expected_bold = title_rules.get("bold", True)
                current_bold = font_info.get("bold", False)
                if current_bold != expected_bold:
                    self._add_issue(
                        category="title",
                        location="Paper Title",
                        para_index=cp.index,
                        description="Title bold formatting does not match template",
                        current="Bold" if current_bold else "Not Bold",
                        expected="Bold" if expected_bold else "Not Bold",
                        severity="warning",
                        text_preview=truncate_text(cp.text, 60)
                    )
                
                # Check alignment
                expected_align = title_rules.get("alignment", "CENTER")
                if alignment != expected_align:
                    self._add_issue(
                        category="title",
                        location="Paper Title",
                        para_index=cp.index,
                        description="Title alignment does not match template",
                        current=alignment,
                        expected=expected_align,
                        severity="warning",
                        text_preview=truncate_text(cp.text, 60)
                    )
                
                break  # Only check the first title
    
    def _check_body_text(self):
        """Check body text formatting - ENHANCED with tolerance"""
        body_rules = self.rules.get("body", {})
        expected_font = body_rules.get("font_name", "Times New Roman")
        expected_size = body_rules.get("font_size", 12)
        
        # Font size tolerance (allow ±0.5pt difference)
        size_tolerance = 0.5
        
        # Common font name variations that are equivalent
        font_equivalents = {
            "times new roman": ["times", "times-roman", "timesnewroman", "times new roman"],
            "arial": ["arial", "arial mt", "arialmt"],
            "calibri": ["calibri", "calibri light"],
        }
        
        def fonts_match(current, expected):
            if not current or not expected:
                return True  # Skip if font not detected
            current_lower = current.lower().strip()
            expected_lower = expected.lower().strip()
            if current_lower == expected_lower:
                return True
            # Check equivalents
            for base, variants in font_equivalents.items():
                if expected_lower in variants and current_lower in variants:
                    return True
            return False
        
        issues_found = 0
        max_issues_to_report = 10  # Limit to avoid too many issues
        
        for cp in self.classifications:
            if cp.paragraph_type == ParagraphType.BODY:
                font_info = cp.font_info
                
                # Check font name
                current_font = font_info.get("font_name")
                if current_font and not fonts_match(current_font, expected_font):
                    if issues_found < max_issues_to_report:
                        self._add_issue(
                            category="body_text",
                            location=f"Paragraph {cp.index + 1}",
                            para_index=cp.index,
                            description="Body text font does not match template",
                            current=current_font,
                            expected=expected_font,
                            severity="warning",
                            text_preview=truncate_text(cp.text, 50)
                        )
                    issues_found += 1
                
                # Check font size with tolerance
                current_size = font_info.get("font_size")
                if current_size and abs(current_size - expected_size) > size_tolerance:
                    if issues_found < max_issues_to_report:
                        self._add_issue(
                            category="body_text",
                            location=f"Paragraph {cp.index + 1}",
                            para_index=cp.index,
                            description="Body text font size does not match template",
                            current=f"{current_size}pt",
                            expected=f"{expected_size}pt",
                            severity="warning",
                            text_preview=truncate_text(cp.text, 50)
                        )
                    issues_found += 1
        
        # Add summary if many issues
        if issues_found > max_issues_to_report:
            self._add_issue(
                category="body_text",
                location="Multiple Paragraphs",
                para_index=-1,
                description=f"Additional {issues_found - max_issues_to_report} body text formatting issues found",
                current="Various",
                expected=f"{expected_font} {expected_size}pt",
                severity="info"
            )
        
        # Check abstract content formatting (usually smaller font like 9pt)
        self._check_abstract_content()
        
        # Check keywords content formatting (usually same as abstract)
        self._check_keywords_content()
    
    def _check_abstract_content(self):
        """Check abstract content formatting"""
        abstract_rules = self.rules.get("abstract", {})
        expected_font = abstract_rules.get("font_name", "Times New Roman")
        expected_size = abstract_rules.get("font_size", 9)
        size_tolerance = 0.5
        
        for cp in self.classifications:
            if cp.paragraph_type == ParagraphType.ABSTRACT_CONTENT:
                font_info = cp.font_info
                
                # Check font size
                current_size = font_info.get("font_size")
                if current_size and abs(current_size - expected_size) > size_tolerance:
                    self._add_issue(
                        category="body_text",
                        location="Abstract",
                        para_index=cp.index,
                        description="Abstract font size does not match template",
                        current=f"{current_size}pt",
                        expected=f"{expected_size}pt",
                        severity="warning",
                        text_preview=truncate_text(cp.text, 50)
                    )
    
    def _check_keywords_content(self):
        """Check keywords content formatting"""
        # Keywords typically use same format as abstract
        keywords_rules = self.rules.get("keywords", self.rules.get("abstract", {}))
        expected_font = keywords_rules.get("font_name", "Times New Roman")
        expected_size = keywords_rules.get("font_size", 9)
        size_tolerance = 0.5
        
        for cp in self.classifications:
            if cp.paragraph_type == ParagraphType.KEYWORDS_CONTENT:
                font_info = cp.font_info
                
                # Check font size
                current_size = font_info.get("font_size")
                if current_size and abs(current_size - expected_size) > size_tolerance:
                    self._add_issue(
                        category="body_text",
                        location="Keywords",
                        para_index=cp.index,
                        description="Keywords font size does not match template",
                        current=f"{current_size}pt",
                        expected=f"{expected_size}pt",
                        severity="warning",
                        text_preview=truncate_text(cp.text, 50)
                    )
    
    def _check_headings(self):
        """Check section heading formatting"""
        heading_rules = self.rules.get("heading", {})
        expected_font = heading_rules.get("font_name", "Times New Roman")
        expected_size = heading_rules.get("font_size", 14)
        expected_bold = heading_rules.get("bold", True)
        
        for cp in self.classifications:
            if cp.paragraph_type == ParagraphType.SECTION_HEADING:
                font_info = cp.font_info
                
                # Check font
                current_font = font_info.get("font_name")
                if current_font and current_font != expected_font:
                    self._add_issue(
                        category="headings",
                        location=f"Heading: {truncate_text(cp.text, 30)}",
                        para_index=cp.index,
                        description="Heading font does not match template",
                        current=current_font,
                        expected=expected_font,
                        severity="warning",
                        text_preview=cp.text
                    )
                
                # Check size
                current_size = font_info.get("font_size")
                if current_size and current_size != expected_size:
                    self._add_issue(
                        category="headings",
                        location=f"Heading: {truncate_text(cp.text, 30)}",
                        para_index=cp.index,
                        description="Heading font size does not match template",
                        current=f"{current_size}pt",
                        expected=f"{expected_size}pt",
                        severity="warning",
                        text_preview=cp.text
                    )
                
                # Check bold - handle None values (None means not bold)
                current_bold = bool(font_info.get("bold"))
                expected_bold_val = bool(heading_rules.get("bold", False))
                if current_bold != expected_bold_val:
                    self._add_issue(
                        category="headings",
                        location=f"Heading: {truncate_text(cp.text, 30)}",
                        para_index=cp.index,
                        description="Heading bold formatting does not match template",
                        current="Bold" if current_bold else "Not Bold",
                        expected="Bold" if expected_bold_val else "Not Bold",
                        severity="warning",
                        text_preview=cp.text
                    )
    
    def _check_document_structure(self) -> Dict[str, bool]:
        """Check for required document sections"""
        found_sections = {section: False for section in REQUIRED_SECTIONS}
        
        for cp in self.classifications:
            text_lower = cp.text.lower().strip()
            
            # Check for abstract - include ABSTRACT_CONTENT type
            if "abstract" in text_lower or cp.paragraph_type in [
                ParagraphType.ABSTRACT_LABEL, ParagraphType.ABSTRACT_CONTENT
            ]:
                found_sections["abstract"] = True
            
            # Check for keywords - include KEYWORDS_CONTENT type
            if any(kw in text_lower for kw in ["keywords", "key words"]) or \
               cp.paragraph_type == ParagraphType.KEYWORDS_CONTENT:
                found_sections["keywords"] = True
            
            if "introduction" in text_lower:
                found_sections["introduction"] = True
            
            if "conclusion" in text_lower:
                found_sections["conclusion"] = True
            
            if text_lower in ["references", "bibliography", "works cited"] or \
               cp.paragraph_type == ParagraphType.REFERENCE:
                found_sections["references"] = True
        
        # Report missing sections
        for section, found in found_sections.items():
            if not found:
                self._add_issue(
                    category="structure",
                    location="Document Structure",
                    para_index=-1,
                    description=f"Missing required section: {section.capitalize()}",
                    current="Not Found",
                    expected=f"{section.capitalize()} section",
                    severity="error"
                )
        
        return found_sections
    
    def _check_tables(self):
        """Check tables in the document"""
        tables = self.document.tables
        
        if not tables:
            # Check if tables are mentioned in text but not found
            for cp in self.classifications:
                if re.search(r'table\s*\d+', cp.text.lower()):
                    self._add_issue(
                        category="tables",
                        location="Tables",
                        para_index=-1,
                        description="Table reference found but no tables in document",
                        current="No tables",
                        expected="Tables matching references",
                        severity="warning"
                    )
                    break
        else:
            # Check table captions
            caption_count = sum(
                1 for cp in self.classifications 
                if cp.paragraph_type == ParagraphType.CAPTION and
                re.match(r'^table\s*\d+', cp.text.lower())
            )
            
            if caption_count < len(tables):
                self._add_issue(
                    category="tables",
                    location="Table Captions",
                    para_index=-1,
                    description="Some tables may be missing captions",
                    current=f"{caption_count} captions",
                    expected=f"{len(tables)} captions",
                    severity="warning"
                )
    
    def _check_figures(self):
        """Check figures in the document"""
        # Count figure captions
        figure_captions = [
            cp for cp in self.classifications
            if cp.paragraph_type == ParagraphType.CAPTION and
            re.match(r'^(figure|fig\.?)\s*\d+', cp.text.lower())
        ]
        
        # Check inline shapes (images)
        image_count = 0
        for para in self.document.paragraphs:
            for run in para.runs:
                if run._element.xpath('.//a:blip'):
                    image_count += 1
        
        # Also check for figures in document's inline shapes
        try:
            for shape in self.document.inline_shapes:
                image_count += 1
        except Exception:
            pass
        
        if image_count > 0 and len(figure_captions) < image_count:
            self._add_issue(
                category="figures",
                location="Figure Captions",
                para_index=-1,
                description="Some figures may be missing captions",
                current=f"{len(figure_captions)} captions",
                expected=f"{image_count} captions (for {image_count} images)",
                severity="warning"
            )
        
        # Check caption formatting
        caption_rules = self.rules.get("caption", {})
        expected_font = caption_rules.get("font_name", "Times New Roman")
        expected_size = caption_rules.get("font_size", 10)
        
        for cp in figure_captions:
            current_font = cp.font_info.get("font_name")
            current_size = cp.font_info.get("font_size")
            
            if current_font and current_font != expected_font:
                self._add_issue(
                    category="figures",
                    location=f"Caption: {truncate_text(cp.text, 30)}",
                    para_index=cp.index,
                    description="Figure caption font does not match template",
                    current=current_font,
                    expected=expected_font,
                    severity="warning",
                    text_preview=truncate_text(cp.text, 50)
                )
            
            if current_size and current_size != expected_size:
                self._add_issue(
                    category="figures",
                    location=f"Caption: {truncate_text(cp.text, 30)}",
                    para_index=cp.index,
                    description="Figure caption size does not match template",
                    current=f"{current_size}pt",
                    expected=f"{expected_size}pt",
                    severity="warning",
                    text_preview=truncate_text(cp.text, 50)
                )
    
    def _check_references(self):
        """Check references section formatting"""
        reference_rules = self.rules.get("reference", {})
        expected_font = reference_rules.get("font_name", "Times New Roman")
        expected_size = reference_rules.get("font_size", 10)
        
        references = [
            cp for cp in self.classifications
            if cp.paragraph_type == ParagraphType.REFERENCE
        ]
        
        if not references:
            self._add_issue(
                category="references",
                location="References Section",
                para_index=-1,
                description="No references found in document",
                current="0 references",
                expected="At least 1 reference",
                severity="error"
            )
            return
        
        # Detect reference style
        ref_texts = [cp.text for cp in references]
        detected_style = detect_reference_style(ref_texts)
        
        # Check for style consistency
        ieee_pattern = r'^\[\d+\]'
        apa_pattern = r'\(\d{4}\)'
        
        ieee_count = sum(1 for ref in ref_texts if re.match(ieee_pattern, ref.strip()))
        apa_count = sum(1 for ref in ref_texts if re.search(apa_pattern, ref))
        
        if ieee_count > 0 and apa_count > 0:
            self._add_issue(
                category="references",
                location="Reference Style",
                para_index=-1,
                description="Mixed reference styles detected (IEEE and APA)",
                current=f"IEEE: {ieee_count}, APA: {apa_count}",
                expected="Consistent style throughout",
                severity="warning"
            )
        
        # Check font formatting (sample first few)
        for i, cp in enumerate(references[:5]):
            current_font = cp.font_info.get("font_name")
            current_size = cp.font_info.get("font_size")
            
            if current_font and current_font != expected_font:
                self._add_issue(
                    category="references",
                    location=f"Reference {i + 1}",
                    para_index=cp.index,
                    description="Reference font does not match template",
                    current=current_font,
                    expected=expected_font,
                    severity="warning",
                    text_preview=truncate_text(cp.text, 50)
                )
            
            if current_size and current_size != expected_size:
                self._add_issue(
                    category="references",
                    location=f"Reference {i + 1}",
                    para_index=cp.index,
                    description="Reference font size does not match template",
                    current=f"{current_size}pt",
                    expected=f"{expected_size}pt",
                    severity="warning",
                    text_preview=truncate_text(cp.text, 50)
                )
    
    def _check_line_spacing(self):
        """Check line spacing throughout document"""
        body_rules = self.rules.get("body", {})
        expected_spacing = body_rules.get("line_spacing", 1.5)
        
        spacing_issues = 0
        
        for cp in self.classifications:
            if cp.paragraph_type in [ParagraphType.BODY, ParagraphType.ABSTRACT_CONTENT]:
                para = self.document.paragraphs[cp.index]
                current_spacing = get_line_spacing(para)
                
                if current_spacing and abs(current_spacing - expected_spacing) > 0.1:
                    spacing_issues += 1
        
        if spacing_issues > 0:
            self._add_issue(
                category="line_spacing",
                location="Line Spacing",
                para_index=-1,
                description=f"{spacing_issues} paragraphs have incorrect line spacing",
                current="Varies",
                expected=f"{expected_spacing} line spacing",
                severity="warning"
            )
    
    def _gather_statistics(self) -> Dict[str, Any]:
        """Gather document statistics"""
        # Count paragraphs by type
        type_counts = {}
        for cp in self.classifications:
            type_name = cp.paragraph_type.value
            type_counts[type_name] = type_counts.get(type_name, 0) + 1
        
        # Count words
        total_words = sum(
            len(cp.text.split()) for cp in self.classifications
            if cp.paragraph_type not in [ParagraphType.EMPTY]
        )
        
        # Count tables and figures
        table_count = len(self.document.tables)
        figure_count = sum(
            1 for cp in self.classifications
            if cp.paragraph_type == ParagraphType.CAPTION and
            re.match(r'^(figure|fig\.?)\s*\d+', cp.text.lower())
        )
        
        # Count references
        reference_count = sum(
            1 for cp in self.classifications
            if cp.paragraph_type == ParagraphType.REFERENCE
        )
        
        return {
            "total_paragraphs": len(self.document.paragraphs),
            "classified_paragraphs": len(self.classifications),
            "paragraph_types": type_counts,
            "total_words": total_words,
            "table_count": table_count,
            "figure_count": figure_count,
            "reference_count": reference_count,
            "pages": len(self.document.sections)
        }
    
    def get_comparison_data(self) -> List[Dict[str, Any]]:
        """Get data for Turnitin-style comparison view"""
        comparison_data = []
        
        for category, issues in self.issues.items():
            for issue in issues:
                comparison_data.append({
                    "category": category,
                    "location": issue.location,
                    "paragraph_index": issue.paragraph_index,
                    "text_preview": issue.text_preview,
                    "current": issue.current_value,
                    "expected": issue.expected_value,
                    "description": issue.description,
                    "severity": issue.severity
                })
        
        return comparison_data
