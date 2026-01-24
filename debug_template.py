"""
Debug script to analyze JIWE template formatting in detail
"""
from docx import Document
from modules.utils import get_paragraph_font_info, get_paragraph_alignment, get_paragraph_text

# Load template
doc = Document('sample/JIWE_Template.docx')

print("=" * 80)
print("DETAILED JIWE TEMPLATE ANALYSIS")
print("=" * 80)

# Analyze first 30 paragraphs
for i, para in enumerate(doc.paragraphs[:30]):
    text = get_paragraph_text(para)
    if not text or len(text.strip()) < 3:
        continue
    
    font_info = get_paragraph_font_info(para)
    alignment = get_paragraph_alignment(para)
    
    # Also get direct run info
    run_fonts = []
    run_sizes = []
    run_bolds = []
    run_italics = []
    
    for run in para.runs:
        if run.text.strip():
            run_fonts.append(run.font.name)
            run_sizes.append(run.font.size.pt if run.font.size else None)
            run_bolds.append(run.font.bold)
            run_italics.append(run.font.italic)
    
    preview = text[:60] + "..." if len(text) > 60 else text
    
    print(f"\n[Para {i}] {preview}")
    print(f"  Font: {font_info.get('font_name')}, Size: {font_info.get('font_size')}pt")
    print(f"  Bold: {font_info.get('bold')}, Italic: {font_info.get('italic')}")
    print(f"  Alignment: {alignment}")
    print(f"  Run fonts: {set(run_fonts)}")
    print(f"  Run sizes: {set(run_sizes)}")
    print(f"  Run bolds: {set(run_bolds)}")
    print(f"  Run italics: {set(run_italics)}")
