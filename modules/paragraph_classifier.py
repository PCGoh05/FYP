"""
Paragraph Classifier Module
Intelligently classifies paragraphs to determine which should be modified
"""

import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from .utils import (
    get_paragraph_text, get_paragraph_font_info, 
    get_paragraph_alignment, is_empty_paragraph
)
from config import (
    JOURNAL_HEADER_PATTERNS, AUTHOR_INFO_PATTERNS,
    SECTION_HEADING_PATTERNS, CAPTION_PATTERNS, REFERENCE_PATTERNS
)


class ParagraphType(Enum):
    """Enumeration of paragraph types"""
    # Types to SKIP (preserve original formatting)
    EMPTY = "empty"
    JOURNAL_HEADER = "journal_header"
    AUTHOR_INFO = "author_info"
    ABSTRACT_LABEL = "abstract_label"
    KEYWORDS_LABEL = "keywords_label"
    
    # Types to FIX (apply template formatting)
    PAPER_TITLE = "paper_title"
    SECTION_HEADING = "section_heading"
    BODY = "body"
    ABSTRACT_CONTENT = "abstract_content"
    KEYWORDS_CONTENT = "keywords_content"
    CAPTION = "caption"
    REFERENCE = "reference"
    
    # Special types
    TABLE = "table"
    FIGURE = "figure"
    UNKNOWN = "unknown"


