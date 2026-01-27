"""
Analyze user's test file 00.docx
"""
import sys
sys.path.insert(0, '.')

from modules.template_extractor import TemplateExtractor
from modules.manuscript_checker import ManuscriptChecker
from modules.paragraph_classifier import ParagraphType
from modules.utils import get_paragraph_text, get_paragraph_font_info
from docx import Document

# 1. Check what's in the file
print("=" * 80)
print("1. FILE CONTENTS - 00.docx")
print("=" * 80)

doc = Document('sample/00.docx')
for i, para in enumerate(doc.paragraphs[:15]):
    text = get_paragraph_text(para)
    if not text:
        print(f"Para {i}: [EMPTY]")
        continue
    
    font_info = get_paragraph_font_info(para)
    text_preview = text[:50] + "..." if len(text) > 50 else text
    print(f"Para {i}: Font={font_info.get('font_name')}, Size={font_info.get('font_size')}pt")
    print(f"         Text: '{text_preview}'")

# 2. Load template and extract rules
print("\n" + "=" * 80)
print("2. TEMPLATE RULES")
print("=" * 80)

extractor = TemplateExtractor()
extractor.load('sample/JIWE_Template.docx')
rules = extractor.extract_all_rules()

print(f"Title: {rules.get('title')}")
print(f"Body: {rules.get('body')}")
print(f"Heading: {rules.get('heading')}")

# 3. Check the file
print("\n" + "=" * 80)
print("3. MANUSCRIPT ANALYSIS")
print("=" * 80)

checker = ManuscriptChecker(rules)
try:
    checker.load_manuscript('sample/00.docx')
    result = checker.check_all()
    print(f"Compliance Score: {result.compliance_score}%")
    print(f"Total Issues: {result.total_issues}")
    
    # Show classifications
    print("\nClassifications:")
    for cp in result.classifications[:10]:
        if cp.paragraph_type == ParagraphType.EMPTY:
            continue
        text_preview = cp.text[:40] + "..." if len(cp.text) > 40 else cp.text
        print(f"  Para {cp.index}: [{cp.paragraph_type.value}] '{text_preview}'")
    
    # Show issues
    print("\nIssues:")
    for cat, issues in result.issues_by_category.items():
        if issues:
            print(f"\n  [{cat}]: {len(issues)} issues")
            for issue in issues[:3]:
                print(f"    - {issue.description}")
                print(f"      Current: {issue.current_value}, Expected: {issue.expected_value}")
except Exception as e:
    print(f"Error: {e}")
