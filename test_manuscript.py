"""
Analyze the user's real manuscript against the template
"""
import sys
sys.path.insert(0, '.')

from modules.template_extractor import TemplateExtractor
from modules.manuscript_checker import ManuscriptChecker
from modules.paragraph_classifier import ParagraphType
from modules.utils import get_paragraph_text, get_paragraph_font_info

# 1. Load template and extract rules
print("=" * 80)
print("1. TEMPLATE RULES")
print("=" * 80)

extractor = TemplateExtractor()
extractor.load('sample/JIWE_Template.docx')
rules = extractor.extract_all_rules()

print(f"Title: {rules.get('title')}")
print(f"Author: {rules.get('author')}")
print(f"Body: {rules.get('body')}")
print(f"Heading: {rules.get('heading')}")
print(f"Abstract: {rules.get('abstract')}")

# 2. Check the manuscript
print("\n" + "=" * 80)
print("2. MANUSCRIPT ANALYSIS")
print("=" * 80)

manuscript_path = r'sample\2201-Article Text-18548-1-2-20250715 (1).docx'
checker = ManuscriptChecker(rules)
checker.load_manuscript(manuscript_path)
result = checker.check_all()

print(f"\nCompliance Score: {result.compliance_score}%")
print(f"Total Issues: {result.total_issues}")

# 3. Show first 15 paragraphs and their classifications
print("\n" + "=" * 80)
print("3. PARAGRAPH CLASSIFICATIONS (first 15)")
print("=" * 80)

for cp in result.classifications[:15]:
    if cp.paragraph_type == ParagraphType.EMPTY:
        continue
    
    text_preview = cp.text[:50].replace('\n', ' ') + ("..." if len(cp.text) > 50 else "")
    font_name = cp.font_info.get('font_name', '?')
    font_size = cp.font_info.get('font_size', '?')
    bold = cp.font_info.get('bold', '?')
    fix_status = "FIX" if cp.should_fix else "SKIP"
    
    print(f"Para {cp.index:2} [{cp.paragraph_type.value:20}] {fix_status}")
    print(f"         Font: {font_name}, Size: {font_size}pt, Bold: {bold}")
    print(f"         Text: '{text_preview}'")

# 4. Show all issues
print("\n" + "=" * 80)
print("4. ALL ISSUES DETECTED")
print("=" * 80)

for category, issues in result.issues_by_category.items():
    if issues:
        print(f"\n[{category}] - {len(issues)} issues:")
        for issue in issues[:5]:  # Show first 5 per category
            print(f"  - {issue.description}")
            print(f"    Current: {issue.current_value}")
            print(f"    Expected: {issue.expected_value}")
            if issue.text_preview:
                preview = issue.text_preview[:40] + "..." if len(issue.text_preview) > 40 else issue.text_preview
                print(f"    Text: '{preview}'")
