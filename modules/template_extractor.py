"""
Template Extractor Module
Extracts formatting rules from journal templates automatically
"""

from docx import Document
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from collections import Counter
from typing import Dict, List, Any, Optional
import re

from .utils import (
    load_document, get_paragraph_text, get_paragraph_font_info,
    get_paragraph_alignment, get_margins, get_line_spacing,
    count_columns, is_empty_paragraph, get_run_font_info
)
from config import DEFAULT_RULES, SECTION_HEADING_PATTERNS


def _parse_instruction_format(text: str) -> Dict[str, Any]:
    """
    Parse formatting instructions from template instruction text.
    
    Examples:
        "(24- Font size, bold Palatino Linotype)" -> may contain format info
        "(11-Font size, bold Times New Roman)" -> font_size=11, bold=True, font_name="Times New Roman"
        "(10-Font size, Times New Roman)" -> font_size=10, bold=False, font_name="Times New Roman"
    
    Returns:
        Dictionary with extracted format rules (font_name, font_size, bold)
        Empty dict if no format info found
    """
    result = {}
    
    # Look for patterns in parentheses or brackets
    # Pattern: (XX- Font size, [bold] FontName) or (XX-Font size, [bold] FontName)
    instruction_match = re.search(r'\((\d+)[- ]?\s*[Ff]ont\s*size,?\s*(bold)?\s*(.+?)\)', text)
    if instruction_match:
        result["font_size"] = int(instruction_match.group(1))
        result["bold"] = instruction_match.group(2) is not None
        font_name = instruction_match.group(3).strip()
        # Clean up font name - remove trailing parenthesis or extra text
        font_name = re.sub(r'\s*\(.*$', '', font_name).strip()
        if font_name and len(font_name) > 2:
            result["font_name"] = font_name
    
    # Also check for patterns like "10pt Times New Roman" or "Times New Roman 12pt"
    if not result:
        pt_match = re.search(r'(\d+)\s*pt\s+(\w[\w\s]+)', text, re.IGNORECASE)
        if pt_match:
            result["font_size"] = int(pt_match.group(1))
            result["font_name"] = pt_match.group(2).strip()
    
    return result


