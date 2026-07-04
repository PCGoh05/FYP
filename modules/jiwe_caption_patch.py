"""Runtime patch for verified JIWE caption behaviour.

This module is intentionally isolated on the bugfix-caption branch so the
corrected caption behaviour can be tested without changing main.
"""

from __future__ import annotations

from copy import deepcopy
from typing import List

from docx.shared import Pt


def _profile_name(instance) -> str:
    profile = getattr(instance, "profile", {}) or {}
    if not profile and hasattr(instance, "rules"):
        profile = instance.rules.get("_profile", {}) or {}
    return str(profile.get("name", "")).strip().lower()


def _is_jiwe(instance) -> bool:
    return _profile_name(instance) == "jiwe"


def _effective_run_bold(paragraph, run) -> bool:
    if run.font.bold is not None:
        return bool(run.font.bold)

    style = getattr(paragraph, "style", None)
    if style is not None and getattr(style, "font", None) is not None:
        if style.font.bold is not None:
            return bool(style.font.bold)

    base_style = getattr(style, "base_style", None) if style is not None else None
    if base_style is not None and getattr(base_style, "font", None) is not None:
        if base_style.font.bold is not None:
            return bool(base_style.font.bold)

    return False


def _visible_bold_states(paragraph) -> List[bool]:
    return [
        _effective_run_bold(paragraph, run)
        for run in paragraph.runs
        if run.text.strip()
    ]


