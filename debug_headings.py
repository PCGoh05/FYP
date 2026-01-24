"""Debug heading bold detection"""
from docx import Document
from modules.utils import get_run_font_info, get_paragraph_text
import re

doc = Document('sample/JIWE_Template.docx')

print('=== ALL PARAGRAPHS WITH HEADING KEYWORDS ===')
heading_keywords = ['introduction', 'literature', 'methodology', 'result', 'discussion', 
                    'conclusion', 'reference', 'abstract', 'keyword']

for i, para in enumerate(doc.paragraphs):
    text = get_paragraph_text(para)
    text_lower = text.lower()
    
    # Check if contains heading keywords
    if any(kw in text_lower for kw in heading_keywords) and len(text) < 100:
        print(f'\nPara {i}: "{text[:60]}..."')
        for run in para.runs:
            if run.text.strip():
                info = get_run_font_info(run)
                print(f'  Run: "{run.text[:30]}" -> bold={info.get("bold")}, size={info.get("font_size")}')
