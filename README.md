# Automated Manuscript Template Compliance Checker

A comprehensive web application for checking and fixing academic manuscript formatting against journal templates. Built with Python Streamlit and featuring LLM integration (Groq) for intelligent analysis.

## 🎯 Features

### Core Functionality
- **Template Rule Extraction**: Automatically extract formatting rules from any journal template (.docx)
- **10-Category Format Checking**: Comprehensive checks for margins, title, body text, headings, structure, tables, figures, references, line spacing, and overall compliance
- **Intelligent Paragraph Classification**: Smart classifier to identify and preserve special content (journal headers, author info, etc.)
- **Auto-Fix System**: Automatically correct formatting issues while preserving special formatting
- **Turnitin-Style Comparison View**: Visual comparison showing before/after changes
- **Two Output Files**: Corrected document and detailed comparison report

### LLM Integration (Optional)
- Intelligent error explanations
- Abstract quality analysis
- Smart paragraph classification fallback
- Writing suggestions

## 📁 Project Structure

```
FYP/
├── app.py                      # Main Streamlit application
├── config.py                   # Configuration settings
├── requirements.txt            # Python dependencies
├── README.md                   # This file
├── assets/
│   └── styles.css             # Custom CSS styles
└── modules/
    ├── __init__.py
    ├── template_extractor.py  # Extract rules from templates
    ├── paragraph_classifier.py # Intelligent paragraph classification
    ├── manuscript_checker.py   # Format checking engine
    ├── auto_fixer.py          # Auto-fix formatting issues
    ├── report_generator.py    # Generate comparison reports
    ├── llm_integration.py     # LLM integration (Groq)
    └── utils.py               # Utility functions
```

## 🚀 Installation

### Prerequisites
- Python 3.8 or higher
- pip (Python package manager)

### Step-by-Step Installation

1. **Navigate to the project directory:**
   ```bash
   cd "c:\Users\Acer\Desktop\latest fyp\FYP"
   ```

2. **Create a virtual environment (recommended):**
   ```bash
   python -m venv venv
   
   # On Windows:
   venv\Scripts\activate
   
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application:**
   ```bash
   streamlit run app.py
   ```

5. **Open in browser:**
   The application will automatically open at `http://localhost:8501`

## 📖 Usage Guide

### Step 1: Upload Template (Optional)
1. Click on "Upload Template" section
2. Upload a journal template document (.docx)
3. The system will automatically extract formatting rules
4. View extracted rules in the sidebar

*Alternatively, click "Use Default Rules" to use IEEE-style formatting*

### Step 2: Upload Manuscript
1. Upload your manuscript document (.docx)
2. Click "Check Format" button
3. View compliance score and issues found

### Step 3: Review Results
- **Compliance Score**: Overall formatting compliance percentage
- **Document Structure**: Check for required sections (Abstract, Introduction, etc.)
- **Issues by Category**: Detailed view of all formatting issues

### Step 4: Auto-Fix
1. Click "Auto-Fix All" button
2. Review the comparison view showing all changes
3. Download the corrected document and comparison report

## 🤖 LLM Configuration

### Using Groq (Cloud - Recommended)
1. Get a free API key from [console.groq.com](https://console.groq.com)
2. In the sidebar, expand "LLM Settings"
3. Select "Groq (Cloud)"
4. Enter your API key

### Using Ollama (Local)
1. Install Ollama from [ollama.ai](https://ollama.ai)
2. Run `ollama pull llama3.1`
3. Start Ollama server
4. In the sidebar, select "Ollama (Local)"

## 📋 Format Checking Categories

| Category | Description |
|----------|-------------|
| **Page Margins** | Left, right, top, bottom margins |
| **Paper Title** | Font, size, bold, alignment |
| **Body Text** | Font name and size consistency |
| **Section Headings** | Heading formatting |
| **Document Structure** | Required sections check |
| **Tables** | Table presence and captions |
| **Figures** | Figure presence and captions |
| **References** | Format consistency (IEEE/APA) |
| **Line Spacing** | Paragraph spacing |
| **Overall Compliance** | Calculated percentage score |

## 🎨 Paragraph Classification

The system intelligently classifies paragraphs to avoid modifying content that should be preserved:

**Preserved (Not Modified):**
- Journal headers (ISSN, DOI, etc.)
- Author information
- Section labels (Abstract, Keywords)

**Fixed (Format Corrected):**
- Paper title
- Section headings
- Body text
- Abstract content
- Captions
- References

## 📤 Output Files

### 1. Corrected Document
- Original content preserved
- All formatting issues fixed
- Ready for submission

### 2. Comparison Report
- Summary of changes
- Target format rules
- Detailed change log
- Color-coded before/after

## ⚙️ Configuration

Edit `config.py` to customize:

```python
# Default formatting rules
DEFAULT_RULES = {
    "margins": {"left": 1.0, "right": 1.0, "top": 1.0, "bottom": 1.0},
    "title": {"font_name": "Times New Roman", "font_size": 24, "bold": True},
    "body": {"font_name": "Times New Roman", "font_size": 12, "line_spacing": 1.5},
    # ... more rules
}

# LLM settings
LLM_CONFIG = {
    "provider": "groq",
    "groq_model": "llama-3.1-8b-instant",
    # ... more settings
}
```

## 🐛 Troubleshooting

### Common Issues

**1. Module not found error:**
```bash
pip install -r requirements.txt
```

**2. Streamlit not starting:**
```bash
pip install --upgrade streamlit
```

**3. Document parsing error:**
- Ensure the document is a valid .docx file
- Check file is not corrupted or password-protected

**4. LLM connection failed:**
- Verify API key is correct (Groq)
- Ensure Ollama is running (Local)

## 🔒 Privacy

- All document processing is done locally
- LLM analysis only sends text snippets (not full documents)
- No data is stored after session ends

## 📝 License

This project is developed as a Final Year Project (FYP).

## 🤝 Contributing

Feel free to submit issues and enhancement requests!

## 📧 Support

For questions or support, please contact the project maintainer.

---

**Built with ❤️ using Python, Streamlit, and python-docx**
