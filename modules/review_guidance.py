"""Deterministic review guidance payloads and fallback explanations."""

from collections import OrderedDict
import hashlib
import json
import re
from typing import Any, Dict, Iterable, List, Optional


EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
ORCID_PATTERN = re.compile(r"\b\d{4}-\d{4}-\d{4}-\d{3}[\dXx]\b")


class ReviewGuidanceBuilder:
    """Build privacy-limited guidance without using an LLM."""

    MAX_GROUPS = 20
    MAX_EXAMPLES = 2

    _MANUAL_PATTERNS = (
        "not found",
        "missing",
        "numbering is not continuous",
        "citation has no matching",
        "not cited",
        "should appear above",
        "should appear below",
        "may be missing a number",
        "required section",
        "required declaration",
        "word count",
        "invalid email",
        "invalid orcid",
        "multiple abstract paragraphs",
        "contains citation",
        "contains equation",
        "contains table or figure",
    )

    def build_pre_fix_payload(
        self,
        result: Any,
        rules: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Build a compact payload from deterministic checker results."""
        profile = rules.get("_profile", {}) if isinstance(rules, dict) else {}
        groups = self._group_issues(
            getattr(result, "issues_by_category", {}) or {}
        )
        return {
            "profile": profile.get("name", "Generic"),
            "total_issues": int(getattr(result, "total_issues", 0) or 0),
            "compliance_index": float(
                getattr(result, "compliance_score", 0.0) or 0.0
            ),
            "groups": groups[:self.MAX_GROUPS],
        }

    def _group_issues(
        self,
        issues_by_category: Dict[str, Iterable[Any]],
    ) -> List[Dict[str, Any]]:
        grouped: OrderedDict = OrderedDict()
        for category, issues in issues_by_category.items():
            for issue in issues:
                issue_category = (
                    getattr(issue, "category", "") or category or "other"
                )
                description = (
                    getattr(issue, "description", "") or "Formatting issue"
                )
                key = (
                    self._normalize(issue_category),
                    self._normalize(description),
                )
                if key not in grouped:
                    property_name = self._infer_safe_property(
                        issue_category,
                        description,
                        getattr(issue, "location", ""),
                    )
                    grouped[key] = {
                        "category": issue_category,
                        "description": description,
                        "severity": (
                            getattr(issue, "severity", "warning") or "warning"
                        ),
                        "count": 0,
                        "examples": [],
                        "auto_fix_supported": property_name is not None,
                        "property_name": property_name,
                        "review_reason": (
                            ""
                            if property_name
                            else self._manual_review_reason(
                                issue_category,
                                description,
                            )
                        ),
                        "priority": self._priority(
                            issue_category,
                            description,
                            getattr(issue, "severity", "warning"),
                        ),
                    }

                group = grouped[key]
                group["count"] += 1
                if len(group["examples"]) < self.MAX_EXAMPLES:
                    group["examples"].append(self._build_example(issue))

        return sorted(
            grouped.values(),
            key=lambda group: (
                group["priority"],
                group["category"].lower(),
                group["description"].lower(),
            ),
        )

    def build_pre_fix_fallback(self, payload: Dict[str, Any]) -> str:
        """Return useful pre-fix guidance without an API."""
        groups = payload.get("groups", [])
        priority_groups = groups[:5]
        quick_fixes = [
            group for group in groups if group.get("auto_fix_supported")
        ]
        manual_groups = [
            group for group in groups if not group.get("auto_fix_supported")
        ]

        lines = ["Priority issues:"]
        lines.extend(self._format_groups(priority_groups))
        lines.append("")
        lines.append("Quick fixes:")
        lines.extend(self._format_groups(quick_fixes))
        lines.append("")
        lines.append("Manual review:")
        lines.extend(self._format_groups(manual_groups, include_reason=True))
        lines.append("")
        lines.append("Suggested order:")
        if groups:
            lines.append(
                "1. Resolve errors and missing structural requirements. "
                "2. Apply supported formatting fixes. "
                "3. Review citations, equations, figures, tables, and remaining warnings."
            )
        else:
            lines.append("No detected issues require correction.")
        lines.append("")
        lines.append("Limitations:")
        lines.append(
            "This guidance organizes deterministic checker results only. "
            "It does not assess research quality, language quality, or manuscript acceptance."
        )
        return "\n".join(lines)

    @staticmethod
    def cache_key(payload: Dict[str, Any], guidance_type: str) -> str:
        """Return a stable cache key for a structured payload."""
        canonical = json.dumps(
            {"type": guidance_type, "payload": payload},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def redact_text(value: Any, limit: int = 80) -> str:
        """Redact personal identifiers and truncate evidence."""
        text = EMAIL_PATTERN.sub("[redacted email]", str(value or ""))
        text = ORCID_PATTERN.sub("[redacted ORCID]", text)
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) > limit:
            return text[:limit - 3].rstrip() + "..."
        return text

    def _build_example(self, issue: Any) -> str:
        location = self.redact_text(
            getattr(issue, "location", "Document"),
            55,
        )
        current = self.redact_text(
            getattr(issue, "current_value", ""),
            80,
        )
        expected = self.redact_text(
            getattr(issue, "expected_value", ""),
            55,
        )
        value_text = f"{current} -> {expected}" if current or expected else ""
        return self.redact_text(
            f"{location}: {value_text}".strip(": "),
            150,
        )

    def _infer_safe_property(
        self,
        category: str,
        description: str,
        location: str,
    ) -> Optional[str]:
        lower = description.lower()
        lower_location = str(location or "").lower()
        if any(pattern in lower for pattern in self._MANUAL_PATTERNS):
            return None

        if "number" in lower or "heading number" in lower_location:
            if "bold" in lower:
                return "number_bold"
            if "font size" in lower or "size" in lower:
                return "number_font_size"
            if "font" in lower:
                return "number_font_name"
            return None

        if "line spacing" in lower:
            return "line_spacing"
        if "manual tab" in lower:
            return "manual_tabs"
        if "alignment" in lower:
            return "alignment"
        if "font size" in lower or " size " in f" {lower} ":
            return "font_size"
        if "font" in lower:
            return "font_name"
        if "bold" in lower:
            return "bold"
        if "italic" in lower:
            return "italic"
        if category == "margins" and "margin" in lower:
            return "margins"
        if category == "layout":
            if "page size" in lower:
                return "page_size"
            if "orientation" in lower:
                return "orientation"
            if "column" in lower:
                return "columns"
        return None

    @staticmethod
    def _manual_review_reason(category: str, description: str) -> str:
        lower = description.lower()
        if "citation" in lower or "reference numbering" in lower:
            return "Citation changes may alter academic meaning."
        if "equation" in lower or "numbering" in lower:
            return "Renumbering may break cross-references."
        if "should appear" in lower or category in {"figures", "tables"}:
            return "Moving document objects can damage Word layout."
        if "not found" in lower or "missing" in lower or category == "structure":
            return "Missing content must be supplied and verified by an author."
        if category == "author_info":
            return "Author identity and contact details require human verification."
        return "No deterministic safe auto-fix is available for this issue."

    @staticmethod
    def _priority(
        category: str,
        description: str,
        severity: str,
    ) -> int:
        lower = description.lower()
        if str(severity).lower() == "error":
            return 0
        if (
            category == "structure"
            or "required section" in lower
            or "required declaration" in lower
        ):
            return 1
        if category in {"references", "figures", "tables"} or "equation" in lower:
            return 2
        if category in {
            "title",
            "author_info",
            "headings",
            "layout",
            "margins",
            "journal_header",
        }:
            return 3
        if category in {"body_text", "line_spacing"}:
            return 4
        return 5

    @staticmethod
    def _format_groups(
        groups: List[Dict[str, Any]],
        include_reason: bool = False,
    ) -> List[str]:
        if not groups:
            return ["- None."]
        lines = []
        for group in groups:
            line = (
                f"- {group['description']} "
                f"({group['count']} issue{'s' if group['count'] != 1 else ''})"
            )
            if include_reason and group.get("review_reason"):
                line += f" Reason: {group['review_reason']}"
            lines.append(line)
        return lines

    @staticmethod
    def _normalize(value: Any) -> str:
        return re.sub(r"\s+", " ", str(value or "").strip().lower())
