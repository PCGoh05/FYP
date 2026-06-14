# Project Context

## Project

Automated Manuscript Template Compliance Checker for academic journal submissions.

The working project path is:

```text
C:\Users\Acer\Desktop\latest fyp\FYP
```

## Core Direction

- The checker must be rule-first, not LLM-first.
- LLM usage is optional and should be limited to explanations or report assistance.
- Detection, correction, reporting, and evaluation should be explainable.
- Code comments, docstrings, CLI text, generated files, and repository documentation should remain English-only.
- After each completed code change, commit and push to GitHub.

## Current Architecture

- `app.py`: Streamlit UI for template upload, manuscript upload, checking, fixing, highlighting, and downloads.
- `config.py`: application constants and remaining default rule/pattern definitions.
- `evaluate_checker.py`: smoke testing and manual-label evaluation entry point.
- `template_profiles/jiwe.json`: validated JIWE journal profile.
- `template_profiles/generic.json`: generic academic fallback profile.
- `modules/profile_loader.py`: loads, detects, normalizes, and merges template profiles.
- `modules/template_extractor.py`: extracts formatting rules from uploaded templates and attaches provenance.
- `modules/paragraph_classifier.py`: deterministic, profile-aware paragraph classifier.
- `modules/manuscript_checker.py`: rule-based validation engine that creates formatting issues.
- `modules/auto_fixer.py`: applies safer issue-based formatting fixes.
- `modules/report_generator.py`: report generation.
- `modules/llm_integration.py`: optional explanation layer only.
- `modules/utils.py`: DOCX/PDF utilities and shared helpers.

## Validated Profile

JIWE is the main validated profile.

Important JIWE rules currently encoded:

- Journal header: Palatino Linotype, 24 pt, bold, centered.
- Paper title: Times New Roman, 24 pt, centered.
- Body text: Times New Roman, 10 pt.
- Section headings: Times New Roman, 10 pt.
- Captions: Times New Roman, 10 pt.
- References: Times New Roman, 9 pt.
- Page size: Letter.

## Recent Important Commits

```text
4558b36 Restrict auto-fix to detected issue properties
83f97a6 Make paragraph classification profile-aware
e714fae Centralize template profile loading
d476d06 Fix heading numbering formatting
263ea53 Ignore locked temp files after PDF conversion
```

## Current Improvements Already Made

- Template rules are now profile-based through `ProfileLoader`.
- JIWE and Generic profiles include full default formatting rules.
- Paragraph classification can read profile `classification_patterns`.
- Auto-fix is safer because it only fixes properties connected to detected issues.
- Heading numbering formatting is detected and fixed through Word numbering XML.
- Reference entries are checked and fixed across the full references section.
- LLM is not used in the core checking path.
- `evaluate_checker.py` skips Word temp files and supports manual-label evaluation.

## Known Risks

- `modules/auto_fixer.py` still contains duplicate old and new method implementations. Python uses the later definitions, but the file is confusing and should be cleaned carefully.
- Some JIWE assumptions still exist in Python logic, especially around journal header detection and title behavior.
- PDF handling is still less robust than DOCX handling.
- Compliance score is only a UI-friendly index. FYP accuracy should use Precision, Recall, and F1 from labelled samples.
- Multi-journal support is profile-based but not fully universal.

## Recommended Next Task

Clean up `modules/auto_fixer.py` without changing behavior:

1. Identify duplicate old methods that are overridden by later definitions.
2. Remove dead duplicate implementations carefully.
3. Keep the structured, issue-based implementations.
4. Run:

```text
python -m py_compile modules\auto_fixer.py modules\manuscript_checker.py app.py evaluate_checker.py
python evaluate_checker.py
```

5. Confirm no Chinese characters exist in changed code files.
6. Commit and push.

## FYP Framing

Best defensible project framing:

```text
A rule-first, profile-based manuscript template compliance checker with explainable issue detection, safer auto-correction, highlighted outputs, and measurable accuracy evaluation.
```

Avoid claiming that the system perfectly understands every journal template automatically. The stronger claim is that the architecture supports journal profiles and JIWE is the primary validated case study.
