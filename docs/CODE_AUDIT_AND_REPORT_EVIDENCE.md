# Code Audit and Final Report Evidence

## Purpose

This document records the code evidence that should be used when writing the FYP2 final report for the project:

**Automated Manuscript Template Compliance Checker for Academic Journals**

The final report should present the work as a research-based project supported by a proof-of-concept prototype. The prototype demonstrates and evaluates a rule-first, profile-based approach for checking academic manuscript template compliance. The system should not be described as a purely application-based product or as an autonomous editorial decision system.

## Handbook and FYP1 Evidence Used

The FYP handbook states that a research-based FYP2 final report should include:

- Chapter 1: Introduction
- Chapter 2: Literature Review
- Chapter 3: Theoretical Framework
- Chapter 4: Research Methodology
- Chapter 5: Data Analysis and Results
- Chapter 6: Discussion
- Chapter 7: Conclusion and Recommendations

The handbook also indicates that FYP2 report assessment includes abstract, problem statement, objectives, literature review, solution, analysis or discussion, conclusion, writing organization, figures, tables, references, and appendices. Therefore, the report should emphasize research framing, theoretical basis, methodology, prototype evidence, evaluation design, and discussion of limitations.

The supplied FYP1 report file was used only as a formatting and organization reference for preliminary pages and chapter presentation. Its project topic does not match the current FYP2 project and should not be reused as technical content.

## Repository Structure

```text
FYP/
|-- app.py
|-- config.py
|-- evaluate_checker.py
|-- requirements.txt
|-- README.md
|-- PROJECT_CONTEXT.md
|-- assets/
|   `-- styles.css
|-- docs/
|   `-- evaluation_guide.md
|-- evaluation_results/
|   |-- published_auto_fix_summary.md
|   |-- declined_auto_fix_summary.md
|   |-- published_alignment_rules.md
|   |-- declined_sdt_references.md
|   |-- phase1_keywords_published.json
|   |-- phase1_keywords_declined.json
|   |-- phase2_author_published.json
|   |-- phase2_author_declined.json
|   |-- phase3_layout_published.json
|   |-- phase4_abstract_published.json
|   `-- phase5_declarations_published.json
|-- modules/
|   |-- auto_fixer.py
|   |-- llm_integration.py
|   |-- manuscript_checker.py
|   |-- paragraph_classifier.py
|   |-- profile_loader.py
|   |-- report_generator.py
|   |-- review_guidance.py
|   |-- template_extractor.py
|   `-- utils.py
|-- template_profiles/
|   |-- generic.json
|   `-- jiwe.json
`-- tests/
    `-- regression test files
