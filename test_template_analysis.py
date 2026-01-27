"""
Analyze what the JIWE template ACTUALLY says the paper title should be
"""
import sys
sys.path.insert(0, '.')

from modules.template_extractor import TemplateExtractor, _parse_instruction_format
from modules.utils import get_paragraph_text, get_paragraph_font_info

extractor = TemplateExtractor()
extractor.load('sample/JIWE_Template.docx')

print("=" * 80)
print("ANALYZING TITLE INSTRUCTION IN TEMPLATE")
print("=" * 80)

# Look at first 5 paragraphs
for i, para in enumerate(extractor.document.paragraphs[:8]):
    text = get_paragraph_text(para)
    if not text:
        continue
    font_info = get_paragraph_font_info(para)
    
    print(f"\nPara {i}:")
    print(f"  Text: {text[:80]}...")
    print(f"  Actual font: {font_info.get('font_name')}")
    print(f"  Actual size: {font_info.get('font_size')}pt")
    print(f"  Actual bold: {font_info.get('bold')}")
    
    # Parse instruction if present
    instruction = _parse_instruction_format(text)
    if instruction:
        print(f"  Instruction says: {instruction}")

print("\n" + "=" * 80)
print("QUESTION: What font should the paper title actually use?")
print("=" * 80)
print("""
Looking at the template, Para 0 says:
  "(24- Font size, bold Palatino Linotype)"

This means:
  - Font size: 24pt
  - Bold: Yes
  - Font name: Palatino Linotype

BUT the user's manuscript in the screenshot uses a different font for the title!
The system is correctly detecting this mismatch.

HOWEVER - the real question is: Does JIWE want Palatino Linotype or Times New Roman?

Looking at the published JIWE papers, they typically use Times New Roman for body text.
The "Palatino Linotype" in the template instruction might be WRONG or just for the template example.
""")
