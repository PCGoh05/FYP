"""
Full Flow Test - Test the complete format checking workflow
"""
from modules.template_extractor import TemplateExtractor
from modules.manuscript_checker import ManuscriptChecker
from modules.paragraph_classifier import ParagraphType
import json

# 1. Load template and extract rules
print("=" * 60)
print("1. TEMPLATE EXTRACTION")
print("=" * 60)

extractor = TemplateExtractor()
extractor.load('sample/JIWE_Template.docx')
rules = extractor.extract_all_rules()

# Print key rules
print(f"\nExtracted Rules:")
print(f"  - Title: {rules.get('title', {}).get('font_size')}pt, Bold: {rules.get('title', {}).get('bold')}")
print(f"  - Author: {rules.get('author', {}).get('font_size')}pt, Bold: {rules.get('author', {}).get('bold')}")
print(f"  - Affiliation: {rules.get('affiliation', {}).get('font_size')}pt")
print(f"  - Abstract: {rules.get('abstract', {}).get('font_size')}pt")
print(f"  - Body: {rules.get('body', {}).get('font_size')}pt")
print(f"  - Heading: {rules.get('heading', {}).get('font_size')}pt, Bold: {rules.get('heading', {}).get('bold')}")
print(f"  - Reference: {rules.get('reference', {}).get('font_size')}pt")

# 2. Use the same template as manuscript to test (should be fully compliant)
print("\n" + "=" * 60)
print("2. MANUSCRIPT CHECK (Template as Manuscript)")
print("=" * 60)

checker = ManuscriptChecker(rules, llm_integration=None)
checker.load_manuscript('sample/JIWE_Template.docx')
result = checker.check_all()

print(f"\nCompliance Score: {result.compliance_score}%")
print(f"Total Issues: {result.total_issues}")

# Print classification info
print(f"\n3. PARAGRAPH CLASSIFICATIONS:")
print("-" * 60)

type_counts = {}
for cp in result.classifications[:30]:  # First 30 paragraphs
    ptype = cp.paragraph_type.value
    type_counts[ptype] = type_counts.get(ptype, 0) + 1
    
    if cp.paragraph_type in [ParagraphType.PAPER_TITLE, ParagraphType.SECTION_HEADING, 
                              ParagraphType.BODY, ParagraphType.ABSTRACT_CONTENT]:
        preview = cp.text[:50] + "..." if len(cp.text) > 50 else cp.text
        font_size = cp.font_info.get('font_size')
        print(f"  [{ptype}] Para {cp.index}: size={font_size}pt, '{preview}'")

print(f"\nType Counts: {type_counts}")

# 4. Print all issues
print(f"\n4. ALL ISSUES FOUND:")
print("-" * 60)

if result.total_issues == 0:
    print("  [OK] No issues found! Template is self-compliant.")
else:
    for category, issues in result.issues_by_category.items():
        if issues:
            print(f"\n  [{category}] ({len(issues)} issues)")
            for issue in issues[:5]:  # Show max 5 per category
                print(f"    - {issue.description}")
                print(f"      Current: {issue.current_value}, Expected: {issue.expected_value}")
                if issue.text_preview:
                    print(f"      Text: '{issue.text_preview}'")
