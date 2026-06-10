"""
Template profile loading utilities.

Profiles keep journal-specific assumptions outside the core checker as much as
possible. A profile can define required sections, heading patterns, scoring
weights, fallback defaults, and default formatting rules.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict

from config import DEFAULT_RULES, REQUIRED_SECTIONS


class ProfileLoader:
    """Load, detect, and normalize journal template profiles."""

    def __init__(self, profile_dir: Path | None = None):
        base_dir = Path(__file__).resolve().parent.parent
        self.profile_dir = profile_dir or base_dir / "template_profiles"

    def load(self, profile_name: str) -> Dict[str, Any]:
        """Load a profile by name, returning a safe generic fallback on error."""
        normalized_name = (profile_name or "generic").lower().strip()
        profile_path = self.profile_dir / f"{normalized_name}.json"

        try:
            if profile_path.exists():
                with open(profile_path, "r", encoding="utf-8") as profile_file:
                    return self._normalize(json.load(profile_file), normalized_name)
        except (OSError, json.JSONDecodeError):
            pass

        if normalized_name != "generic":
            return self.load("generic")

        return self._normalize(
            {
                "name": "Generic",
                "description": "Fallback academic manuscript profile",
                "required_sections": REQUIRED_SECTIONS,
                "heading_patterns": [],
                "rule_weights": {},
                "fallback_defaults": {},
                "rules": {},
            },
            normalized_name,
        )

    def detect_from_document(self, document, template_name: str = "") -> Dict[str, Any]:
        """Detect the closest known profile from template text and file name."""
        first_text = "\n".join(
            paragraph.text.lower()
            for paragraph in document.paragraphs[:30]
        )
        template_name_lower = (template_name or "").lower()

        if (
            "journal of informatics and web engineering" in first_text
            or "jiwe" in first_text
            or "jiwe" in template_name_lower
        ):
            return self.load("jiwe")

        return self.load("generic")

    def default_rules(self, profile: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """Return deep-copied default rules for the selected profile."""
        selected_profile = profile or self.load("generic")
        return deepcopy(selected_profile.get("rules", DEFAULT_RULES))

    def apply_rule_defaults(
        self,
        rules: Dict[str, Any],
        profile: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Fill missing extracted rule fields from the selected profile defaults."""
        merged = self.default_rules(profile)

        for category, values in rules.items():
            if category.startswith("_") or not isinstance(values, dict):
                merged[category] = values
                continue

            category_defaults = merged.get(category, {})
            if not isinstance(category_defaults, dict):
                merged[category] = values
                continue

            updated = deepcopy(category_defaults)
            for field, value in values.items():
                if value is not None:
                    updated[field] = value
            merged[category] = updated

        return merged

    def _normalize(self, profile: Dict[str, Any], profile_name: str) -> Dict[str, Any]:
        """Ensure every profile has the fields expected by the checker."""
        normalized = deepcopy(profile)
        normalized.setdefault("name", profile_name.title())
        normalized.setdefault("description", "Academic manuscript profile")
        normalized.setdefault("required_sections", REQUIRED_SECTIONS)
        normalized.setdefault("heading_patterns", [])
        normalized.setdefault("rule_weights", {})
        normalized.setdefault("fallback_defaults", {})

        rules = deepcopy(DEFAULT_RULES)
        profile_rules = normalized.get("rules", {})
        if isinstance(profile_rules, dict):
            for category, values in profile_rules.items():
                if isinstance(values, dict) and isinstance(rules.get(category), dict):
                    category_rules = deepcopy(rules[category])
                    category_rules.update(values)
                    rules[category] = category_rules
                else:
                    rules[category] = deepcopy(values)

        fallback_defaults = normalized.get("fallback_defaults", {})
        if isinstance(fallback_defaults, dict):
            font_name = fallback_defaults.get("font_name")
            if font_name:
                for category in ["title", "author", "affiliation", "body", "heading", "abstract", "keywords", "caption", "reference"]:
                    if category in rules and isinstance(rules[category], dict):
                        rules[category].setdefault("font_name", font_name)

            fallback_map = {
                "body_font_size": ("body", "font_size"),
                "abstract_font_size": ("abstract", "font_size"),
                "caption_font_size": ("caption", "font_size"),
                "reference_font_size": ("reference", "font_size"),
                "page_size": ("layout", "page_size"),
            }
            for fallback_key, (category, field) in fallback_map.items():
                if fallback_key in fallback_defaults and category in rules:
                    rules[category][field] = fallback_defaults[fallback_key]

        normalized["rules"] = rules
        return normalized