```

## Main Modules and Roles

| File | Role in the prototype | Report evidence |
|---|---|---|
| `app.py` | Streamlit user interface for template upload, manuscript upload, checking, review guidance, auto-fix, validation, and downloads. | Supports the implementation and user interface sections. |
| `config.py` | Shared constants, default values, and configuration for rules and optional LLM. | Supports the prototype configuration description. |
| `evaluate_checker.py` | Command-line smoke evaluation, labelled evaluation support, auto-fix before/after evaluation, and summary artifact generation. | Supports Chapter 5 evaluation design and results. |
| `template_profiles/jiwe.json` | Validated JIWE journal profile with required sections, declaration requirements, classification patterns, rule weights, and formatting rules. | Supports the profile-based rule representation section. |
| `template_profiles/generic.json` | Generic fallback journal profile. | Supports extensibility discussion. |
| `modules/profile_loader.py` | Loads, detects, normalizes, and merges journal profiles with extracted rules. | Supports the profile-based architecture. |
| `modules/template_extractor.py` | Extracts formatting rules and instruction-derived requirements from DOCX templates. | Supports template rule extraction method. |
| `modules/paragraph_classifier.py` | Rule-based paragraph classification using text, formatting, position, and profile patterns. | Supports the rule-first classification method. |
| `modules/manuscript_checker.py` | Main deterministic validation engine that creates `FormatIssue` and `CheckResult` records. | Supports compliance checking and issue categories. |
| `modules/auto_fixer.py` | Applies safer formatting corrections based on detected issue properties; validates post-fix results. | Supports auto-correction and safety validation. |
| `modules/report_generator.py` | Generates a comparison report explaining changed properties, target rules, and validation summary. | Supports report generation output. |
| `modules/review_guidance.py` | Builds deterministic review guidance payloads and fallback explanations from rule-detected issues. | Supports optional review guidance without relying on LLM decisions. |
| `modules/llm_integration.py` | Optional NVIDIA API integration for explanations and review guidance only. | Supports the optional AI explanation layer. |
| `modules/utils.py` | Shared DOCX/PDF utilities, font extraction, margin handling, scoring, reference helpers, and PDF backend selection. | Supports implementation details and limitations. |

## Implemented Features Confirmed by Code

The following features are supported by the current codebase and can be described in the FYP2 report:

- Streamlit web interface.
- DOCX template upload and template rule extraction.
- Default JIWE profile loaded through profile-based rules.
- Generic fallback profile.
- DOCX manuscript upload.
- PDF upload conversion to DOCX when `pdf2docx` is available.
- Rule-based paragraph classification.
- Margin checking.
- Page layout checking, including page size and orientation.
- Journal header checking.
- Paper title checking.
- Author name, affiliation, and corresponding author information checking.
- Body text font, size, bold, line spacing, and alignment checking.
- Heading and subheading checking.
- Required section checking.
- Required declaration checking.
- Table and figure caption checks.
- Reference section and reference formatting checks.
- Citation and reference consistency checks.
- Equation-related checks.
- Abstract word count and content restriction checks.
- Keyword requirement checks.
- Compliance index calculation.
- Issue categorisation by rule area.
- Safer issue-based auto-fix for supported deterministic formatting properties.
- Corrected DOCX output.
- Highlighted original DOCX output.
- Comparison report DOCX output.
- Post-fix validation by re-checking the corrected document.
- Optional AI issue explanation and review guidance.
- Rule-based fallback guidance when LLM is unavailable.
- Smoke evaluation and auto-fix before/after evaluation through `evaluate_checker.py`.
- Label template export and labelled metric calculation support for precision, recall, and F1-score.

## JIWE Rules Confirmed by Profile

The current JIWE profile encodes the following main rules:

- Required sections: Abstract, Keywords, Introduction, Conclusion, References.
- Required declarations: funding statement, author contributions, conflict of interests, data availability.
- Journal header: Palatino Linotype, 24 pt, bold, centered.
- Paper title: Times New Roman, 24 pt, centered.
- Author names: Times New Roman, 11 pt, bold, centered.
- Affiliations: Times New Roman, 9 pt, centered.
- Corresponding author: Times New Roman, 9 pt, italic, centered, email and ORCID required.
- Body text: Times New Roman, 10 pt, justified, 1.0 line spacing.
- Main headings: Times New Roman, 10 pt, bold, all caps.
- Subheadings: Times New Roman, 10 pt, italic.
- Abstract: Times New Roman, 9 pt, justified, 200 to 300 words, one paragraph, no equations, no tables or figures, and no citations.
- Keywords: Times New Roman, 9 pt, italic, at least five keywords.
- Captions: Times New Roman, 10 pt.
- References: Times New Roman, 9 pt, justified, 1.15 line spacing, publication title italic requirement.
- Layout: single column, Letter page size, portrait orientation.

## Partially Implemented or Risky Features

These features exist but should be described carefully:

| Feature | Current status | Safe report wording |
|---|---|---|
| PDF upload | Available when `pdf2docx` is installed, but conversion quality depends on source PDF structure. | PDF upload is supported as a convenience path, while DOCX remains the primary reliable format. |
| PDF download | Only offered when a high-fidelity Microsoft Word backend is available. Low-fidelity LibreOffice conversion is avoided. | Final PDF should be exported from the corrected DOCX using Microsoft Word to preserve layout. |
| Multi-journal support | Architecture supports profiles, but JIWE is the validated case study. | The system is profile-based and can be extended to other journals after validation. |
| Template extraction | Extracts many observable rules and instruction-based requirements, but some rules need profile fallback or validation. | Template extraction is combined with profile defaults and rule provenance. |
| Compliance index | Implemented as a rule-weighted user-facing score. | Accuracy must be evaluated with precision, recall, and F1-score using labelled samples. |
| Auto-fix | Supports deterministic formatting corrections, not semantic rewriting or object repositioning. | Auto-fix is intentionally conservative and leaves risky changes for manual review. |
| LLM support | Optional explanations and guidance only. | AI does not detect issues, make compliance decisions, or approve manuscripts. |

## Unsupported Features That Should Be Future Work Only

The report should not claim that the prototype currently provides:

- Full autonomous manuscript rewriting.
- Full citation style conversion.
- CrossRef, PubMed, or external bibliographic verification.
- Complete double-column layout reconstruction.
- Automatic figure and table repositioning.
- Complete universal multi-journal compliance without per-journal validation.
- LLM-based compliance decision making.
- A trained machine learning classifier.
- Semantic evaluation of research quality.
- Guaranteed PDF output in every deployment environment.
- Guaranteed detection of every possible formatting issue.

## Evaluation Files Found

The repository contains these evaluation-related files:

- `docs/evaluation_guide.md`
- `evaluation_results/published_auto_fix_summary.md`
- `evaluation_results/declined_auto_fix_summary.md`
- `evaluation_results/published_alignment_rules.md`
- `evaluation_results/declined_sdt_references.md`
- Several JSON and log files for phased evaluation runs, including keyword, author, layout, abstract, and declaration phases.

## Evaluation Evidence Available Now

The strongest available evidence is smoke evaluation and auto-fix before/after evaluation. Manual ground-truth labels have not yet been provided in the available result files.

### Published JIWE Sample Evaluation

From `evaluation_results/published_auto_fix_summary.json` and `.md`:

- Documents checked: 10.
- Invalid samples skipped: 0.
- Total detected issues before auto-fix: 88.
- Total detected issues after auto-fix: 14.
- Total formatting changes recorded: 94.
- Safe post-fix validations: 10 out of 10.
- Average compliance index before auto-fix: 91.64.
- Average compliance index after auto-fix: 97.34.

### Declined or Flawed Sample Evaluation

From `evaluation_results/declined_auto_fix_summary.json` and `.md`:

- Documents checked: 6.
- Invalid samples skipped: 0.
- Total detected issues before auto-fix: 98.
- Total detected issues after auto-fix: 28.
- Total formatting changes recorded: 75.
- Safe post-fix validations: 6 out of 6.
- Average compliance index before auto-fix: 87.62.
- Average compliance index after auto-fix: 97.47.

### Later Phased Evaluation Evidence

From `evaluation_results/phase5_declarations_published.json`:

- Documents checked: 10.
- Invalid samples skipped: 0.
- Total detected issues before auto-fix: 134.
- Total detected issues after auto-fix: 18.
- Total formatting changes recorded: 321.
- Safe post-fix validations: 10 out of 10.
- Average compliance index before auto-fix: 88.80.
- Average compliance index after auto-fix: 97.12.

These results should be reported as smoke and auto-fix safety evidence, not as final detection accuracy.

## Evaluation Still Needed for a Strong FYP2 Report

The final report should include or clearly plan:

1. Manual-label accuracy evaluation.
   - Export a label template using `evaluate_checker.py`.
   - Manually label expected issues and paragraph roles for representative samples.
   - Report precision, recall, and F1-score.

2. Subject expert evaluation.
   - Ask a supervisor, lecturer, editor, or trained reviewer to use the system.
   - Collect ratings on usefulness, clarity, time saving, trust, and remaining manual workload.
   - Report both quantitative Likert-scale results and qualitative comments.

3. Efficiency evaluation.
   - Compare time taken to screen manuscripts manually versus with the system.
   - Record number of issues found and missed.

## Exact Final Report Narrative

Use this narrative consistently:

> This project proposes, implements, and evaluates a rule-first, profile-based manuscript template compliance checking approach for academic journals. The prototype uses deterministic rule-based validation for objective formatting and structure checks, with JIWE as the primary validated journal profile. The system extracts or loads template rules, classifies document elements using profile-aware rules, detects compliance issues, applies conservative auto-corrections where deterministic correction is safe, and generates corrected, highlighted, and report outputs. Optional AI support is used only to explain rule-detected issues and organize review guidance. AI does not make compliance decisions, extract final compliance results, or approve manuscripts.

## Recommended Claims

Use these claims:

- The prototype improves consistency of initial manuscript formatting screening.
- The system supports explainable rule-based checking.
- The system can reduce common formatting issues through safer auto-fix.
- The system separates deterministic checking from optional AI explanation.
- The JIWE profile demonstrates the feasibility of a profile-based journal compliance approach.

Avoid these claims:

- The system guarantees acceptance by a journal.
- The system replaces editors or subject experts.
- The system perfectly checks all journals.
- The system can fully fix every manuscript automatically.
- The system performs research quality review.

