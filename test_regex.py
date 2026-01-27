import re

text = "(24- Font size, bold Palatino Linotype)"

# Test bold extraction
bold_match = re.search(r'\bbold\b', text, re.IGNORECASE)
print(f"Bold match: {bold_match}")
print(f"Bold found: {bold_match is not None}")

# Test size extraction
size_match = re.search(r'\((\d+)\s*[-]?\s*[Ff]ont', text)
print(f"Size match: {size_match.group(1) if size_match else None}")

# Test font extraction
font_patterns = [
    r'(Palatino\s*Linotype)',
    r'(Times\s*New\s*Roman)',
]
for pattern in font_patterns:
    font_match = re.search(pattern, text, re.IGNORECASE)
    if font_match:
        print(f"Font match: {font_match.group(1)}")
        break
