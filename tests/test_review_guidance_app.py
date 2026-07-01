import unittest
from types import SimpleNamespace

from app import (
    build_auto_fix_preview_record,
    build_issue_display_record,
    build_pre_fix_guidance_payload,
    build_post_fix_guidance_payload,
    format_change_display_value,
    resolve_pre_fix_guidance,
    resolve_post_fix_guidance,
)
from modules.review_guidance import ReviewGuidanceBuilder


class FakeLLM:
    def __init__(self, available=True, review_text="AI guidance", post_fix_text="AI post-fix guidance"):
        self.available = available
        self.review_text = review_text
        self.post_fix_text = post_fix_text
        self.calls = 0

    def is_available(self):
        return self.available

    def generate_review_guidance(self, payload):
        self.calls += 1
        return self.review_text

    def generate_post_fix_summary(self, payload):
        self.calls += 1
        return self.post_fix_text


def _result():
    issue = SimpleNamespace(
        category="body_text",
        description="Body text font does not match template",
        severity="warning",
        location="Paragraph 7",
        current_value="Calibri",
        expected_value="Times New Roman",
        text_preview="Body text.",
        paragraph_index=6,
    )
    return SimpleNamespace(
        total_issues=1,
        compliance_score=96.0,
        issues_by_category={"body_text": [issue]},
    )


class ReviewGuidanceAppTest(unittest.TestCase):
    def test_formats_inherited_change_value_for_users(self):
        self.assertEqual(
            format_change_display_value("(inherited)"),
            "Inherited from Word style",
        )
        self.assertEqual(format_change_display_value("Times New Roman"), "Times New Roman")

    def test_builds_issue_display_record_with_action_guidance(self):
        issue = SimpleNamespace(
            category="body_text",
            description="Body text font does not match template",
            severity="warning",
            location="Paragraph 7",
            current_value="Calibri",
            expected_value="Times New Roman",
            text_preview="Contact jane@example.com ORCID 0000-0002-1825-0097.",
            paragraph_index=6,
        )

        record = build_issue_display_record(issue, "body_text")

        self.assertEqual(record["location"], "Paragraph 7")
        self.assertEqual(record["action_label"], "Auto-fix supported")
        self.assertIn("font name", record["action_detail"])
        self.assertNotIn("jane@example.com", str(record))
        self.assertNotIn("0000-0002-1825-0097", str(record))

    def test_builds_auto_fix_preview_record_for_app_display(self):
        issue = SimpleNamespace(
            category="body_text",
            description="Body text font does not match template",
            severity="warning",
            location="Paragraph 7",
            current_value="Calibri",
            expected_value="Times New Roman",
            text_preview="Body text.",
            paragraph_index=6,
        )

        preview = build_auto_fix_preview_record({"body_text": [issue]})

        self.assertEqual(preview["supported_count"], 1)
        self.assertEqual(preview["manual_count"], 0)
        self.assertTrue(preview["can_run_auto_fix"])

    def test_builds_pre_fix_payload_from_checker_result(self):
        payload = build_pre_fix_guidance_payload(
            _result(),
            {"_profile": {"name": "JIWE"}},
        )

        self.assertEqual(payload["profile"], "JIWE")
        self.assertEqual(payload["total_issues"], 1)
        self.assertEqual(payload["groups"][0]["count"], 1)

    def test_resolves_rule_based_guidance_without_llm(self):
        payload = build_pre_fix_guidance_payload(_result(), {})

        guidance, cache_key, source = resolve_pre_fix_guidance(
            payload,
            llm=None,
            cache={},
        )

        self.assertIn("Most important issues:", guidance)
        self.assertTrue(cache_key)
        self.assertEqual(source, "Rule-based guidance")

    def test_reuses_cached_ai_guidance(self):
        payload = build_pre_fix_guidance_payload(_result(), {})
        llm = FakeLLM()
        cache = {}

        first = resolve_pre_fix_guidance(payload, llm, cache)
        second = resolve_pre_fix_guidance(payload, llm, cache)

        self.assertEqual(first, second)
        self.assertEqual(first[0], "AI guidance")
        self.assertEqual(first[2], "AI-enhanced guidance")
        self.assertEqual(llm.calls, 1)

    def test_marks_llm_fallback_when_connected_ai_returns_rule_based_text(self):
        payload = build_pre_fix_guidance_payload(_result(), {})
        fallback_text = ReviewGuidanceBuilder().build_pre_fix_fallback(payload)
        llm = FakeLLM(review_text=fallback_text)

        guidance, _, source = resolve_pre_fix_guidance(payload, llm, {})

        self.assertEqual(guidance, fallback_text)
        self.assertEqual(
            source,
            "Rule-based fallback after AI response was unavailable or incomplete",
        )

    def test_resolves_and_caches_post_fix_guidance(self):
        before = _result()
        after = SimpleNamespace(
            total_issues=0,
            compliance_score=100.0,
            issues_by_category={},
        )
        changes = [
            SimpleNamespace(change_type="body", property_name="font_name")
        ]
        validation = SimpleNamespace(
            is_safe=True,
            before_issues=1,
            after_issues=0,
            new_or_increased_categories={},
        )
        payload = build_post_fix_guidance_payload(
            before,
            after,
            changes,
            validation,
            {"_profile": {"name": "JIWE"}},
        )
        llm = FakeLLM()
        cache = {}

        first = resolve_post_fix_guidance(payload, llm, cache)
        second = resolve_post_fix_guidance(payload, llm, cache)

        self.assertEqual(first, second)
        self.assertEqual(first[0], "AI post-fix guidance")
        self.assertEqual(first[2], "AI-enhanced guidance")
        self.assertEqual(llm.calls, 1)

    def test_marks_post_fix_llm_fallback_when_ai_returns_rule_based_text(self):
        before = _result()
        after = SimpleNamespace(
            total_issues=0,
            compliance_score=100.0,
            issues_by_category={},
        )
        changes = [
            SimpleNamespace(change_type="body", property_name="font_name")
        ]
        validation = SimpleNamespace(
            is_safe=True,
            before_issues=1,
            after_issues=0,
            new_or_increased_categories={},
        )
        payload = build_post_fix_guidance_payload(
            before,
            after,
            changes,
            validation,
            {},
        )
        fallback_text = ReviewGuidanceBuilder().build_post_fix_fallback(payload)
        llm = FakeLLM(post_fix_text=fallback_text)

        guidance, _, source = resolve_post_fix_guidance(payload, llm, {})

        self.assertEqual(guidance, fallback_text)
        self.assertEqual(
            source,
            "Rule-based fallback after AI response was unavailable or incomplete",
        )


if __name__ == "__main__":
    unittest.main()
