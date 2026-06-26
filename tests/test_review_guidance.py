import unittest
from types import SimpleNamespace

from modules.review_guidance import ReviewGuidanceBuilder


def _issue(
    category,
    description,
    severity="warning",
    location="Paragraph 1",
    current="Calibri",
    expected="Times New Roman",
    preview="",
):
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


def _result(issues_by_category, score=80.0):
    return SimpleNamespace(
        total_issues=sum(len(issues) for issues in issues_by_category.values()),
        compliance_score=score,
        issues_by_category=issues_by_category,
    )


class ReviewGuidanceBuilderTest(unittest.TestCase):
    def test_groups_repeated_issues_and_orders_errors_first(self):
        result = _result({
            "body_text": [
                _issue("body_text", "Body text font does not match template"),
                _issue(
                    "body_text",
                    "Body text font does not match template",
                    location="Paragraph 2",
                ),
            ],
            "references": [
                _issue(
                    "references",
                    "In-text citation has no matching reference",
                    severity="error",
                    current="[4]",
                    expected="Matching reference",
                )
            ],
        })

        payload = ReviewGuidanceBuilder().build_pre_fix_payload(
            result,
            {"_profile": {"name": "JIWE"}},
        )

        self.assertEqual(payload["groups"][0]["severity"], "error")
        self.assertFalse(payload["groups"][0]["auto_fix_supported"])
        self.assertEqual(payload["groups"][1]["count"], 2)
        self.assertTrue(payload["groups"][1]["auto_fix_supported"])
        self.assertEqual(payload["groups"][1]["property_name"], "font_name")

    def test_redacts_private_data_and_limits_payload(self):
        private_preview = (
            "Contact jane@example.com, ORCID 0000-0002-1825-0097. "
            + ("private manuscript sentence " * 20)
        )
        categories = {}
        for index in range(25):
            categories[f"category_{index}"] = [
                _issue(
                    f"category_{index}",
                    f"Unique issue {index}",
                    location=f"jane@example.com location {index}",
                    current=private_preview,
                    expected="Expected format",
                    preview=private_preview,
                )
            ]

        payload = ReviewGuidanceBuilder().build_pre_fix_payload(
            _result(categories),
            {"_profile": {"name": "JIWE"}},
        )
        serialized = str(payload)

        self.assertEqual(len(payload["groups"]), 20)
        self.assertNotIn("jane@example.com", serialized)
        self.assertNotIn("0000-0002-1825-0097", serialized)
        self.assertNotIn("private manuscript sentence private manuscript sentence", serialized)
        self.assertTrue(all(len(group["examples"]) <= 2 for group in payload["groups"]))

    def test_unknown_and_high_risk_issues_require_manual_review(self):
        result = _result({
            "structure": [
                _issue("structure", "Required section not found"),
            ],
            "figures": [
                _issue("figures", "Figure caption should appear below the figure"),
            ],
            "other": [
                _issue("other", "Unrecognized issue from future checker"),
            ],
        })

        payload = ReviewGuidanceBuilder().build_pre_fix_payload(result, {})

        self.assertTrue(all(
            group["auto_fix_supported"] is False
            for group in payload["groups"]
        ))
        self.assertTrue(all(group["review_reason"] for group in payload["groups"]))

    def test_fallback_has_required_sections_and_uses_payload_only(self):
        payload = ReviewGuidanceBuilder().build_pre_fix_payload(
            _result({
                "body_text": [
                    _issue("body_text", "Body text alignment does not match template")
                ],
                "references": [
                    _issue("references", "Reference numbering is not continuous")
                ],
            }),
            {"_profile": {"name": "JIWE"}},
        )

        fallback = ReviewGuidanceBuilder().build_pre_fix_fallback(payload)

        for heading in [
            "Priority issues:",
            "Quick fixes:",
            "Manual review:",
            "Suggested order:",
            "Limitations:",
        ]:
            self.assertIn(heading, fallback)
        self.assertIn("Body text alignment does not match template", fallback)
        self.assertIn("Reference numbering is not continuous", fallback)

    def test_cache_key_is_stable_and_changes_with_payload(self):
        builder = ReviewGuidanceBuilder()
        payload = builder.build_pre_fix_payload(
            _result({"body_text": [
                _issue("body_text", "Body text font does not match template")
            ]}),
            {},
        )

        first = builder.cache_key(payload, "pre-fix")
        second = builder.cache_key(payload, "pre-fix")
        changed_payload = dict(payload)
        changed_payload["total_issues"] = payload["total_issues"] + 1
        changed = builder.cache_key(changed_payload, "pre-fix")

        self.assertEqual(first, second)
        self.assertNotEqual(first, changed)

    def test_builds_post_fix_payload_from_actual_result_shapes(self):
        before = _result({
            "body_text": [
                _issue("body_text", "Body text font does not match template"),
                _issue("body_text", "Body text font does not match template"),
            ],
            "references": [
                _issue("references", "Reference numbering is not continuous"),
            ],
        }, score=82.0)
        after = _result({
            "references": [
                _issue("references", "Reference numbering is not continuous"),
            ],
        }, score=94.0)
        changes = [
            SimpleNamespace(change_type="body", property_name="font_name"),
            SimpleNamespace(change_type="body", property_name="font_name"),
        ]
        validation = SimpleNamespace(
            is_safe=True,
            before_issues=3,
            after_issues=1,
            new_or_increased_categories={},
        )

        payload = ReviewGuidanceBuilder().build_post_fix_payload(
            before,
            after,
            changes,
            validation,
            {"_profile": {"name": "JIWE"}},
        )

        self.assertEqual(payload["issues_before"], 3)
        self.assertEqual(payload["issues_after"], 1)
        self.assertTrue(payload["safe"])
        self.assertEqual(payload["change_groups"][0]["count"], 2)
        self.assertEqual(
            payload["remaining_groups"][0]["description"],
            "Reference numbering is not continuous",
        )

    def test_post_fix_payload_excludes_change_previews_and_private_text(self):
        before = _result({})
        after = _result({
            "author_info": [
                _issue(
                    "author_info",
                    "Author information requires manual review",
                    current="jane@example.com 0000-0002-1825-0097",
                    preview="Full private manuscript paragraph.",
                )
            ]
        })
        change = SimpleNamespace(
            change_type="author_info",
            property_name="alignment",
            text_preview="jane@example.com Full private manuscript paragraph.",
            current_value="0000-0002-1825-0097",
        )
        validation = SimpleNamespace(
            is_safe=False,
            before_issues=0,
            after_issues=1,
            new_or_increased_categories={"author_info": 1},
        )

        payload = ReviewGuidanceBuilder().build_post_fix_payload(
            before,
            after,
            [change],
            validation,
            {},
        )
        serialized = str(payload)

        self.assertNotIn("jane@example.com", serialized)
        self.assertNotIn("0000-0002-1825-0097", serialized)
        self.assertNotIn("Full private manuscript paragraph", serialized)

    def test_post_fix_fallback_uses_user_friendly_wording(self):
        payload = {
            "safe": True,
            "change_groups": [
                {"type": "body", "property": "alignment", "count": 3},
                {"type": "page_header", "property": "manual_tabs", "count": 1},
            ],
            "remaining_groups": [
                {
                    "description": "Some figures may be missing captions",
                    "count": 1,
                    "review_reason": "Moving document objects can damage Word layout.",
                }
            ],
        }

        guidance = ReviewGuidanceBuilder().build_post_fix_fallback(payload)

        self.assertIn("Auto-fixed items:", guidance)
        self.assertIn("Body text alignment was corrected to match the template. (3 changes)", guidance)
        self.assertIn("Page header spacing was adjusted. (1 change)", guidance)
        self.assertIn("Issues still needing review:", guidance)
        self.assertIn("Why these were not auto-fixed:", guidance)
        self.assertIn("Auto-fix safety check:", guidance)
        self.assertIn("The auto-fix did not create additional detected issues.", guidance)
        self.assertNotIn("Body: alignment", guidance)
        self.assertNotIn("manual tabs", guidance)
        self.assertNotIn("Post-fix validation did not increase detected issues", guidance)


if __name__ == "__main__":
    unittest.main()