class TemplateExtractor:
    """Extract formatting rules from a journal template document"""
    
    def __init__(self, document=None, llm_integration=None):
        """
        Initialize the template extractor.
        
        Args:
            document: Optional pre-loaded document
            llm_integration: Optional LLM integration for intelligent analysis
        """
        self.document = document
        self.rules = DEFAULT_RULES.copy()
        self.debug_info = {}  # Store debug information
        self.llm = llm_integration  # LLM for fallback classification
        
    def load(self, file_path_or_bytes):
        """Load the template document"""
        self.document = load_document(file_path_or_bytes)
        return self
    
    def scan_all_fonts(self) -> Dict[str, Any]:
        """Scan ALL fonts in the document for debugging purposes"""
        if not self.document:
            raise ValueError("No document loaded. Call load() first.")
        
        all_fonts = []
        all_sizes = []
        paragraph_details = []
        
        for i, para in enumerate(self.document.paragraphs):
            text = get_paragraph_text(para)
            preview = text[:50] + "..." if len(text) > 50 else text
            
            para_fonts = []
            para_sizes = []
            
            # Method 1: Scan each run individually
            for run in para.runs:
                if not run.text.strip():
                    continue
                    
                run_info = get_run_font_info(run)
                
                if run_info.get("font_name"):
                    para_fonts.append(run_info["font_name"])
                    all_fonts.append(run_info["font_name"])
                
                if run_info.get("font_size"):
                    para_sizes.append(run_info["font_size"])
                    all_sizes.append(run_info["font_size"])
            
            # Method 2: Check paragraph style directly
            style = para.style
            style_font = None
            style_size = None
            if style:
                if style.font:
                    style_font = style.font.name
                    if style.font.size:
                        style_size = style.font.size.pt
            
            # Method 3: Check XML directly for paragraph-level font
            pPr = para._element.pPr
            xml_size = None
            if pPr is not None:
                rPr = pPr.find(qn('w:rPr'))
                if rPr is not None:
                    sz = rPr.find(qn('w:sz'))
                    if sz is not None:
                        sz_val = sz.get(qn('w:val'))
                        if sz_val:
                            try:
                                xml_size = int(sz_val) / 2
                            except:
                                pass
            
            if para_fonts or para_sizes or style_font or style_size or xml_size:
                paragraph_details.append({
                    "index": i,
                    "preview": preview,
                    "fonts_from_runs": list(set(para_fonts)) if para_fonts else None,
                    "sizes_from_runs": list(set(para_sizes)) if para_sizes else None,
                    "style_name": style.name if style else None,
                    "style_font": style_font,
                    "style_size": style_size,
                    "xml_size": xml_size
                })
        
        # Also scan document styles
        style_details = []
        for style in self.document.styles:
            # Skip styles that don't have font attribute (like NumberingStyle)
            if not hasattr(style, 'font') or style.font is None:
                continue
            try:
                style_info = {
                    "name": style.name,
                    "type": str(style.type)
                }
                if style.font.name:
                    style_info["font_name"] = style.font.name
                if style.font.size:
                    style_info["font_size"] = style.font.size.pt
                if style.font.bold is not None:
                    style_info["bold"] = style.font.bold
                if any(k in style_info for k in ["font_name", "font_size", "bold"]):
                    style_details.append(style_info)
            except AttributeError:
                # Skip styles that cause attribute errors
                continue
        
        # Summary
        font_counter = Counter(all_fonts)
        size_counter = Counter(all_sizes)
        
        self.debug_info = {
            "total_paragraphs": len(self.document.paragraphs),
            "font_frequency": dict(font_counter.most_common(10)),
            "size_frequency": dict(size_counter.most_common(10)),
            "unique_fonts": list(set(all_fonts)),
            "unique_sizes": sorted(list(set(all_sizes))),
            "paragraph_samples": paragraph_details[:30],  # First 30 paragraphs
            "document_styles": style_details[:20]  # First 20 styles
        }
        
        return self.debug_info
    
    def extract_all_rules(self) -> Dict[str, Any]:
        """Extract all formatting rules from the template - SMART EXTRACTION"""
        if not self.document:
            raise ValueError("No document loaded. Call load() first.")
        
        # First scan all fonts for debugging
        self.scan_all_fonts()
        
        # Smart extraction based on frequency analysis
        size_freq = self.debug_info.get("size_frequency", {})
        
        # Find the most common sizes
        sizes_sorted = sorted(size_freq.items(), key=lambda x: x[1], reverse=True)
        
        # Determine body size (most common) and other sizes
        body_size = 10  # default
        abstract_size = 9  # default
        heading_size = 10  # default
        title_size = 24  # default
        
        if sizes_sorted:
            # Body text is usually the most common size
            body_size = sizes_sorted[0][0]
            
            # Find smaller sizes for abstract/reference (usually 9pt)
            for size, count in sizes_sorted:
                if size < body_size and count > 5:
                    abstract_size = size
                    break
            
            # Find larger sizes for title
            for size, count in sizes_sorted:
                if size >= 20:
                    title_size = size
                    break
        
        rules = {
            "margins": self._extract_margins(),
            "title": self._extract_title_style(),
            "author": {
                "font_name": "Times New Roman",
                "font_size": 11,
                "bold": True,
                "alignment": "CENTER"
            },
            "affiliation": {
                "font_name": "Times New Roman", 
                "font_size": abstract_size,
                "alignment": "CENTER"
            },
            "body": self._extract_body_style(),
            "heading": self._extract_heading_style(),
            "abstract": self._extract_abstract_style(),
            "keywords": {
                "font_name": "Times New Roman",
                "font_size": abstract_size
            },
            "caption": self._extract_caption_style(),
            "reference": self._extract_reference_style(),
            "layout": self._extract_layout(),
            "_debug": self.debug_info
        }
        
        self.rules = rules
        return rules
    
    def _extract_margins(self) -> Dict[str, float]:
        """Extract page margins from the template"""
        return get_margins(self.document)
    
    def _extract_title_style(self) -> Dict[str, Any]:
        """
        Extract paper title formatting style using intelligent detection.
        
        This method distinguishes between:
        - Journal Title (e.g., "(Journal Title) Journal of Informatics...")
        - Paper Title (e.g., "(Title) Preparation template...")
        
        The paper title is identified by looking for "(Title)" keyword first.
        """
        from docx.oxml.ns import qn
        
        # STEP 1: Search for "(Title)" in ALL paragraph elements (including those in text boxes)
        # This is the most reliable way to find Paper Title format
        body_xml = self.document.element.body
        all_p = body_xml.findall('.//' + qn('w:p'))
        
        for p_elem in all_p:
            texts = [t.text for t in p_elem.findall('.//' + qn('w:t')) if t.text]
            full_text = ''.join(texts)
            
            # Look for "(Title)" keyword (not "(Journal Title)")
            if '(Title)' in full_text and '(Journal Title)' not in full_text:
                # Found Paper Title paragraph - try to parse instruction format
                instruction_rules = _parse_instruction_format(full_text)
                if instruction_rules:
                    return {
                        "font_name": instruction_rules.get("font_name", "Times New Roman"),
                        "font_size": instruction_rules.get("font_size", 24),
                        "bold": instruction_rules.get("bold", False),
                        "alignment": "CENTER"
                    }
        
        # STEP 2: Fall back to original logic if "(Title)" not found
        # Keywords that indicate journal name (not paper title)
        journal_name_keywords = [
            'journal of', 'proceedings of', 'transactions on',
            'international journal', 'ieee', 'acm', 'springer',
            'elsevier', 'wiley', 'taylor & francis', 'mdpi',
            'frontiers in', 'annals of', 'advances in',
            'review of', 'letters in', 'communications in',
            '(journal title)'  # Added this!
        ]
        
        # Keywords that indicate journal info (volume, issue, etc.)
        journal_info_keywords = [
            'vol.', 'volume', 'issue', 'issn', 'eissn', 'e-issn',
            'p-issn', 'doi:', 'doi ', 'http', 'www.', '©',
            'copyright', 'open access', 'received', 'accepted',
            'published', 'article info', 'article history',
            'palatino linotype'  # This is journal title font, skip it!
        ]
        
        # Track paragraphs to find paper title
        journal_header_end = -1
        candidates = []
        
        for i, para in enumerate(self.document.paragraphs[:15]):
            text = get_paragraph_text(para)
            if not text or len(text) < 10:
                continue
            
            text_lower = text.lower().strip()
            font_info = get_paragraph_font_info(para)
            alignment = get_paragraph_alignment(para)
            
            # Check if this is a journal name
            is_journal_name = any(kw in text_lower for kw in journal_name_keywords)
            
            # Check if this is journal info (volume, ISSN, etc.)
            is_journal_info = any(kw in text_lower for kw in journal_info_keywords)
            
            # Check if this is a section heading
            is_heading = any(
                re.match(pattern, text_lower) 
                for pattern in SECTION_HEADING_PATTERNS
            )
            
            if is_journal_name or is_journal_info:
                journal_header_end = i
                continue
            
            if is_heading:
                continue
            
            # This could be the paper title - add as candidate
            # Score based on multiple factors
            score = 0
            
            # Position: should be after journal header
            if i > journal_header_end:
                score += 2
            
            # Length: typical title is 50-300 characters
            if 30 <= len(text) <= 300:
                score += 2
            elif len(text) > 300:
                score -= 1  # Too long, probably body text
            
            # Font size: larger fonts are more likely titles
            font_size = font_info.get("font_size")
            if font_size:
                if font_size >= 16:
                    score += 3
                elif font_size >= 12:
                    score += 2
                elif font_size >= 10:
                    score += 1
            
            # Bold text is common for titles
            if font_info.get("bold"):
                score += 2
            
            # Center alignment is common for titles
            if alignment == "CENTER":
                score += 2
            
            # Title usually doesn't end with period
            if not text.endswith('.'):
                score += 1
            
            # Title has multiple words
            word_count = len(text.split())
            if 4 <= word_count <= 25:
                score += 1
            
            # Check if next paragraph looks like author info
            if i + 1 < len(self.document.paragraphs):
                next_text = get_paragraph_text(self.document.paragraphs[i + 1]).lower()
                author_indicators = ['@', 'university', 'faculty', 'department', 
                                    'institute', 'college', 'school of']
                if any(ind in next_text for ind in author_indicators):
                    score += 3
            
            if score >= 4:
                candidates.append({
                    'index': i,
                    'score': score,
                    'font_info': font_info,
                    'alignment': alignment,
                    'text': text[:100]
                })
        
        # Select best candidate
        if candidates:
            # Sort by score (descending), then by position (ascending)
            candidates.sort(key=lambda x: (-x['score'], x['index']))
            best = candidates[0]
            
            # Use LLM to verify if score is borderline (4-6)
            if self.llm and self.llm.is_available() and best['score'] < 7:
                verified = self._llm_verify_title(best['text'])
                if not verified and len(candidates) > 1:
                    # Try second best candidate
                    best = candidates[1]
            
            # FIRST: Try to parse instruction format from the text itself
            # This handles templates like "(24-Font size, bold Times New Roman)"
            instruction_rules = _parse_instruction_format(best['text'])
            
            if instruction_rules:
                # Use instruction rules if found
                return {
                    "font_name": instruction_rules.get("font_name", "Times New Roman"),
                    "font_size": instruction_rules.get("font_size", 24),
                    "bold": instruction_rules.get("bold", True),
                    "alignment": best['alignment'] or "CENTER"
                }
            else:
                # Fall back to actual paragraph formatting
                return {
                    "font_name": best['font_info'].get("font_name", "Times New Roman"),
                    "font_size": best['font_info'].get("font_size", 14) or 14,
                    "bold": best['font_info'].get("bold", True),
                    "alignment": best['alignment'] or "CENTER"
                }
        
        # Default title style if no candidates found
        return DEFAULT_RULES["title"]
    
    def _llm_verify_title(self, text: str) -> bool:
        """
        Use LLM to verify if text is a paper title.
        
        Args:
            text: The text to verify
            
        Returns:
            True if LLM confirms this is a paper title
        """
        if not self.llm:
            return True  # Assume true if no LLM available
        
        prompt = f"""Is this text a paper title from an academic manuscript?

Text: "{text[:200]}"

A paper title is the main title of a research paper, NOT:
- Journal name (e.g., "Journal of Computer Science")
- Volume/Issue info (e.g., "Vol. 3 No. 2")
- Author information
- Section headings (e.g., "Introduction", "Methodology")

Answer with ONLY "yes" or "no"."""

        try:
            response = self.llm.generate(prompt)
            return 'yes' in response.lower()
        except Exception:
            return True  # Assume true on error
    
    def _extract_body_style(self) -> Dict[str, Any]:
        """Extract body text style using frequency analysis - ENHANCED"""
        font_names = []
        font_sizes = []
        line_spacings = []
        
        # Analyze ALL runs in body paragraphs to get accurate font info
        for para in self.document.paragraphs[5:]:
            text = get_paragraph_text(para)
            
            # Skip empty paragraphs and short headings
            if not text or len(text) < 50:
                continue
            
            # Skip section headings (usually ALL CAPS or numbered)
            text_stripped = text.strip()
            if text_stripped.isupper() and len(text_stripped) < 50:
                continue
            
            is_heading = any(
                re.match(pattern, text.lower()) 
                for pattern in SECTION_HEADING_PATTERNS
            )
            if is_heading:
                continue
            
            # Get font info from EACH run individually
            for run in para.runs:
                if not run.text.strip():
                    continue
                
                run_info = get_run_font_info(run)
                
                if run_info.get("font_name"):
                    font_names.append(run_info["font_name"])
                if run_info.get("font_size"):
                    font_sizes.append(run_info["font_size"])
            
            spacing = get_line_spacing(para)
            if spacing:
                line_spacings.append(spacing)
        
        # Get most common values
        body_style = {
            "font_name": Counter(font_names).most_common(1)[0][0] if font_names else "Times New Roman",
            "font_size": Counter(font_sizes).most_common(1)[0][0] if font_sizes else 10,
            "line_spacing": Counter(line_spacings).most_common(1)[0][0] if line_spacings else 1.0
        }
        
        return body_style
    
    def _extract_heading_style(self) -> Dict[str, Any]:
        """Extract section heading style - ENHANCED"""
        heading_fonts = []
        heading_sizes = []
        heading_bold = []
        
        for para in self.document.paragraphs:
            text = get_paragraph_text(para)
            text_stripped = text.strip()
            
            # Check if this is a heading (ALL CAPS, numbered, or matches pattern)
            is_all_caps = text_stripped.isupper() and 5 < len(text_stripped) < 60
            is_numbered = re.match(r'^\d+\.?\s+[A-Z]', text_stripped)
            is_pattern_match = any(
                re.match(pattern, text.lower()) 
                for pattern in SECTION_HEADING_PATTERNS
            )
            
            if (is_all_caps or is_numbered or is_pattern_match) and len(text) < 100:
                # Get font info from the FIRST run only (heading text, not annotations)
                for run in para.runs:
                    run_text = run.text.strip()
                    if not run_text:
                        continue
                    
                    # Skip annotation runs (e.g., "(10-Font size...)")
                    if run_text.startswith('(') or 'font' in run_text.lower():
                        continue
                    
                    run_info = get_run_font_info(run)
                    
                    if run_info.get("font_name"):
                        heading_fonts.append(run_info["font_name"])
                    if run_info.get("font_size"):
                        heading_sizes.append(run_info["font_size"])
                    if run_info.get("bold") is not None:
                        heading_bold.append(run_info["bold"])
                    
                    # Only take first meaningful run
                    break
        
        # Determine heading style from extracted data
        if heading_fonts or heading_sizes:
            # Use actual bold value from template, not hardcoded
            # Some templates use ALL CAPS instead of bold (like JIWE)
            actual_bold = Counter(heading_bold).most_common(1)[0][0] if heading_bold else False
            
            return {
                "font_name": Counter(heading_fonts).most_common(1)[0][0] if heading_fonts else "Times New Roman",
                "font_size": Counter(heading_sizes).most_common(1)[0][0] if heading_sizes else 10,
                "bold": actual_bold,  # Use actual template value
                "all_caps": True  # JIWE uses ALL CAPS for main headings
            }
        
        return DEFAULT_RULES["heading"]
    
    def _extract_abstract_style(self) -> Dict[str, Any]:
        """Extract abstract text style"""
        in_abstract = False
        
        for para in self.document.paragraphs:
            text = get_paragraph_text(para)
            
            if text.lower().startswith("abstract"):
                in_abstract = True
                # Check if abstract text is on same line
                if len(text) > 20 and "-" in text:
                    # Format: "Abstract - content..."
                    for run in para.runs:
                        if run.text.strip() and len(run.text) > 10:
                            run_info = get_run_font_info(run)
                            if run_info.get("font_size"):
                                return {
                                    "font_name": run_info.get("font_name", "Times New Roman"),
                                    "font_size": run_info.get("font_size", 9)
                                }
                continue
            
            if in_abstract and text and len(text) > 50:
                # Get font info from runs for accuracy
                for run in para.runs:
                    if run.text.strip() and len(run.text) > 10:
                        run_info = get_run_font_info(run)
                        if run_info.get("font_size"):
                            return {
                                "font_name": run_info.get("font_name", "Times New Roman"),
                                "font_size": run_info.get("font_size", 9)
                            }
            
            # Stop if we hit another section
            if in_abstract and any(
                re.match(pattern, text.lower()) 
                for pattern in SECTION_HEADING_PATTERNS
            ):
                break
        
        return DEFAULT_RULES.get("abstract", {"font_name": "Times New Roman", "font_size": 9})
    
    def _extract_caption_style(self) -> Dict[str, Any]:
        """Extract figure/table caption style"""
        caption_fonts = []
        caption_sizes = []
        caption_italic = []
        
        caption_patterns = [
            r'^figure\s*\d+',
            r'^fig\.\s*\d+',
            r'^table\s*\d+',
        ]
        
        for para in self.document.paragraphs:
            text = get_paragraph_text(para)
            
            is_caption = any(
                re.match(pattern, text.lower()) 
                for pattern in caption_patterns
            )
            
            if is_caption:
                font_info = get_paragraph_font_info(para)
                
                if font_info.get("font_name"):
                    caption_fonts.append(font_info["font_name"])
                if font_info.get("font_size"):
                    caption_sizes.append(font_info["font_size"])
                if font_info.get("italic") is not None:
                    caption_italic.append(font_info["italic"])
        
        if caption_fonts or caption_sizes:
            return {
                "font_name": Counter(caption_fonts).most_common(1)[0][0] if caption_fonts else "Times New Roman",
                "font_size": Counter(caption_sizes).most_common(1)[0][0] if caption_sizes else 10,
                "italic": Counter(caption_italic).most_common(1)[0][0] if caption_italic else True
            }
        
        return DEFAULT_RULES.get("caption", {"font_name": "Times New Roman", "font_size": 10, "italic": True})
    
    def _extract_reference_style(self) -> Dict[str, Any]:
        """Extract reference entry style - ENHANCED"""
        in_references = False
        ref_fonts = []
        ref_sizes = []
        
        for para in self.document.paragraphs:
            text = get_paragraph_text(para)
            text_upper = text.upper().strip()
            
            # Check for REFERENCES heading
            if text_upper in ["REFERENCES", "BIBLIOGRAPHY", "WORKS CITED"] or \
               text.lower() in ["references", "bibliography", "works cited"]:
                in_references = True
                continue
            
            # Stop at next major section
            if in_references and text_upper.startswith("BIOGRAPHIES"):
                break
            
            if in_references and text:
                # Get font info from runs for accuracy
                for run in para.runs:
                    if run.text.strip():
                        run_info = get_run_font_info(run)
                        
                        if run_info.get("font_name"):
                            ref_fonts.append(run_info["font_name"])
                        if run_info.get("font_size"):
                            ref_sizes.append(run_info["font_size"])
        
        if ref_fonts or ref_sizes:
            return {
                "font_name": Counter(ref_fonts).most_common(1)[0][0] if ref_fonts else "Times New Roman",
                "font_size": Counter(ref_sizes).most_common(1)[0][0] if ref_sizes else 9
            }
        
        return DEFAULT_RULES.get("reference", {"font_name": "Times New Roman", "font_size": 9})
    
    def _extract_layout(self) -> Dict[str, Any]:
        """Extract document layout settings"""
        columns = count_columns(self.document)
        
        # Detect page size
        try:
            section = self.document.sections[0]
            width = section.page_width.inches if section.page_width else 8.5
            height = section.page_height.inches if section.page_height else 11
            
            # Determine page size
            if abs(width - 8.27) < 0.1 and abs(height - 11.69) < 0.1:
                page_size = "A4"
            elif abs(width - 8.5) < 0.1 and abs(height - 11) < 0.1:
                page_size = "Letter"
            else:
                page_size = f"{width:.2f}x{height:.2f}"
        except Exception:
            page_size = "A4"
        
        return {
            "columns": columns,
            "page_size": page_size
        }
    
    def get_rules(self) -> Dict[str, Any]:
        """Get the extracted rules"""
        return self.rules
    
    def get_rules_summary(self) -> str:
        """Generate a human-readable summary of the extracted rules"""
        rules = self.rules
        
        summary = []
        summary.append("=== Extracted Formatting Rules (JIWE Style) ===\n")
        
        # Margins
        summary.append("📐 Page Margins:")
        margins = rules.get("margins", {})
        summary.append(f"   Left: {margins.get('left', 1.0):.2f}in")
        summary.append(f"   Right: {margins.get('right', 1.0):.2f}in")
        summary.append(f"   Top: {margins.get('top', 1.0):.2f}in")
        summary.append(f"   Bottom: {margins.get('bottom', 1.0):.2f}in")
        
        # Title
        summary.append("\n📝 Paper Title Style:")
        title = rules.get("title", {})
        summary.append(f"   Font: {title.get('font_name', 'Times New Roman')}")
        summary.append(f"   Size: {title.get('font_size', 24)}pt")
        summary.append(f"   Bold: {title.get('bold', True)}")
        summary.append(f"   Alignment: {title.get('alignment', 'CENTER')}")
        
        # Author
        summary.append("\n👤 Author Names Style:")
        author = rules.get("author", {})
        summary.append(f"   Font: {author.get('font_name', 'Times New Roman')}")
        summary.append(f"   Size: {author.get('font_size', 11)}pt")
        summary.append(f"   Bold: {author.get('bold', True)}")
        
        # Affiliation
        summary.append("\n🏛️ Affiliation Style:")
        affiliation = rules.get("affiliation", {})
        summary.append(f"   Font: {affiliation.get('font_name', 'Times New Roman')}")
        summary.append(f"   Size: {affiliation.get('font_size', 9)}pt")
        
        # Abstract
        summary.append("\n📋 Abstract Style:")
        abstract = rules.get("abstract", {})
        summary.append(f"   Font: {abstract.get('font_name', 'Times New Roman')}")
        summary.append(f"   Size: {abstract.get('font_size', 9)}pt")
        
        # Body
        summary.append("\n📄 Body Text Style:")
        body = rules.get("body", {})
        summary.append(f"   Font: {body.get('font_name', 'Times New Roman')}")
        summary.append(f"   Size: {body.get('font_size', 10)}pt")
        summary.append(f"   Line Spacing: {body.get('line_spacing', 1.0)}")
        
        # Headings
        summary.append("\n🔖 Section Heading Style:")
        heading = rules.get("heading", {})
        summary.append(f"   Font: {heading.get('font_name', 'Times New Roman')}")
        summary.append(f"   Size: {heading.get('font_size', 10)}pt")
        summary.append(f"   Bold: {heading.get('bold', True)}")
        summary.append(f"   ALL CAPS: {heading.get('all_caps', True)}")
        
        # Reference
        summary.append("\n📚 Reference Style:")
        reference = rules.get("reference", {})
        summary.append(f"   Font: {reference.get('font_name', 'Times New Roman')}")
        summary.append(f"   Size: {reference.get('font_size', 9)}pt")
        
        # Layout
        summary.append("\n📏 Layout:")
        layout = rules.get("layout", {})
        summary.append(f"   Columns: {layout.get('columns', 1)}")
        summary.append(f"   Page Size: {layout.get('page_size', 'A4')}")
        
        return "\n".join(summary)
