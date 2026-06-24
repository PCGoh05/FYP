# Content and Paragraph Rules Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Detect JIWE abstract word limits and paragraph alignment rules, then safely auto-fix body, abstract, and reference alignment without changing manuscript content.

**Architecture:** Store validated JIWE constraints in the profile and default rules. Template extraction may add deterministic abstract word limits and paragraph alignment when explicit evidence exists. The checker reports content and formatting issues; the auto-fixer changes only alignment and spacing properties.

**Tech Stack:** Python, python-docx, unittest, JSON journal profiles.

---

### Task 1: Add Rule-First Detection Tests

**Files:**
- Create: `tests/test_content_and_alignment_rules.py`

- [ ] Write tests proving that an abstract outside 200-300 words is reported.
- [ ] Write tests proving that non-justified body and reference paragraphs are reported.
- [ ] Run `python -m unittest tests.test_content_and_alignment_rules` and confirm the tests fail for missing behavior.

### Task 2: Encode and Extract Rules

**Files:**
- Modify: `template_profiles/jiwe.json`
- Modify: `config.py`
- Modify: `modules/template_extractor.py`

- [ ] Add `alignment: JUSTIFY` to JIWE body, abstract, and reference rules.
- [ ] Add `min_words: 200` and `max_words: 300` to the JIWE abstract rule.
- [ ] Preserve profile defaults while extracting alignment and explicit abstract word limits from uploaded templates.
- [ ] Run the focused tests and confirm rule extraction behavior.

### Task 3: Check and Auto-Fix Paragraph Rules

**Files:**
- Modify: `modules/manuscript_checker.py`
- Modify: `modules/auto_fixer.py`
- Test: `tests/test_content_and_alignment_rules.py`

- [ ] Count abstract words after removing the `Abstract` label and report values outside the configured range.
- [ ] Check body, abstract, and reference alignment only when the rule defines an expected alignment.
- [ ] Auto-fix detected alignment issues while preserving all paragraph text and run formatting.
- [ ] Never auto-fix abstract word count.

### Task 4: Verify and Publish

**Files:**
- Test: `tests/test_content_and_alignment_rules.py`

- [ ] Run `python -m unittest discover tests`.
- [ ] Run `python -m compileall -q app.py config.py evaluate_checker.py modules tests`.
- [ ] Run the real JIWE sample evaluation.
- [ ] Confirm changed code contains English only.
- [ ] Commit and push only the intended files.