@dataclass
class ClassifiedParagraph:
    """Represents a classified paragraph with metadata"""
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
    Intelligent paragraph classifier that identifies paragraph types
    to determine which should be modified and which should be preserved
    """
    
    # Types that should NOT be modified
    SKIP_TYPES = {
        ParagraphType.EMPTY,
        ParagraphType.JOURNAL_HEADER,
        ParagraphType.AUTHOR_INFO,
        ParagraphType.ABSTRACT_LABEL,
        ParagraphType.KEYWORDS_LABEL,
    }
    
    # Types that SHOULD be modified
    FIX_TYPES = {
        ParagraphType.PAPER_TITLE,
        ParagraphType.SECTION_HEADING,
        ParagraphType.BODY,
        ParagraphType.ABSTRACT_CONTENT,
        ParagraphType.KEYWORDS_CONTENT,
        ParagraphType.CAPTION,
        ParagraphType.REFERENCE,
    }
    
    def __init__(self, llm_integration=None):
        """Initialize the classifier with optional LLM integration"""
        self.llm = llm_integration
        self.classifications: List[ClassifiedParagraph] = []
        self._context = {
            "found_title": False,
            "title_index": -1,
            "in_abstract": False,
            "in_keywords": False,
            "in_references": False,
            "author_section_end": -1,
        }
    
    def classify_document(self, document) -> List[ClassifiedParagraph]:
        """Classify all paragraphs in a document with LLM enhancement for low confidence cases"""
        self.classifications = []
        self._reset_context()
        
        paragraphs = document.paragraphs
        total = len(paragraphs)
        
        # First pass: rule-based classification
        for i, para in enumerate(paragraphs):
            classified = self._classify_paragraph(para, i, total)
            self.classifications.append(classified)
        
        # Post-processing: refine classifications based on context
        self._refine_classifications()
        
        # LLM enhancement pass: verify low confidence classifications
        if self.llm and self.llm.is_available():
            self._llm_enhance_classifications()
        
        return self.classifications
    
    def _llm_enhance_classifications(self):
        """Use LLM to verify and improve low confidence classifications"""
        for i, cp in enumerate(self.classifications):
            # Skip high confidence, empty, and already-verified classifications
            if cp.confidence >= 0.85 or cp.paragraph_type == ParagraphType.EMPTY:
                continue
            
            # Use LLM for uncertain classifications
            llm_type, llm_conf = self.classify_with_llm(cp.text)
            
            if llm_conf > cp.confidence and llm_type != ParagraphType.UNKNOWN:
                # Update with LLM result
                self.classifications[i] = self._create_classification(
                    cp.index, cp.text, llm_type, llm_conf,
                    cp.font_info, cp.alignment, llm_type in self.FIX_TYPES,
                    f"LLM enhanced ({cp.classification_reason})"
                )
    
    def _reset_context(self):
        """Reset classification context"""
        self._context = {
            "found_title": False,
            "title_index": -1,
            "in_abstract": False,
            "in_keywords": False,
            "in_references": False,
            "author_section_end": -1,
            "last_heading_index": -1,
        }
    
    def _classify_paragraph(self, paragraph, index: int, total: int) -> ClassifiedParagraph:
        """Classify a single paragraph"""
        text = get_paragraph_text(paragraph)
        font_info = get_paragraph_font_info(paragraph)
        alignment = get_paragraph_alignment(paragraph)
        
        # Empty paragraph
        if not text:
            return ClassifiedParagraph(
                index=index,
                text="",
                paragraph_type=ParagraphType.EMPTY,
                confidence=1.0,
                font_info=font_info,
                alignment=alignment,
                should_fix=False,
                classification_reason="Empty paragraph"
            )
        
        text_lower = text.lower().strip()
        
        # Check for section labels (Abstract, Keywords) - ENHANCED
        # Handle standalone labels
        if text_lower in ["abstract", "abstract:"]:
            self._context["in_abstract"] = True
            return self._create_classification(
                index, text, ParagraphType.ABSTRACT_LABEL,
                1.0, font_info, alignment, False,
                "Abstract section label"
            )
        
        # Handle inline abstract content: "Abstract - content..." or "Abstract: content..."
        if text_lower.startswith("abstract") and len(text) > 15:
            abstract_match = re.match(r'^abstract[\s\-:—–]+(.+)$', text, re.IGNORECASE)
            if abstract_match and len(abstract_match.group(1)) > 20:
                return self._create_classification(
                    index, text, ParagraphType.ABSTRACT_CONTENT,
                    0.95, font_info, alignment, True,
                    "Abstract with inline content"
                )
        
        # Handle Keywords - standalone
        if text_lower in ["keywords", "keywords:", "key words", "key words:"]:
            self._context["in_abstract"] = False
            self._context["in_keywords"] = True
            return self._create_classification(
                index, text, ParagraphType.KEYWORDS_LABEL,
                1.0, font_info, alignment, False,
                "Keywords section label"
            )
        
        # Handle inline keywords content: "Keywords—word1, word2..." or "Keywords: word1, word2..."
        keywords_match = re.match(r'^keywords?[\s\-:—–]+(.+)$', text, re.IGNORECASE)
        if keywords_match and len(keywords_match.group(1)) > 5:
            return self._create_classification(
                index, text, ParagraphType.KEYWORDS_CONTENT,
                0.95, font_info, alignment, True,
                "Keywords with inline content"
            )
        
        # Check for section headings
        if self._is_section_heading(text):
            self._context["in_abstract"] = False
            self._context["in_keywords"] = False
            if text_lower in ["references", "bibliography", "works cited"]:
                self._context["in_references"] = True
            else:
                self._context["in_references"] = False
            self._context["last_heading_index"] = index
            return self._create_classification(
                index, text, ParagraphType.SECTION_HEADING,
                0.9, font_info, alignment, True,
                "Matches section heading pattern"
            )
        
        # Check for journal header (first few paragraphs)
        if index < 8 and not self._context["found_title"]:
            if self._is_journal_header(text):
                self._context["last_journal_header_index"] = index
                return self._create_classification(
                    index, text, ParagraphType.JOURNAL_HEADER,
                    0.85, font_info, alignment, False,
                    "Matches journal header pattern"
                )
            
            # Check for journal name continuation (same format as previous journal header)
            # e.g., "Journal of Informatics and" + "Web Engineering"
            last_journal_idx = self._context.get("last_journal_header_index", -1)
            if last_journal_idx >= 0 and index == last_journal_idx + 1:
                # If short text and likely part of journal name
                font_size = font_info.get("font_size", 0) or 0
                font_name = font_info.get("font_name", "")
                # Journal name continuation if: large font OR Palatino font OR short text right after journal header
                is_journal_font = font_name and "palatino" in font_name.lower()
                is_large_font = font_size >= 16
                is_short_text = len(text) < 50 and not any(c in text.lower() for c in ['abstract', 'introduction', 'keyword'])
                if is_short_text and (is_large_font or is_journal_font):
                    self._context["last_journal_header_index"] = index  # Update for next continuation
                    return self._create_classification(
                        index, text, ParagraphType.JOURNAL_HEADER,
                        0.80, font_info, alignment, False,
                        "Continuation of journal header (same format)"
                    )
        
        # Check for paper title (first substantial non-header paragraph)
        if not self._context["found_title"] and index < 15:
            if self._is_paper_title(text, font_info, alignment, index):
                self._context["found_title"] = True
                self._context["title_index"] = index
                return self._create_classification(
                    index, text, ParagraphType.PAPER_TITLE,
                    0.9, font_info, alignment, True,
                    "Identified as paper title"
                )
        
        # Check for author info (paragraphs after title)
        if self._context["found_title"] and index <= self._context["title_index"] + 10:
            if self._is_author_info(text):
                self._context["author_section_end"] = index
                return self._create_classification(
                    index, text, ParagraphType.AUTHOR_INFO,
                    0.85, font_info, alignment, False,
                    "Matches author information pattern"
                )
        
        # Check for abstract content
        if self._context["in_abstract"]:
            # Check if this might be a heading that ends abstract
            if self._is_section_heading(text):
                self._context["in_abstract"] = False
            else:
                return self._create_classification(
                    index, text, ParagraphType.ABSTRACT_CONTENT,
                    0.85, font_info, alignment, True,
                    "Content within abstract section"
                )
        
        # Check for keywords content
        if self._context["in_keywords"]:
            if self._is_section_heading(text):
                self._context["in_keywords"] = False
            else:
                return self._create_classification(
                    index, text, ParagraphType.KEYWORDS_CONTENT,
                    0.85, font_info, alignment, True,
                    "Content within keywords section"
                )
        
        # Check for caption
        if self._is_caption(text):
            return self._create_classification(
                index, text, ParagraphType.CAPTION,
                0.9, font_info, alignment, True,
                "Matches figure/table caption pattern"
            )
        
        # Check for reference entry
        if self._context["in_references"] or self._is_reference(text):
            return self._create_classification(
                index, text, ParagraphType.REFERENCE,
                0.8, font_info, alignment, True,
                "Reference entry"
            )
        
        # Default to body text if substantial content
        if len(text) > 30:
            return self._create_classification(
                index, text, ParagraphType.BODY,
                0.7, font_info, alignment, True,
                "Default body text classification"
            )
        
        # Unknown short text
        return self._create_classification(
            index, text, ParagraphType.UNKNOWN,
            0.5, font_info, alignment, False,
            "Short unclassified text"
        )
    
    def _create_classification(self, index: int, text: str, 
                              para_type: ParagraphType, confidence: float,
                              font_info: Dict, alignment: str,
                              should_fix: bool, reason: str) -> ClassifiedParagraph:
        """Create a ClassifiedParagraph object"""
        return ClassifiedParagraph(
            index=index,
            text=text,
            paragraph_type=para_type,
            confidence=confidence,
            font_info=font_info,
            alignment=alignment,
            should_fix=should_fix,
            classification_reason=reason
        )
    
    def _is_journal_header(self, text: str) -> bool:
        """Check if text matches journal header patterns"""
        text_lower = text.lower()
        
        # Check against patterns
        for pattern in JOURNAL_HEADER_PATTERNS:
            if re.search(pattern, text_lower, re.IGNORECASE):
                return True
        
        # Additional checks
        if len(text) < 200:  # Headers are usually short
            # Check for common journal header elements
            if any(keyword in text_lower for keyword in [
                'journal', 'vol.', 'volume', 'issue', 'issn', 'doi:',
                'http', 'www.', '©', 'copyright', 'open access',
                'received', 'accepted', 'published', 'article'
            ]):
                return True
        
        return False
    
    def _is_paper_title(self, text: str, font_info: Dict, 
                        alignment: str, index: int) -> bool:
        """Check if text is likely the paper title - ENHANCED"""
        # Must be substantial
        if len(text) < 15 or len(text) > 500:
            return False
        
        # Should not contain journal header keywords
        text_lower = text.lower()
        header_keywords = ['journal', 'vol.', 'issn', 'doi:', 'http', 'www.', '©', 
                          'received', 'accepted', 'published', 'article info']
        if any(kw in text_lower for kw in header_keywords):
            return False
        
        # Should not contain author info patterns
        if self._is_author_info(text):
            return False
        
        # Should not be a section heading
        if self._is_section_heading(text):
            return False
        
        # Should not be a typical sentence (ending with period and long)
        if text.endswith('.') and len(text) > 200:
            return False
        
        # Positive indicators with scoring
        score = 0
        
        # Large font is a strong indicator (if detected)
        font_size = font_info.get("font_size")
        if font_size:
            if font_size >= 16:
                score += 4
            elif font_size >= 14:
                score += 3
            elif font_size >= 12:
                score += 1
        else:
            # Font not detected, give benefit of doubt based on position
            if index < 8:
                score += 1
        
        # Bold is often used for titles
        if font_info.get("bold"):
            score += 2
        
        # Center alignment is common for titles
        if alignment == "CENTER":
            score += 2
        
        # Position matters - title should be in first 10 paragraphs
        if index < 5:
            score += 2
        elif index < 10:
            score += 1
        
        # Length check - titles are usually 1-2 lines (50-200 chars)
        if 30 <= len(text) <= 250:
            score += 1
        
        # Title usually doesn't end with period
        if not text.endswith('.'):
            score += 1
        
        # Title usually has multiple words (at least 3)
        word_count = len(text.split())
        if 4 <= word_count <= 25:
            score += 1
        
        # Title usually starts with capital letter
        if text[0].isupper():
            score += 1
        
        return score >= 4  # Need at least 4 points to be considered title
    
    def _is_author_info(self, text: str) -> bool:
        """Check if text contains author information"""
        text_lower = text.lower()
        
        # Check against patterns
        for pattern in AUTHOR_INFO_PATTERNS:
            if re.search(pattern, text_lower, re.IGNORECASE):
                return True
        
        # Check for email pattern
        if re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text):
            return True
        
        # Check for superscript numbers often used in author affiliations
        if re.search(r'\d+\s*[,\s]*\d*\s*(university|faculty|department)', text_lower):
            return True
        
        return False
    
    def _is_section_heading(self, text: str) -> bool:
        """Check if text is a section heading - ENHANCED with instruction stripping"""
        text_lower = text.lower().strip()
        original_text = text.strip()
        
        # Too long to be a heading
        if len(original_text) > 150:
            return False
        
        # NEW: Strip parenthetical instructions like "(10-Font size, Times New Roman)"
        # This is common in template files where headings have format instructions
        clean_text = re.sub(r'\s*\([^)]*[Ff]ont[^)]*\)\s*$', '', original_text).strip()
        clean_text_lower = clean_text.lower().strip()
        
        # Also strip any trailing whitespace and common punctuation
        clean_text_lower = clean_text_lower.rstrip(':.')
        
        # EXCLUDE author/affiliation patterns - these should NOT be headings
        affiliation_keywords = ['university', 'faculty', 'department', 'college', 'institute',
                               'school', 'center', 'centre', 'laboratory', 'lab', 'malaysia',
                               'indonesia', 'singapore', 'thailand', 'china', 'japan', 'korea',
                               'email', '@', 'orcid', 'corresponding']
        if any(kw in clean_text_lower for kw in affiliation_keywords):
            return False
        
        # Check exact matches first (most common section names) - using CLEAN text
        exact_headings = [
            'abstract', 'keywords', 'key words', 'introduction', 'background',
            'literature review', 'related work', 'related works',
            'methodology', 'method', 'methods', 'approach',
            'materials and methods', 'material and method',
            'experiment', 'experiments', 'experimental setup',
            'results', 'result', 'findings',
            'discussion', 'analysis',
            'results and discussion', 'result and discussion',
            'conclusion', 'conclusions', 'summary',
            'future work', 'future works',
            'recommendations', 'recommendation',
            'references', 'reference', 'bibliography', 'works cited',
            'acknowledgements', 'acknowledgement', 'acknowledgment',
            'funding', 'conflict of interest', 'data availability',
            'appendix', 'appendices',
            # Research methodology variations
            'research methodology', 'research method', 'research design',
            'data collection', 'data analysis', 'theoretical framework',
            'conceptual framework', 'problem statement', 'research questions',
            'research objectives', 'scope of study', 'limitations',
            'significance of study', 'definition of terms',
        ]
        
        if clean_text_lower in exact_headings:
            return True
        
        # Check patterns with optional numbering using CLEAN text
        for pattern in SECTION_HEADING_PATTERNS:
            if re.match(pattern, clean_text_lower):
                return True
        
        # Check for numbered headings like "1. Introduction", "2 Methodology", "I. Introduction"
        # Pattern: number + optional dot + space + heading text
        numbered_match = re.match(r'^(\d+\.?\s+|\d+\.\d+\.?\s+|[IVXLC]+\.\s+)(.+)$', clean_text, re.IGNORECASE)
        if numbered_match:
            heading_text = numbered_match.group(2).strip().lower()
            # Check if the text part is a known heading
            if heading_text in exact_headings:
                return True
            # Short enough to be a heading and doesn't end with period
            if len(heading_text) < 50 and not heading_text.endswith('.'):
                # Check if it contains heading-like words
                heading_keywords = ['introduction', 'method', 'result', 'discussion', 'conclusion',
                                   'review', 'background', 'experiment', 'analysis', 'study',
                                   'approach', 'framework', 'model', 'system', 'design',
                                   'implementation', 'evaluation', 'comparison', 'related',
                                   'proposed', 'overview', 'problem', 'solution', 'formulation']
                if any(kw in heading_text for kw in heading_keywords):
                    return True
        
        # Check for ALL CAPS headings (common in some formats) - using CLEAN text
        if clean_text.isupper() and len(clean_text) < 60 and len(clean_text.split()) <= 6:
            return True
        
        # Check if it looks like a subsection heading (e.g., "3.2.1 Data Collection")
        if re.match(r'^\d+(\.\d+)+\.?\s+\w+', clean_text_lower):
            return True
        
        return False
    
    def _is_caption(self, text: str) -> bool:
        """Check if text is a figure or table caption"""
        text_lower = text.lower().strip()
        
        for pattern in CAPTION_PATTERNS:
            if re.match(pattern, text_lower):
                return True
        
        return False
    
    def _is_reference(self, text: str) -> bool:
        """Check if text is a reference entry"""
        text_lower = text.lower().strip()
        
        # Check patterns
        for pattern in REFERENCE_PATTERNS:
            if re.search(pattern, text_lower):
                return True
        
        return False
    
    def _refine_classifications(self):
        """Post-process to refine classifications based on context"""
        # Find where author info likely ends
        author_end = -1
        for i, cp in enumerate(self.classifications):
            if cp.paragraph_type == ParagraphType.AUTHOR_INFO:
                author_end = i
        
        # Re-classify ambiguous paragraphs between title and abstract
        if self._context["title_index"] >= 0:
            for i, cp in enumerate(self.classifications):
                if (self._context["title_index"] < i <= author_end + 2 and
                    cp.paragraph_type == ParagraphType.UNKNOWN):
                    # Likely author info
                    if len(cp.text) < 200:
                        self.classifications[i] = self._create_classification(
                            i, cp.text, ParagraphType.AUTHOR_INFO,
                            0.6, cp.font_info, cp.alignment, False,
                            "Contextual: between title and abstract"
                        )
    
    def classify_with_llm(self, text: str) -> Tuple[ParagraphType, float]:
        """Use LLM as fallback for uncertain classifications"""
        if not self.llm:
            return ParagraphType.UNKNOWN, 0.5
        
        prompt = f"""Classify this paragraph from an academic paper. 
