# LLM Review Guidance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add privacy-preserving, rule-first pre-fix and post-fix review guidance that remains useful without an LLM and uses the NVIDIA API only to improve presentation.

**Architecture:** A new deterministic `ReviewGuidanceBuilder` converts checker results and change records into compact grouped payloads, priorities, auto-fix capability, fallbacks, and cache keys. `LLMIntegration` receives only these payloads and validates fixed-section responses. Streamlit exposes explicit on-demand actions and session caching; checking, auto-fix, reports, and downloads remain independent.

**Tech Stack:** Python 3, `unittest`, Streamlit, python-docx data classes, NVIDIA OpenAI-compatible API client, SHA-256 payload hashing.

---

## File Structure

- Create `modules/review_guidance.py`: deterministic grouping, priority, redaction, payload limits, fallback text, and cache keys.
- Create `tests/test_review_guidance.py`: builder, privacy, priority, fix support, limits, fallback, and cache tests.
- Modify `modules/llm_integration.py`: pre-fix and post-fix generation methods with strict response validation and fallback.
- Modify `tests/test_llm_explanations.py`: prompt boundaries, invalid-output fallback, and valid structured response tests.
- Modify `app.py`: session state, on-demand guidance actions, caching, and privacy/status copy.
- Create `tests/test_review_guidance_app.py`: app helper integration without running the Streamlit server.
- Modify `modules/__init__.py`: export the deterministic builder API.

### Task 1: Deterministic Review Guidance Builder

**Files:**
- Create: `modules/review_guidance.py`
- Create: `tests/test_review_guidance.py`
- Modify: `modules/__init__.py`

- [ ] **Step 1: Write failing grouping and priority tests**

Create tests using lightweight issue objects:

```python
from types import SimpleNamespace

from modules.review_guidance import ReviewGuidanceBuilder


def issue(category, description, severity="warning", location="Paragraph 1",
          current="Calibri", expected="Times New Roman", preview=""):
    return SimpleNamespace(
        category=category,
        description=description,
        severity=severity,
        location=location,
        current_value=current,
        expected_value=expected,
        text_preview=preview,
        paragraph_index=0,
    )


def test_groups_repeated_issues_and_orders_errors_first():
    result = SimpleNamespace(
        total_issues=3,
        compliance_score=80.0,
        issues_by_category={
            "body_text": [
                issue("body_text", "Body text font does not match template"),
                issue("body_text", "Body text font does not match template", location="Paragraph 2"),
            ],
            "references": [
                issue(
                    "references",
                    "In-text citation has no matching reference",
                    severity="error",
                    current="[4]",
                    expected="Matching reference",
                )
            ],
        },
    )

    payload = ReviewGuidanceBuilder().build_pre_fix_payload(result, {"_profile": {"name": "JIWE"}})

    assert payload["groups"][0]["severity"] == "error"
    assert payload["groups"][0]["auto_fix_supported"] is False
    assert payload["groups"][1]["count"] == 2
    assert payload["groups"][1]["auto_fix_supported"] is True
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_review_guidance -v
```

Expected: import failure because `modules.review_guidance` does not exist.

- [ ] **Step 3: Implement issue grouping and deterministic priority**

Add:

```python
class ReviewGuidanceBuilder:
    MAX_GROUPS = 20
    MAX_EXAMPLES = 2

    def build_pre_fix_payload(self, result, rules):
        groups = self._group_issues(result.issues_by_category)
        return {
            "profile": rules.get("_profile", {}).get("name", "Generic"),
            "total_issues": int(result.total_issues),
            "compliance_index": float(result.compliance_score),
            "groups": groups[:self.MAX_GROUPS],
        }
```

Group by normalized `(category, description)`, count entries, retain two examples, assign numeric priority, sort by priority then category and description, and keep the original severity.

- [ ] **Step 4: Add failing fix-support and privacy tests**

Test:

```python
def test_redacts_private_data_and_limits_examples_and_groups():
    preview = "Contact jane@example.com, ORCID 0000-0002-1825-0097. " + ("private " * 80)
    # Build 25 unique issue groups.
    payload = builder.build_pre_fix_payload(result, rules)

    serialized = str(payload)
    assert "jane@example.com" not in serialized
    assert "0000-0002-1825-0097" not in serialized
    assert len(payload["groups"]) == 20
    assert all(len(group["examples"]) <= 2 for group in payload["groups"])
```

Also test that font, size, bold, italic, alignment, line spacing, margins, page size, orientation, and columns are supported only when the issue description maps to an existing safe property; missing sections, declarations, citations, equations, and caption movement are manual.

- [ ] **Step 5: Implement redaction and conservative auto-fix classification**

Implement:

```python
EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
ORCID_PATTERN = re.compile(r"\b\d{4}-\d{4}-\d{4}-\d{3}[\dXx]\b")

def redact_text(value, limit=120):
    text = EMAIL_PATTERN.sub("[redacted email]", str(value or ""))
    text = ORCID_PATTERN.sub("[redacted ORCID]", text)
    return re.sub(r"\s+", " ", text).strip()[:limit]
```

