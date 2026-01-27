"""Enhanced debug script to trace title extraction flow"""
import sys
sys.path.insert(0, '.')

from modules.template_extractor import TemplateExtractor, _parse_instruction_format
from modules.utils import get_paragraph_text, get_paragraph_font_info

# Load the template
extractor = TemplateExtractor()
extractor.load('sample/JIWE_Template.docx')

print("=== Scanning first 15 paragraphs ===")
for i, para in enumerate(extractor.document.paragraphs[:15]):
    text = get_paragraph_text(para)
    if not text:
        continue
    font_info = get_paragraph_font_info(para)
    text_preview = text[:60] + "..." if len(text) > 60 else text
    print(f"Para {i}: size={font_info.get('font_size')}pt, '{text_preview}'")
    
    # Try parsing instruction on each
    instruction = _parse_instruction_format(text)
    if instruction:
        print(f"         -> Instruction: {instruction}")

print("\n=== Checking for '(Title)' in document ===")
from docx.oxml.ns import qn
body_xml = extractor.document.element.body
all_p = body_xml.findall('.//' + qn('w:p'))
for p_elem in all_p[:20]:
    texts = [t.text for t in p_elem.findall('.//' + qn('w:t')) if t.text]
    full_text = ''.join(texts)
    if '(Title)' in full_text:
        print(f"Found (Title): {full_text[:80]}...")
        break
else:
    print("No '(Title)' keyword found in first 20 elements")

print("\n=== Final extracted rules ===")
rules = extractor.extract_all_rules()
print(f"Title: font={rules['title'].get('font_name')}, size={rules['title'].get('font_size')}, bold={rules['title'].get('bold')}")
