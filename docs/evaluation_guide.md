# Evaluation Guide

This project should be evaluated as a rule-first manuscript template compliance checker, not as a perfect editorial decision system. The recommended evaluation combines smoke testing, manual-label accuracy metrics, auto-fix before/after validation, and a small efficiency study.

## 1. Smoke Test With Real JIWE Samples

Use real published and rejected manuscripts to prove the checker runs on realistic documents.

```powershell
python evaluate_checker.py `
  --template "C:\Users\Acer\Downloads\FYP_SAMPLETEST\JIWE_Template-new_jan2026-OTH (8).docx" `
  --samples "C:\Users\Acer\Downloads\FYP_SAMPLETEST\PUBLISHED\TEST" `
  --summary-json "evaluation_results\published_summary.json" `
  --summary-md "evaluation_results\published_summary.md"
```

Repeat for rejected or intentionally flawed manuscripts:

```powershell
python evaluate_checker.py `
  --template "C:\Users\Acer\Downloads\FYP_SAMPLETEST\JIWE_Template-new_jan2026-OTH (8).docx" `
  --samples "C:\Users\Acer\Downloads\FYP_SAMPLETEST\DECLINED\TEST" `
  --summary-json "evaluation_results\declined_summary.json" `
  --summary-md "evaluation_results\declined_summary.md"
```

Report these values:

- Number of documents checked
- Number of skipped invalid documents
- Compliance index per document
- Issues by category

## 2. Auto-Fix Before/After Evaluation

Use the auto-fix evaluation flag to prove the corrected output is re-checked.

```powershell
python evaluate_checker.py `
  --template "C:\Users\Acer\Downloads\FYP_SAMPLETEST\JIWE_Template-new_jan2026-OTH (8).docx" `
  --samples "C:\Users\Acer\Downloads\FYP_SAMPLETEST\DECLINED\TEST" `
  --auto-fix-evaluation `
  --summary-json "evaluation_results\declined_auto_fix_summary.json" `
  --summary-md "evaluation_results\declined_auto_fix_summary.md"
```

Report these values:

- Issues before auto-fix
- Issues after auto-fix
- Compliance index before auto-fix
- Compliance index after auto-fix
- Whether post-fix validation is safe
- Remaining issues after auto-fix

Recommended FYP wording:

> Auto-fix was evaluated by re-checking each corrected manuscript. The system records whether the corrected document reduced or preserved the number of detected issues and warns when the corrected version appears worse.

## 3. Manual-Label Accuracy Evaluation

Compliance index is a user-facing score. Accuracy should be reported using manually labelled ground truth.

Create a starter label file:

```powershell
python evaluate_checker.py `
  --template "C:\Users\Acer\Downloads\FYP_SAMPLETEST\JIWE_Template-new_jan2026-OTH (8).docx" `
  --samples "C:\Users\Acer\Downloads\FYP_SAMPLETEST\PUBLISHED\TEST" `
  --export-label-template "evaluation_results\evaluation_labels.json"
```

Manually review and correct `evaluation_results\evaluation_labels.json`. Then run:

```powershell
python evaluate_checker.py `
  --template "C:\Users\Acer\Downloads\FYP_SAMPLETEST\JIWE_Template-new_jan2026-OTH (8).docx" `
  --samples "C:\Users\Acer\Downloads\FYP_SAMPLETEST\PUBLISHED\TEST" `
  --labels "evaluation_results\evaluation_labels.json" `
  --summary-json "evaluation_results\labelled_summary.json" `
  --summary-md "evaluation_results\labelled_summary.md"
```

Report these metrics:

- Issue detection precision
- Issue detection recall
- Issue detection F1-score
- Paragraph classification accuracy
- Paragraph classification precision
- Paragraph classification recall
- Paragraph classification F1-score

Recommended FYP wording:

> Precision, recall, and F1-score were calculated using manually labelled issue and paragraph classification labels. This separates actual detection accuracy from the user-facing compliance index.

## 4. Intentional Error Evaluation

Create or modify manuscripts with known errors:

- Entire body text changed to Calibri
- Entire document changed to 20 pt font
- Body text made bold
- Missing Abstract, Keywords, Introduction, Conclusion, or References
- Misspelled section heading such as `INTRODUTION`
- Wrong title font or size
- Wrong reference font size
- Missing italic source segment in references
- Header using manual spaces or tabs

For each document, record:

- Expected injected issue
- Whether the checker detected it
- Whether auto-fix applied a safe correction
- Whether the issue remained for manual review

## 5. Efficiency Evaluation

Use a small practical study to show whether the checker can reduce initial screening time.

Suggested setup:

- 3 to 5 participants, or one repeated manual baseline if participants are unavailable
- 3 manuscripts
- Task A: inspect manually
- Task B: inspect with the system

Record:

- Time taken
- Number of issues found
- Missed issues
- User rating from 1 to 5

Recommended FYP wording:

> The system is intended to improve the speed and consistency of initial formatting screening. Final editorial approval remains under human review.