Options: journal_header, paper_title, author_info, abstract_label, keywords_label, 
section_heading, body, abstract_content, keywords_content, caption, reference

Paragraph: "{text[:500]}"

Respond with ONLY the classification type, nothing else."""
        
        try:
            response = self.llm.generate(prompt)
            response_lower = response.lower().strip()
            
            type_mapping = {
                "journal_header": ParagraphType.JOURNAL_HEADER,
                "paper_title": ParagraphType.PAPER_TITLE,
                "author_info": ParagraphType.AUTHOR_INFO,
                "abstract_label": ParagraphType.ABSTRACT_LABEL,
                "keywords_label": ParagraphType.KEYWORDS_LABEL,
                "section_heading": ParagraphType.SECTION_HEADING,
                "body": ParagraphType.BODY,
                "abstract_content": ParagraphType.ABSTRACT_CONTENT,
                "keywords_content": ParagraphType.KEYWORDS_CONTENT,
                "caption": ParagraphType.CAPTION,
                "reference": ParagraphType.REFERENCE,
            }
            
            for key, para_type in type_mapping.items():
                if key in response_lower:
                    return para_type, 0.75
            
            return ParagraphType.UNKNOWN, 0.5
        except Exception:
            return ParagraphType.UNKNOWN, 0.5
    
    def get_paragraphs_to_fix(self) -> List[ClassifiedParagraph]:
        """Get list of paragraphs that should be fixed"""
        return [cp for cp in self.classifications if cp.should_fix]
    
    def get_paragraphs_to_skip(self) -> List[ClassifiedParagraph]:
        """Get list of paragraphs that should be skipped"""
        return [cp for cp in self.classifications if not cp.should_fix]
    
    def get_classification_summary(self) -> Dict[str, int]:
        """Get summary of classifications by type"""
        summary = {}
        for cp in self.classifications:
            type_name = cp.paragraph_type.value
            summary[type_name] = summary.get(type_name, 0) + 1
        return summary
