import unittest
from types import SimpleNamespace

from app import (
    build_pre_fix_guidance_payload,
    build_post_fix_guidance_payload,
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
