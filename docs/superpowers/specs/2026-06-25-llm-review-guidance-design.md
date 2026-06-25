# LLM Review Guidance Design

## Purpose

Improve the optional LLM feature from repetitive single-issue paraphrasing into practical manuscript review guidance.

The rule-based engine remains the only source of:

- issue detection;
- compliance decisions;
- auto-fix decisions;
- post-fix validation;
- evaluation metrics.

The LLM must not inspect the full manuscript, discover new issues, modify documents, or decide whether a paper should be accepted.

## User Value

The feature should help an author or reviewer answer:

1. Which problems should be handled first?
2. Which problems can the system fix automatically?
3. Which problems require careful manual review?
4. What remains after auto-fix?
5. What should be checked before submission?

This replaces the current workflow in which users must click `Explain` repeatedly for similar issues.

## Recommended Workflow

### Before Auto-Fix

After format checking, the interface provides a `Generate Review Guidance` action.

The resulting guidance contains:

- `Priority issues`: errors and high-impact structural problems;
- `Quick fixes`: supported formatting problems suitable for auto-fix;
- `Manual review`: citations, equations, missing content, and layout movement;
- `Suggested order`: a short ordered correction workflow;
- `Limitations`: checks that still require human judgment.

### After Auto-Fix

The post-fix section provides an `Explain Fix Results` action.

The resulting summary contains:

- `Fixed automatically`: grouped changes that were applied;
- `Remaining issues`: grouped unresolved checks;
- `Why they remain`: safety reason for not changing them automatically;
- `Next review steps`: a short manual checklist;
- `Safety status`: whether post-fix validation found a regression.

The existing per-issue `Explain` action remains available as a secondary feature.

## Architecture

### ReviewGuidanceBuilder

Add a deterministic module responsible for converting checker results into compact structured data.

Responsibilities:

- group issues by normalized category and description;
- count repeated issues;
- retain no more than two short examples per group;
- assign a deterministic priority;
- classify each group as `auto_fix_supported` or `manual_review`;
- remove personal information and long manuscript text;
- limit the payload to the highest-priority 20 groups;
- build a useful fallback summary without any API.

This module must not call an LLM.

### LLMIntegration

Add two explanation-only methods:

- `generate_review_guidance(summary_payload)`;
- `generate_post_fix_summary(post_fix_payload)`.

Each method:

- receives only structured rule results;
- uses a fixed output schema;
- rejects unstructured or incomplete responses;
- falls back to deterministic guidance on timeout, invalid output, or missing API access;
- never changes checker or auto-fixer state.

The existing `explain_error()` method remains supported.

### Streamlit UI

Add session-state fields for:

- pre-fix guidance;
- post-fix guidance;
- cache keys;
- generation status.

Guidance is generated only when the user presses the corresponding button. It is not generated during document upload or format checking.

The UI must clearly state:

> AI organizes and explains rule-detected results. It does not detect issues or approve manuscripts.

## Data Contract

The pre-fix payload contains:

```json
{
  "profile": "JIWE",
  "total_issues": 12,
  "compliance_index": 84.0,
  "groups": [
    {
      "category": "references",
      "description": "Reference numbering is not continuous",
      "severity": "warning",
      "count": 1,
      "examples": ["Reference Numbering: [1], [2], [4]"],
      "auto_fix_supported": false,
      "review_reason": "Renumbering may alter citation meaning"
    }
  ]
}
```

The post-fix payload additionally contains:

```json
{
  "issues_before": 12,
  "issues_after": 4,
  "safe": true,
  "change_groups": [
    {
      "type": "body",
      "property": "font_name",
      "count": 8
    }
  ],
  "remaining_groups": []
}
```

Full paragraphs, author email addresses, ORCID values, reference lists, and manuscript files must not be included.

## Priority Rules

Priority is deterministic:

1. Error-severity missing structure, unmatched citations, and post-fix regressions.
2. Missing required sections or declarations.
3. Reference, equation, figure, and table consistency issues.
4. Title, author, heading, and layout issues.
5. Repeated body formatting issues.

LLM output may explain this order but must not change it.

## Auto-Fix Classification