def apply_jiwe_caption_patch() -> None:
    """Apply the test-branch caption fixes once."""
    from config import DEFAULT_RULES
    from .profile_loader import ProfileLoader
    from .paragraph_classifier import ParagraphType
    from .manuscript_checker import ManuscriptChecker
    from .auto_fixer import AutoFixer
    from .utils import (
        get_paragraph_text,
        get_space_after_pt,
        to_journal_caption_title_case,
        truncate_text,
    )

    if getattr(AutoFixer, "_jiwe_caption_patch_applied", False):
        return

    DEFAULT_RULES.setdefault("caption", {})["bold"] = False
    DEFAULT_RULES["caption"]["title_case"] = False

    original_normalize = ProfileLoader._normalize

    def patched_normalize(self, profile, profile_name):
        normalized = original_normalize(self, profile, profile_name)
        if str(normalized.get("name", "")).strip().lower() == "jiwe":
            normalized.setdefault("rules", {}).setdefault("caption", {})["bold"] = False
            normalized["rules"]["caption"]["title_case"] = False
        return normalized

    ProfileLoader._normalize = patched_normalize

    original_check_tables = ManuscriptChecker._check_tables
    original_check_figures = ManuscriptChecker._check_figures

    def add_caption_bold_issues(checker, category: str, caption_type: str) -> None:
        caption_rules = checker.rules.setdefault("caption", {})
        expected_bold = caption_rules.get("bold")
        if expected_bold is None and _is_jiwe(checker):
            expected_bold = False
            caption_rules["bold"] = False
        if expected_bold is None:
            return

        description = (
            "Table caption bold formatting does not match template"
            if caption_type == "table"
            else "Figure caption bold formatting does not match template"
        )

        for classified in checker.classifications:
            if classified.paragraph_type != ParagraphType.CAPTION:
                continue
            if not checker._is_numbered_caption_text(classified.text, caption_type):
                continue

            paragraph = checker.document.paragraphs[classified.index]
            states = _visible_bold_states(paragraph)
            mismatch = bool(states) and (
                (bool(expected_bold) and not all(states))
                or (not bool(expected_bold) and any(states))
            )
            if not mismatch:
                continue

            already_reported = any(
                issue.paragraph_index == classified.index
                and issue.description == description
                for issue in checker.issues.get(category, [])
            )
            if already_reported:
                continue

            checker._add_issue(
                category=category,
                location=f"Caption: {truncate_text(classified.text, 30)}",
                para_index=classified.index,
                description=description,
                current="Contains bold text" if any(states) else "Not fully bold",
                expected="Bold" if expected_bold else "Not Bold",
                severity="warning",
                text_preview=truncate_text(classified.text, 50),
            )

    def patched_check_tables(self):
        original_check_tables(self)
        add_caption_bold_issues(self, "tables", "table")

    def patched_check_figures(self):
        original_check_figures(self)
        add_caption_bold_issues(self, "figures", "figure")

    ManuscriptChecker._check_tables = patched_check_tables
    ManuscriptChecker._check_figures = patched_check_figures

    def replace_text_preserving_runs(self, paragraph, text: str):
        original_segments = [run.text for run in paragraph.runs]
        if sum(len(segment) for segment in original_segments) != len(text):
            self._replace_paragraph_text_preserving_first_run(paragraph, text)
            return

        offset = 0
        for run, original_segment in zip(paragraph.runs, original_segments):
            segment_length = len(original_segment)
            if segment_length == 0:
                continue
            replacement = text[offset:offset + segment_length]
            self._set_run_text_preserving_drawings(run, replacement)
            offset += segment_length

    AutoFixer._replace_paragraph_text_preserving_runs = replace_text_preserving_runs

    def patched_fix_caption(self, paragraph, index: int):
        caption_rules = deepcopy(self.rules.get("caption", {}))
        if _is_jiwe(self):
            caption_rules["bold"] = False
            caption_rules["title_case"] = False
            self.rules.setdefault("caption", {}).update({
                "bold": False,
                "title_case": False,
            })

        changes = []
        allowed_properties = self._allowed_properties_for(
            index,
            categories=["figures", "tables"],
            fallback=[
                "font_name",
                "font_size",
                "bold",
                "italic",
                "space_after",
                "capitalization",
            ],
        )

        expected_font = caption_rules.get("font_name", "Times New Roman")
        expected_size = caption_rules.get("font_size", 10)
        expected_bold = caption_rules.get("bold")
        expected_italic = caption_rules.get("italic")
        expected_space_after = caption_rules.get("space_after")
        title_case_required = bool(caption_rules.get("title_case"))

        for run in paragraph.runs:
            if not run.text.strip():
                continue
            changes.extend(self._fix_run_formatting(
                run,
                expected_font,
                expected_size,
                expected_bold,
                expected_italic,
                allowed_properties=allowed_properties,
            ))

        if (
            expected_space_after is not None
            and self._property_allowed("space_after", allowed_properties)
        ):
            current_space_after = get_space_after_pt(paragraph)
            if (
                current_space_after is None
                or abs(float(current_space_after) - float(expected_space_after)) > 0.5
            ):
                paragraph.paragraph_format.space_after = Pt(float(expected_space_after))
                changes.append({
                    "property_name": "space_after",
                    "current_value": (
                        f"{current_space_after}pt"
                        if current_space_after is not None
                        else "(inherited)"
                    ),
                    "target_value": f"{expected_space_after}pt",
                    "evidence": "Caption paragraph spacing after did not match target rule",
                })

        current_text = get_paragraph_text(paragraph)
        if (
            title_case_required
            and self._property_allowed("capitalization", allowed_properties)
        ):
            target_text = to_journal_caption_title_case(current_text)
            if target_text != current_text:
                self._replace_paragraph_text_preserving_runs(paragraph, target_text)
                changes.append({
                    "property_name": "capitalization",
                    "current_value": current_text,
                    "target_value": target_text,
                    "evidence": "Caption capitalization did not match target rule",
                })

        if changes:
            self._add_property_changes(
                paragraph_index=index,
                location="Caption",
                change_type="caption",
                details=changes,
                text_preview=truncate_text(get_paragraph_text(paragraph), 50),
                paragraph_type=ParagraphType.CAPTION.value,
            )

    AutoFixer._fix_caption = patched_fix_caption
    AutoFixer._jiwe_caption_patch_applied = True
