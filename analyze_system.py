"""
Automated Test Script for Detection and Correction Analysis
"""
import sys
sys.path.insert(0, '.')

from modules.template_extractor import TemplateExtractor
from modules.manuscript_checker import ManuscriptChecker
from modules.paragraph_classifier import ParagraphType
from modules.utils import get_paragraph_text, get_paragraph_font_info
from docx import Document

print('='*60)
print('1. TEMPLATE RULES EXTRACTION')
print('='*60)
extractor = TemplateExtractor()
extractor.load('sample/JIWE_Template.docx')
rules = extractor.extract_all_rules()
print(f"Title: {rules.get('title')}")
print(f"Body: {rules.get('body')}")
print(f"Heading: {rules.get('heading')}")
print(f"Abstract: {rules.get('abstract')}")

print()
print('='*60)
print('2. MANUSCRIPT CHECK RESULTS (00.docx)')
print('='*60)
checker = ManuscriptChecker(rules)
checker.load_manuscript('sample/00.docx')
result = checker.check_all()
print(f"Compliance Score: {result.compliance_score}%")
print(f"Total Issues: {result.total_issues}")

print()
print('3. PARAGRAPH CLASSIFICATIONS (first 15):')
for cp in result.classifications[:15]:
    if cp.paragraph_type == ParagraphType.EMPTY:
        continue
    text_preview = cp.text[:35] + '...' if len(cp.text) > 35 else cp.text
    print(f"  [{cp.paragraph_type.value:15}] {text_preview}")

print()
print('4. ISSUES FOUND:')
for cat, issues in result.issues_by_category.items():
    if issues:
        print(f"  {cat}: {len(issues)} issues")
        for issue in issues[:2]:
            print(f"    - {issue.description}")
            print(f"      Current: {issue.current_value}, Expected: {issue.expected_value}")

print()
print('5. SAMPLE DOCUMENT FONT ANALYSIS (00.docx - first 10 paras):')
doc = Document('sample/00.docx')
for i, para in enumerate(doc.paragraphs[:10]):
    text = get_paragraph_text(para)
    if not text:
        continue
    font_info = get_paragraph_font_info(para)
    text_preview = text[:40] + '...' if len(text) > 40 else text
    print(f"  Para {i}: Font={font_info.get('font_name')}, Size={font_info.get('font_size')}pt, Bold={font_info.get('bold')}")
    print(f"           '{text_preview}'")

print()
print('6. SAMPLE OF SECTION_HEADING CLASSIFICATIONS:')
count = 0
for cp in result.classifications:
    if cp.paragraph_type == ParagraphType.SECTION_HEADING:
        text_preview = cp.text[:60] + '...' if len(cp.text) > 60 else cp.text
        print(f"  Para {cp.index}: \"{text_preview}\"")
        count += 1
        if count >= 15:
            print(f"  ... and {90 - count} more")
            break