The builder determines auto-fix support from the existing issue-to-property behavior in `AutoFixer`.

Examples normally suitable for auto-fix:

- font name;
- font size;
- bold or italic formatting;
- paragraph alignment;
- line spacing;
- page margins and supported layout properties.

Examples requiring manual review:

- missing text or sections;
- citation and reference renumbering;
- equation renumbering;
- moving tables or figures;
- rewriting author information;
- research content or language quality.

If support cannot be proven deterministically, the item is classified as manual review.

## LLM Prompt Boundaries

The system prompt must state:

- all issues were detected by deterministic rules;
- do not add, remove, validate, or contradict issues;
- do not recommend manuscript acceptance or rejection;
- do not infer missing manuscript content;
- do not request or expose API credentials;
- return only the requested section format;
- keep the response concise and actionable.

The response must contain all required headings. Otherwise, the deterministic fallback is displayed.

## Performance and Cost

- No LLM call during checking or auto-fix.
- Maximum two optional calls per manuscript workflow.
- Maximum 20 grouped issues per request.
- Maximum two short examples per issue group.
- Target input size: below 1,000 tokens.
- Target output size: 400 to 600 tokens.
- Low temperature for stable output.
- Cache by a hash of the structured payload, model, and prompt version.

The model runs through a remote API, so it does not significantly increase local CPU or memory usage.

## Connection Handling

The deployment uses a server-managed API key.

- Normal users do not enter a key.
- Developer override remains hidden unless explicitly enabled.
- Missing or invalid credentials show deterministic guidance.
- API failures never block checking, fixing, reporting, or downloads.
- Connection errors should be recorded internally without exposing the key.

The client should avoid repeated verification calls within the same session.

## Privacy

Only the minimum structured issue metadata is sent.

The application must:

- truncate examples;
- redact email addresses and ORCID identifiers;
- exclude full reference entries;
- exclude complete paragraphs;
- exclude manuscript binary data;
- explain in the UI that optional issue metadata is sent to the configured API.

## Error Handling

Use deterministic fallback guidance when:

- no server key exists;
- the API connection fails;
- the request times out;
- the model returns an empty response;
- required headings are absent;
- the response attempts to add unsupported findings.

The fallback must still provide priorities, auto-fix capability, manual-review reasons, and next steps.

## Testing

### Unit Tests

- repeated issues are grouped correctly;
- deterministic priorities are stable;
- supported and unsupported fixes are classified correctly;
- personal information is redacted;
- payload limits are enforced;
- fallback guidance includes every required section;
- invalid LLM responses trigger fallback;
- prompts preserve rule-first boundaries;
- cache keys change when checker results change.

### Integration Tests

- guidance works without an API key;
- API failure does not interrupt other workflows;
- pre-fix guidance contains only current checker results;
- post-fix guidance uses actual change records and remaining issues;
- no full manuscript text enters the LLM payload;
- repeated button presses reuse cached guidance.

### Regression Tests

- all existing checker and auto-fix tests continue to pass;
- `py_compile` succeeds;
- published and declined sample evaluation reports zero unsafe auto-fixes;
- changed code and generated text remain English-only.

## Evaluation

The LLM feature should be evaluated separately from checker accuracy.

Suitable measures:

- reduction in explanation requests compared with per-issue clicks;
- average guidance generation time;
- response fallback rate;
- percentage of guidance sections rated useful by users;
- reviewer agreement that the priority order is understandable.

Precision, Recall, and F1 remain measurements of the deterministic checker, not the LLM.

## Out of Scope

- full-paper language editing;
- research-quality evaluation;
- plagiarism detection;
- reference authenticity checking;
- automatic acceptance recommendations;
- LLM-based template extraction or compliance decisions;
- automatic rewriting of missing manuscript sections.

## Acceptance Criteria

The feature is complete when:

1. Useful pre-fix guidance is available with or without an API.
2. Useful post-fix guidance explains changes and remaining risks.
3. Repeated issues are grouped before reaching the LLM.
4. The full manuscript is never sent.
5. Normal users never need to provide an API key.
6. No LLM result changes checker or auto-fixer behavior.
7. Invalid API responses fall back safely.
8. Existing tests and sample evaluations remain safe.
