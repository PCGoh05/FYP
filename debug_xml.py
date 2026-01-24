"""Debug heading bold from XML"""
from docx import Document
from docx.oxml.ns import qn

doc = Document('sample/JIWE_Template.docx')

print('=== INTRODUCTION PARAGRAPH XML DEBUG ===')
for i, para in enumerate(doc.paragraphs):
    if 'INTRODUCTION' in para.text and i < 15:
        print(f'\nPara {i}: "{para.text[:40]}"')
        
        # Check paragraph style
        if para.style:
            print(f'  Style: {para.style.name}')
            if para.style.font:
                print(f'  Style Bold: {para.style.font.bold}')
        
        # Check each run
        for j, run in enumerate(para.runs):
            if run.text.strip():
                print(f'\n  Run {j}: "{run.text[:20]}"')
                
                # Direct API
                print(f'    API bold: {run.font.bold}')
                
                # From XML
                rPr = run._element.rPr
                if rPr is not None:
                    b = rPr.find(qn('w:b'))
                    if b is not None:
                        b_val = b.get(qn('w:val'))
                        print(f'    XML w:b element found, val={b_val}')
                    else:
                        print(f'    XML: no w:b element')
                else:
                    print(f'    XML: no rPr element')
                
                # Print raw XML
                print(f'    Raw XML: {run._element.xml[:200] if len(run._element.xml) > 200 else run._element.xml}')
        break
