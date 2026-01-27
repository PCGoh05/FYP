"""
DEEP TEMPLATE ANALYSIS
Verify if we are correctly extracting rules from the JIWE template
"""
import sys
sys.path.insert(0, '.')

from docx import Document
from modules.utils import get_paragraph_text, get_paragraph_font_info, get_paragraph_alignment

# Load template
doc = Document('sample/JIWE_Template.docx')

print("=" * 100)
print("DEEP TEMPLATE ANALYSIS - JIWE_Template.docx")
print("=" * 100)

print("\n" + "=" * 100)
print("PART 1: FIRST 20 PARAGRAPHS - RAW DATA")
print("=" * 100)

for i, para in enumerate(doc.paragraphs[:20]):
    text = get_paragraph_text(para)
    if not text:
        print(f"Para {i:2}: [EMPTY]")
        continue
    
    font_info = get_paragraph_font_info(para)
    alignment = get_paragraph_alignment(para)
    
    text_preview = text[:60].replace('\n', ' ') + ("..." if len(text) > 60 else "")
    
    print(f"\nPara {i:2}: '{text_preview}'")
    print(f"         Font: {font_info.get('font_name')}, Size: {font_info.get('font_size')}pt, Bold: {font_info.get('bold')}, Align: {alignment}")

print("\n" + "=" * 100)
print("PART 2: SEARCH FOR TEXT BOXES AND LABELS")
print("=" * 100)

from docx.oxml.ns import qn

body_xml = doc.element.body
all_p = body_xml.findall('.//' + qn('w:p'))

print(f"\nTotal XML paragraph elements: {len(all_p)}")
print("\nSearching for '(Title)' or similar labels...")

label_found = False
for idx, p_elem in enumerate(all_p[:50]):
    texts = [t.text for t in p_elem.findall('.//' + qn('w:t')) if t.text]
    full_text = ''.join(texts)
    
    # Look for labels
    if '(Title)' in full_text or '(Paper Title)' in full_text or 'Paper Title' in full_text:
        print(f"\nFound label at XML index {idx}:")
        print(f"  Text: {full_text[:100]}...")
        label_found = True

if not label_found:
    print("  No '(Title)' label found in XML elements")

print("\n" + "=" * 100)
print("PART 3: ANALYZE WHAT THE TEMPLATE IS ACTUALLY SAYING")
print("=" * 100)

print("""
Based on the template analysis:

Para 0: "(24- Font size, bold Palatino Linotype)"
  - This is INSTRUCTION TEXT telling users what format to use for the paper title
  - The instruction itself is formatted in Palatino Linotype 24pt Bold
  - BUT this might mean: "Use 24pt bold Palatino Linotype for your paper title"

THE KEY QUESTION:
  Is the template instruction telling users to use:
  A) Palatino Linotype (what the instruction text SAYS)
  B) Times New Roman (the more common academic font)
  C) Whatever the instruction paragraph is actually formatted in

CURRENT BEHAVIOR:
  We extract font_name from the instruction text content ("Palatino Linotype")
  This may or may not be the intended behavior depending on the template design.
""")

# Now let's check what the extracted rules actually are
print("\n" + "=" * 100)
print("PART 4: CURRENT EXTRACTED RULES")
print("=" * 100)

from modules.template_extractor import TemplateExtractor
extractor = TemplateExtractor()
extractor.load('sample/JIWE_Template.docx')
rules = extractor.extract_all_rules()

for key, value in rules.items():
    print(f"\n{key}:")
    if isinstance(value, dict):
        for k, v in value.items():
            print(f"    {k}: {v}")
    else:
        print(f"    {value}")
