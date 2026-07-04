"""
Modules for Academic Manuscript Format Checker
"""

from .template_extractor import TemplateExtractor
from .profile_loader import ProfileLoader
from .paragraph_classifier import ParagraphClassifier
from .manuscript_checker import ManuscriptChecker
from .auto_fixer import AutoFixer
from .report_generator import ReportGenerator
from .llm_integration import LLMIntegration
from .review_guidance import ReviewGuidanceBuilder
from .utils import *
from .jiwe_caption_patch import apply_jiwe_caption_patch

# Apply the isolated test-branch patch after the core classes are imported.
apply_jiwe_caption_patch()

__all__ = [
    'TemplateExtractor',
    'ProfileLoader',
    'ParagraphClassifier', 
    'ManuscriptChecker',
    'AutoFixer',
    'ReportGenerator',
    'LLMIntegration',
    'ReviewGuidanceBuilder'
]