Use a fixed description-to-property map matching `AutoFixer._infer_issue_property`. Unknown descriptions default to manual review.

- [ ] **Step 6: Add failing fallback and cache tests**

Test required pre-fix headings:

```text
Priority issues:
Quick fixes:
Manual review:
Suggested order:
Limitations:
```

Test that the cache key is stable for the same payload and changes when any issue group changes.

- [ ] **Step 7: Implement fallback text and canonical cache key**

Use sorted JSON serialization:

```python
encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
```

The fallback must use only payload values and must not invent findings.

- [ ] **Step 8: Run focused and full tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_review_guidance -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
```

Expected: all tests pass.

- [ ] **Step 9: Commit and push**

```powershell
git add modules/review_guidance.py modules/__init__.py tests/test_review_guidance.py
git commit -m "Add deterministic review guidance builder"
git push
```

### Task 2: LLM Guidance Methods and Safe Fallback

**Files:**
- Modify: `modules/llm_integration.py`
- Modify: `tests/test_llm_explanations.py`

- [ ] **Step 1: Write failing pre-fix guidance tests**

Add a capturing subclass that returns valid or invalid responses. Assert:

```python
guidance = llm.generate_review_guidance(payload)
assert "Priority issues:" in guidance
assert "Quick fixes:" in guidance
assert "Manual review:" in guidance
assert "Suggested order:" in guidance
assert "Limitations:" in guidance
assert "Do not add, remove, validate, or contradict issues" in llm.last_prompt
assert "do not recommend acceptance or rejection" in llm.last_system_prompt.lower()
```

For an empty or malformed model response, assert exact equality with `ReviewGuidanceBuilder().build_pre_fix_fallback(payload)`.

- [ ] **Step 2: Run focused tests and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_llm_explanations -v
```

Expected: attribute failure for `generate_review_guidance`.

- [ ] **Step 3: Implement `generate_review_guidance`**

Serialize only the structured payload with `json.dumps`. Require all five headings. On unavailable client, exception, empty response, or invalid headings, return deterministic fallback.

- [ ] **Step 4: Write failing post-fix guidance tests**

Require:

```text
Fixed automatically:
Remaining issues:
Why they remain:
Next review steps:
Safety status:
```

Assert the prompt states that the model must not reinterpret change records, checker results, or safety status.

- [ ] **Step 5: Implement `generate_post_fix_summary`**

Validate all five headings and use `ReviewGuidanceBuilder().build_post_fix_fallback(payload)` for every failure path.

- [ ] **Step 6: Remove client verification request at initialization**

Change `_init_client()` so constructing the API client does not send the `"test"` completion. The first user-triggered explanation request verifies availability. Set availability when a key and client library exist; failures in `generate()` return an empty string and therefore trigger fallback.

Add a test with a patched client constructor proving initialization creates no completion request.

- [ ] **Step 7: Run tests and compile**

Run:

```powershell
.\.venv\Scripts\python.exe -m py_compile modules\llm_integration.py
.\.venv\Scripts\python.exe -m unittest tests.test_llm_explanations -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
```

- [ ] **Step 8: Commit and push**

```powershell
git add modules/llm_integration.py tests/test_llm_explanations.py
git commit -m "Add structured LLM review guidance"
git push
```

### Task 3: Pre-Fix Streamlit Guidance and Session Cache

**Files:**
- Modify: `app.py`
- Create: `tests/test_review_guidance_app.py`

- [ ] **Step 1: Extract testable app helpers**

Write failing tests for:

```python
payload = build_pre_fix_guidance_payload(check_result, rules)
text, cache_key = generate_pre_fix_guidance(payload, llm=None, cached={})
```

Assert no LLM is required, deterministic fallback is returned, and a second call with the same cache dictionary reuses the existing value.

- [ ] **Step 2: Run focused tests and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_review_guidance_app -v
```

Expected: helper functions do not exist.

- [ ] **Step 3: Implement pure helper functions**

Add helpers near existing connection helpers:

```python
def build_pre_fix_guidance_payload(result, rules):
    return ReviewGuidanceBuilder().build_pre_fix_payload(result, rules)


def resolve_pre_fix_guidance(payload, llm, cache):
    key = ReviewGuidanceBuilder.cache_key(payload, "pre-fix")
    if key not in cache:
        cache[key] = (
            llm.generate_review_guidance(payload)
            if llm and llm.is_available()
            else ReviewGuidanceBuilder().build_pre_fix_fallback(payload)
        )
    return cache[key], key
