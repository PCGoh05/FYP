"""
Comprehensive accuracy test - analyze ALL issues
"""
from modules.template_extractor import TemplateExtractor, _parse_instruction_format
from modules.manuscript_checker import ManuscriptChecker
from modules.paragraph_classifier import ParagraphType, ParagraphClassifier
from modules.utils import get_paragraph_text, get_paragraph_font_info
import json

# 1. Load template and extract rules
print("=" * 80)
print("COMPREHENSIVE ACCURACY ANALYSIS")
print("=" * 80)

extractor = TemplateExtractor()
extractor.load('sample/JIWE_Template.docx')
rules = extractor.extract_all_rules()

print("\n1. EXTRACTED RULES:")
print("-" * 40)
for key, value in rules.items():
    print(f"  {key}: {value}")

# 2. Analyze ALL paragraphs in document
print("\n2. ALL PARAGRAPH CLASSIFICATIONS:")
print("-" * 80)

checker = ManuscriptChecker(rules)
checker.load_manuscript('sample/JIWE_Template.docx')
result = checker.check_all()

# Print ALL classifications (not just sample)
for cp in result.classifications:
    if cp.paragraph_type == ParagraphType.EMPTY:
        continue
    
    text_preview = cp.text[:50] + "..." if len(cp.text) > 50 else cp.text
    should_fix = "FIX" if cp.should_fix else "SKIP"
    
    # Check if this paragraph has issues
    has_issues = False
    issues_for_para = []
    for cat, issues in result.issues_by_category.items():
        for issue in issues:
            if issue.paragraph_index == cp.index:
                has_issues = True
                issues_for_para.append(f"{cat}: {issue.description}")
    
    status = "[!]" if has_issues else "[OK]"
    print(f"{status}[{cp.paragraph_type.value:20}] Para {cp.index:2}: conf={cp.confidence:.2f} {should_fix} | '{text_preview}'")
    
    if has_issues:
        for issue_desc in issues_for_para:
            print(f"      └─ ISSUE: {issue_desc}")

# 3. Summary of issues by category
print("\n3. ISSUES SUMMARY:")
print("-" * 40)
for category, issues in result.issues_by_category.items():
    if issues:
        print(f"\n  [{category}] - {len(issues)} issues:")
        for issue in issues:
            print(f"    - {issue.description}")
            print(f"      Current: {issue.current_value}")
            print(f"      Expected: {issue.expected_value}")

# 4. Check if heading extraction is correct
print("\n4. HEADING RULE ANALYSIS:")
print("-" * 40)
print(f"  Extracted heading rule: {rules.get('heading', {})}")

# Find all headings in document
headings = [cp for cp in result.classifications if cp.paragraph_type == ParagraphType.SECTION_HEADING]
print(f"  Found {len(headings)} headings:")
for h in headings[:10]:
    text_preview = h.text[:40] + "..." if len(h.text) > 40 else h.text
    print(f"    - Para {h.index}: size={h.font_info.get('font_size')}pt, bold={h.font_info.get('bold')}, '{text_preview}'")
