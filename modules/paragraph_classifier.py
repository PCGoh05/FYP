"""
Paragraph Classifier Module
LLM-First Architecture: Uses AI as primary classifier, rules as fallback
"""

import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from .utils import (
    get_paragraph_text, get_paragraph_font_info, 
    get_paragraph_alignment, is_empty_paragraph
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
    LLM-First Paragraph Classifier
    
    Architecture:
    1. If LLM available → Batch classify ALL paragraphs with AI
    2. Else → Use minimal fallback rules
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
    
    def classify_document(self, document) -> List[ClassifiedParagraph]:
        """
        Classify all paragraphs in a document.
        
        LLM-FIRST: Uses AI batch classification if available,
        falls back to minimal rules otherwise.
        """
        self.classifications = []
        paragraphs = document.paragraphs
        
        # Collect paragraph info
        para_data = []
        for i, para in enumerate(paragraphs):
            text = get_paragraph_text(para)
            font_info = get_paragraph_font_info(para)
            alignment = get_paragraph_alignment(para)
            para_data.append({
                "index": i,
                "text": text,
                "font_info": font_info,
                "alignment": alignment
            })
        
        # LLM-FIRST: Try AI classification
        if self.llm and self.llm.is_available():
            self.classifications = self._llm_classify_all(para_data)
        else:
            # Fallback to minimal rules
            self.classifications = self._fallback_classify_all(para_data)
        
        return self.classifications
    
    def _llm_classify_all(self, para_data: List[Dict]) -> List[ClassifiedParagraph]:
        """
        Use LLM to classify ALL paragraphs in a single batch call.
        This is the PRIMARY classification method.
        """
        classifications = []
        
        # Prepare texts for batch classification
        texts = [p["text"] for p in para_data]
        
        # Filter out empty paragraphs first (no need to send to LLM)
        non_empty_indices = []
        non_empty_texts = []
        
        for i, text in enumerate(texts):
            if not text or not text.strip():
                # Empty paragraph - classify immediately
                classifications.append(self._create_classification(
                    para_data[i], ParagraphType.EMPTY, 1.0, "Empty paragraph"
                ))
            else:
                non_empty_indices.append(i)
                non_empty_texts.append(text)
        
        # Batch classify non-empty paragraphs with LLM
        if non_empty_texts and hasattr(self.llm, 'classify_paragraphs_batch'):
            try:
                llm_results = self.llm.classify_paragraphs_batch(non_empty_texts)
                
                # Map results back to original indices
                for idx, llm_type_str in zip(non_empty_indices, llm_results):
                    para_type = self._string_to_paragraph_type(llm_type_str)
                    should_fix = para_type in self.FIX_TYPES
                    
                    classifications.append(self._create_classification(
                        para_data[idx], para_type, 0.85, f"AI classified: {llm_type_str}"
                    ))
                
            except Exception as e:
                # If batch fails, fallback to individual classification
                print(f"[DEBUG] Batch classification failed: {e}, using fallback")
                for idx in non_empty_indices:
                    classifications.append(self._fallback_classify_single(para_data[idx]))
        else:
            # No batch method, use individual LLM calls
            for idx in non_empty_indices:
                try:
                    llm_type = self.llm.classify_paragraph(para_data[idx]["text"])
                    para_type = self._string_to_paragraph_type(llm_type)
                    classifications.append(self._create_classification(
                        para_data[idx], para_type, 0.80, f"AI classified: {llm_type}"
                    ))
                except Exception:
                    classifications.append(self._fallback_classify_single(para_data[idx]))
        
        # Sort by index to maintain order
        classifications.sort(key=lambda x: x.index)
        return classifications
    
    def _fallback_classify_all(self, para_data: List[Dict]) -> List[ClassifiedParagraph]:
        """
        Minimal fallback classification when LLM is unavailable.
        Uses only essential structural patterns.
        """
        classifications = []
        context = {
            "found_title": False,
            "in_abstract": False,
            "in_references": False,
        }
        
        for data in para_data:
            cp = self._fallback_classify_single(data, context)
            classifications.append(cp)
            
            # Update context
            if cp.paragraph_type == ParagraphType.PAPER_TITLE:
                context["found_title"] = True
            elif cp.paragraph_type == ParagraphType.ABSTRACT_LABEL:
                context["in_abstract"] = True
            elif cp.paragraph_type == ParagraphType.SECTION_HEADING:
                context["in_abstract"] = False
                if "reference" in cp.text.lower():
                    context["in_references"] = True
        
        return classifications
    
    def _fallback_classify_single(self, data: Dict, context: Dict = None) -> ClassifiedParagraph:
        """
        Classify a single paragraph using minimal rules.
        Only uses structural patterns, not content-based keywords.
        """
        text = data["text"]
        font_info = data["font_info"]
        alignment = data["alignment"]
        index = data["index"]
        
        if context is None:
            context = {"found_title": False, "in_abstract": False, "in_references": False}
        
        # 1. Empty paragraph
        if not text or not text.strip():
            return self._create_classification(data, ParagraphType.EMPTY, 1.0, "Empty")
        
        text_lower = text.lower().strip()
        
        # 2. Structural patterns (not content-based)
        
        # Abstract/Keywords labels (exact match)
        if text_lower in ["abstract", "abstract:"]:
            return self._create_classification(data, ParagraphType.ABSTRACT_LABEL, 0.95, "Abstract label")
        
        if text_lower in ["keywords", "keywords:", "key words", "key words:"]:
            return self._create_classification(data, ParagraphType.KEYWORDS_LABEL, 0.95, "Keywords label")
        
        # Numbered section headings (e.g., "1. Introduction", "2.1 Methods")
        if re.match(r'^\d+\.?\d*\.?\s+\w', text) and len(text) < 80:
            return self._create_classification(data, ParagraphType.SECTION_HEADING, 0.80, "Numbered heading")
        
        # Figure/Table captions
        if re.match(r'^(figure|fig\.|table)\s*\d+', text_lower):
            return self._create_classification(data, ParagraphType.CAPTION, 0.90, "Caption pattern")
        
        # Email pattern → Author info
        if re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text):
            return self._create_classification(data, ParagraphType.AUTHOR_INFO, 0.85, "Contains email")
        
        # URL/DOI pattern → Journal header
        if re.search(r'(https?://|doi:|issn|eissn)', text_lower):
            return self._create_classification(data, ParagraphType.JOURNAL_HEADER, 0.85, "Contains URL/DOI")
        
        # Reference pattern (starts with [1] or 1. followed by author names)
        if context.get("in_references") or re.match(r'^\[\d+\]|\d+\.\s+[A-Z][a-z]+,?\s+[A-Z]', text):
            return self._create_classification(data, ParagraphType.REFERENCE, 0.75, "Reference entry")
        
        # First substantial paragraph with large font → likely title
        if not context.get("found_title") and index < 10:
            font_size = font_info.get("font_size") or 0
            if font_size >= 16 or (font_info.get("bold") and len(text) < 200):
                return self._create_classification(data, ParagraphType.PAPER_TITLE, 0.70, "Large font, early position")
        
        # Context-based classification
        if context.get("in_abstract"):
            return self._create_classification(data, ParagraphType.ABSTRACT_CONTENT, 0.70, "After abstract label")
        
        # Default to body text
        if len(text) > 30:
            return self._create_classification(data, ParagraphType.BODY, 0.60, "Default body text")
        
        return self._create_classification(data, ParagraphType.UNKNOWN, 0.50, "Unknown short text")
    
    def _create_classification(self, data: Dict, para_type: ParagraphType, 
                               confidence: float, reason: str) -> ClassifiedParagraph:
        """Create a ClassifiedParagraph object"""
        return ClassifiedParagraph(
            index=data["index"],
            text=data["text"],
            paragraph_type=para_type,
            confidence=confidence,
            font_info=data["font_info"],
            alignment=data["alignment"],
            should_fix=para_type in self.FIX_TYPES,
            classification_reason=reason
        )
    
    def _string_to_paragraph_type(self, type_str: str) -> ParagraphType:
        """Convert a string classification to ParagraphType enum"""
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
        }
        return type_mapping.get(type_str.lower().strip(), ParagraphType.UNKNOWN)
    
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