```

- [ ] **Step 4: Add session-state fields and reset behavior**

Initialize:

```python
"review_guidance_cache": {},
"pre_fix_guidance": "",
"pre_fix_guidance_key": "",
"post_fix_guidance": "",
"post_fix_guidance_key": "",
```

Reset displayed guidance when a new manuscript check runs, but retain the bounded session cache.

- [ ] **Step 5: Add the pre-fix UI**

Below `Issues by Category`, add:

- explanatory caption about rule-first behavior and optional metadata transmission;
- `Generate Review Guidance` button;
- spinner while resolving;
- a bordered or expander result area;
- source caption: `AI-enhanced guidance` or `Rule-based guidance`.

Do not call the LLM automatically.

- [ ] **Step 6: Keep single-issue Explain secondary**

Retain the existing button but relabel it `Explain This Issue` and pass `text_preview` after redaction/truncation only.

- [ ] **Step 7: Run app tests and smoke import**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_review_guidance_app -v
.\.venv\Scripts\python.exe -m py_compile app.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
```

- [ ] **Step 8: Commit and push**

```powershell
git add app.py tests/test_review_guidance_app.py
git commit -m "Add pre-fix review guidance workflow"
git push
```

### Task 4: Post-Fix Guidance

**Files:**
- Modify: `modules/review_guidance.py`
- Modify: `app.py`
- Modify: `tests/test_review_guidance.py`
- Modify: `tests/test_review_guidance_app.py`

- [ ] **Step 1: Write failing post-fix payload tests**

Use actual-shaped `ChangeRecord` and `PostFixValidationResult` objects. Assert:

```python
payload = builder.build_post_fix_payload(
    before_result,
    after_result,
    changes,
    validation,
    rules,
)
assert payload["issues_before"] == 8
assert payload["issues_after"] == 3
assert payload["safe"] is True
assert payload["change_groups"][0]["count"] == 2
assert payload["remaining_groups"]
```

Verify text previews and personal information are absent.

- [ ] **Step 2: Implement grouped change and remaining-issue payload**

Group changes by `(change_type, property_name)` and remaining issues using the same deterministic issue grouping code. Include validation category increases only as structured counts.

- [ ] **Step 3: Write failing app helper tests**

Test `resolve_post_fix_guidance()` fallback, cache reuse, and cache invalidation when `issues_after` changes.

- [ ] **Step 4: Implement post-fix helpers and UI**

In `display_post_fix_validation()`, add an explicit `Explain Fix Results` button after the remaining-issues table. Display source and guidance without blocking corrected-document downloads.

- [ ] **Step 5: Run focused and full tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_review_guidance tests.test_review_guidance_app tests.test_llm_explanations -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
```

- [ ] **Step 6: Commit and push**

```powershell
git add modules/review_guidance.py app.py tests/test_review_guidance.py tests/test_review_guidance_app.py
git commit -m "Add post-fix review guidance"
git push
```

### Task 5: Final Privacy, Regression, and Sample Verification

**Files:**
- Modify only if verification reveals a regression.

- [ ] **Step 1: Compile all project Python files**

Run:

```powershell
$files = Get-ChildItem -Recurse -File -Include *.py |
  Where-Object { $_.FullName -notmatch '\\.venv\\' }
.\.venv\Scripts\python.exe -m py_compile $files.FullName
```

- [ ] **Step 2: Run all tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
```

Expected: zero failures.

- [ ] **Step 3: Verify Published sample auto-fix safety**

Run:

```powershell
.\.venv\Scripts\python.exe evaluate_checker.py `
  --template "C:\Users\Acer\Downloads\FYP_SAMPLETEST\JIWE_Template-new_jan2026-OTH (8).docx" `
  --samples "C:\Users\Acer\Downloads\FYP_SAMPLETEST\PUBLISHED\TEST" `
  --auto-fix-evaluation `
  --summary-json "$env:TEMP\fyp_llm_guidance_published.json" `
  --summary-md "$env:TEMP\fyp_llm_guidance_published.md"
```

Expected: ten files evaluated and zero `safe=False`.

- [ ] **Step 4: Verify Declined sample auto-fix safety**

Run the same command with:

```text
--samples C:\Users\Acer\Downloads\FYP_SAMPLETEST\DECLINED\TEST
```

Expected: six files evaluated and zero `safe=False`.

- [ ] **Step 5: Run English-only and secret scans**

Run:

```powershell
rg -n --pcre2 "\p{Han}" app.py config.py modules tests docs\superpowers
rg -n "nvapi-[A-Za-z0-9_-]{8,}|NVIDIA_API_KEY\s*=\s*['\"][^'\"]+" .
```

Expected: no Chinese code/documentation and no committed API key.

- [ ] **Step 6: Verify payload privacy**

Run the privacy unit test with an issue containing a unique fake email, ORCID, long paragraph, and reference entry. Assert none appears in the serialized pre-fix or post-fix payload.

- [ ] **Step 7: Verify Git scope**

Run:

```powershell
git status --short
git diff --check
git rev-list --left-right --count origin/main...HEAD
```

Expected: only the user's pre-existing sample deletions remain and local commits match `origin/main`.

- [ ] **Step 8: Final commit only if verification required changes**

If verification required code changes:

```powershell
git add <changed feature files>
git commit -m "Harden review guidance privacy and fallback"
git push
```
