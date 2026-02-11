"""
Test script to diagnose accuracy issues with sample files
"""

import sys
from pathlib import Path
from modules.template_extractor import TemplateExtractor
from modules.paragraph_classifier import ParagraphClassifier
from modules.manuscript_checker import ManuscriptChecker
from modules.auto_fixer import AutoFixer

def test_template_extraction():
    """Test template extraction to see what rules are extracted"""
    print("=" * 80)
    print("TESTING TEMPLATE EXTRACTION")
    print("=" * 80)
    
    template_path = Path("samples/JIWE_Template.docx")
    
    extractor = TemplateExtractor()
    extractor.load(template_path)
    rules = extractor.extract_all_rules()
    
    print("\n📋 Extracted Template Rules:")
    print("-" * 80)
    
    # Title rules
    title = rules.get("title", {})
    print(f"\n🏷️  TITLE:")
    print(f"   Font: {title.get('font_name')}")
    print(f"   Size: {title.get('font_size')}pt")
    print(f"   Bold: {title.get('bold')}")
    print(f"   Alignment: {title.get('alignment')}")
    
    # Heading rules
    heading = rules.get("heading", {})
    print(f"\n📌 HEADING:")
    print(f"   Font: {heading.get('font_name')}")
    print(f"   Size: {heading.get('font_size')}pt")
    print(f"   Bold: {heading.get('bold')}")
    
    # Body rules
    body = rules.get("body", {})
    print(f"\n📄 BODY:")
    print(f"   Font: {body.get('font_name')}")
    print(f"   Size: {body.get('font_size')}pt")
    
    # Abstract rules
    abstract = rules.get("abstract", {})
    print(f"\n📝 ABSTRACT:")
    print(f"   Font: {abstract.get('font_name')}")
    print(f"   Size: {abstract.get('font_size')}pt")
    
    return rules

def test_manuscript_checking(rules):
    """Test manuscript checking with first sample"""
    print("\n" + "=" * 80)
    print("TESTING MANUSCRIPT CHECKING")
    print("=" * 80)
    
    # Test with first article
    manuscript_path = Path("samples/2323-Article Text-19655-1-2-20250803 (1).docx")
    
    print(f"\n📄 Testing manuscript: {manuscript_path.name}")
    
    checker = ManuscriptChecker(rules)
    checker.load_manuscript(manuscript_path)
    result = checker.check_all()
    
    print(f"\n📊 Check Results:")
    print(f"   Compliance Score: {result.compliance_score}%")
    print(f"   Total Issues: {result.total_issues}")
    
    print(f"\n🔍 Issues by Category:")
    for category, issues in result.issues_by_category.items():
        if issues:
            print(f"\n   {category.upper()}: {len(issues)} issues")
            for i, issue in enumerate(issues[:3], 1):  # Show first 3
                print(f"      {i}. {issue.location}")
                print(f"         Current: {issue.current_value}")
                print(f"         Expected: {issue.expected_value}")
    
    print(f"\n📑 Paragraph Classifications (first 20):")
    print("-" * 80)
    for cp in result.classifications[:20]:
        print(f"   [{cp.index:3d}] {cp.paragraph_type.value:20s} | {cp.text[:60]}")
    
    return result

def test_auto_fix(rules, classifications):
    """Test auto-fixing to see what changes are made"""
    print("\n" + "=" * 80)
    print("TESTING AUTO-FIX")
    print("=" * 80)
    
    manuscript_path = Path("samples/2323-Article Text-19655-1-2-20250803 (1).docx")
    
    fixer = AutoFixer(rules, classifications)
    fixer.load_manuscript(manuscript_path)
    
    fixed_doc, changes = fixer.fix_all()
    
    print(f"\n🔧 Auto-Fix Results:")
    print(f"   Total Changes: {len(changes)}")
    
    print(f"\n📝 Changes by Type:")
    changes_by_type = {}
    for change in changes:
        change_type = change.change_type
        changes_by_type[change_type] = changes_by_type.get(change_type, 0) + 1
    
    for change_type, count in sorted(changes_by_type.items()):
        print(f"   {change_type}: {count}")
    
    print(f"\n🔍 Sample Changes (first 10):")
    print("-" * 80)
    for i, change in enumerate(changes[:10], 1):
        print(f"\n{i}. [{change.change_type}] Para {change.paragraph_index}")
        print(f"   Text: {change.text_preview[:50]}...")
        print(f"   Before: {change.before}")
        print(f"   After: {change.after}")
    
    return changes

def main():
    print("\n🔬 MANUSCRIPT CHECKER ACCURACY DIAGNOSTIC")
    print("\n")
    
    try:
        # Test 1: Template extraction
        rules = test_template_extraction()
        
        # Test 2: Manuscript checking
        result = test_manuscript_checking(rules)
        
        # Test 3: Auto-fixing
        changes = test_auto_fix(rules, result.classifications)
        
        print("\n" + "=" * 80)
        print("✅ DIAGNOSTIC COMPLETE")
        print("=" * 80)
        print("\nPlease review the output above to identify accuracy issues.")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
