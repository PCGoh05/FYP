# Automated Manuscript Template Compliance Checker

A rule-first, profile-based web application for checking academic manuscript
formatting against journal template rules. The primary validated case study is
Journal of Informatics and Web Engineering (JIWE). Optional LLM support is used
only to explain rule-detected results; it does not make compliance decisions.

## Features

### Core Functionality
- Template rule extraction from DOCX journal templates.
- Profile-based default rules, with JIWE as the validated default profile.
- Rule-based paragraph classification for journal headers, title, author info,
  body text, headings, captions, declarations, and references.
- Formatting checks for margins, page layout, journal header, title, author
  information, body text, headings, structure, tables, figures, references, and
  line spacing.
- Safer auto-fix for supported formatting issues only.
- Highlighted original document, corrected DOCX, and comparison report outputs.
- Smoke and labelled evaluation support through `evaluate_checker.py`.

### Optional LLM Layer
- Explains issues already detected by deterministic rules.
- Summarizes review priorities and post-fix results.
- Does not extract template rules, detect compliance issues, auto-fix content, or
  approve manuscripts.

## Project Structure

```text
FYP/
|-- app.py                      # Main Streamlit application
|-- config.py                   # Shared defaults and constants
|-- evaluate_checker.py         # Evaluation and smoke-test CLI
|-- template_profiles/
|   |-- jiwe.json               # Validated JIWE profile
|   `-- generic.json            # Generic fallback profile
|-- modules/
|   |-- template_extractor.py   # Extract rules from templates
|   |-- profile_loader.py       # Load and merge journal profiles
|   |-- paragraph_classifier.py # Rule-based paragraph classification
|   |-- manuscript_checker.py   # Rule-based compliance checker
|   |-- auto_fixer.py           # Supported formatting fixes
|   |-- report_generator.py     # Comparison report generation
|   |-- llm_integration.py      # Optional explanation layer
|   `-- utils.py                # Shared document utilities
|-- tests/                      # Regression tests
`-- docs/                       # Evaluation and implementation notes
```

## Installation

### Prerequisites
- Python 3.8 or higher
- pip

### Setup

1. Navigate to the project directory:
   ```bash
   cd "C:\Users\Acer\Desktop\latest fyp\FYP"
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Run the application:
   ```bash
   streamlit run app.py
   ```

5. Open the local URL shown by Streamlit.

## Usage Guide

### Step 1: Select Template Rules
1. Upload a journal template DOCX to extract formatting rules.
2. Or click "Use Default Rules" to use the validated JIWE default profile.
3. Review extracted, inferred, and defaulted rule sources in the sidebar.

### Step 2: Upload Manuscript
1. Upload a manuscript DOCX.
2. Click "Check Format".
3. Review the compliance index, document structure, and issue categories.

### Step 3: Review Issues
- "Compliance Index" is a user-facing rule-weighted indicator.
- Formal FYP accuracy should be reported with Precision, Recall, and F1-score
  using labelled samples.
- Issues are grouped by category and include current value, expected value, and
  evidence where available.

### Step 4: Auto-Fix Supported Formatting
1. Click "Auto-Fix All".
2. The system applies only supported, deterministic formatting fixes.
3. Remaining issues are shown separately for manual review.
4. Download the corrected DOCX, highlighted original DOCX, or comparison report.

## LLM Configuration

LLM usage is optional. Normal users do not need to enter an API key when the
deployed app has a server-managed key configured.

Supported key locations:
- Streamlit Secrets: `NVIDIA_API_KEY`
- Environment variable: `NVIDIA_API_KEY`
- Local developer override in the sidebar for testing only

If no valid key is configured, the checker still works and shows rule-based
explanations.

## Format Checking Categories

| Category | Description |
|----------|-------------|
| Page Margins | Left, right, top, and bottom margins |
| Layout | Page size and orientation |
| Journal Header | Journal name, volume line, and stable header spacing |
| Paper Title | Font, size, style, and alignment |
| Author Info | Author names, affiliations, and corresponding author lines |
| Body Text | Font, size, bold, line spacing, and alignment |
| Headings | Main heading and subheading formatting |
| Structure | Required sections and declaration sections |
| Tables | Caption presence, order, and numbering checks |
| Figures | Caption presence, order, and numbering checks |
| References | Reference section, citation consistency, and reference formatting |

## Evaluation

Run smoke evaluation with real JIWE samples:

```bash
python evaluate_checker.py --template "C:\Users\Acer\Downloads\FYP_SAMPLETEST\JIWE_Template-new_jan2026-OTH (8).docx" --samples "C:\Users\Acer\Downloads\FYP_SAMPLETEST\PUBLISHED\TEST" --auto-fix-evaluation
```

For formal FYP accuracy, create a labelled issue file and run:

```bash
python evaluate_checker.py --labels evaluation_labels.json
```

## Current Scope and Limitations

- JIWE is the main validated journal profile.
- Additional journals can be added through `template_profiles`, but each journal
  still needs validation with real samples.
- DOCX handling is the most reliable path.
- PDF upload can be converted for checking when dependencies are available.
- PDF download is only offered when a high-fidelity Microsoft Word conversion
  backend is available; low-fidelity LibreOffice conversion is avoided because it
  can shift Word layouts.
- Auto-fix does not move figures/tables, rewrite content, generate missing
  sections, or approve manuscripts.

## Privacy

- Core checking runs locally in the app process.
- LLM requests, when enabled, use grouped and redacted issue metadata rather than
  full manuscripts.
- Uploaded documents are not intentionally stored after the session.

## License

This project is developed as a Final Year Project (FYP).
