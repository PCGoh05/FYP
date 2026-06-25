import unittest
from types import SimpleNamespace

from app import (
    build_pre_fix_guidance_payload,
    resolve_pre_fix_guidance,
)


class FakeLLM:
    def __init__(self, available=True):
        self.available = available
        self.calls = 0

    def is_available(self):
        return self.available

    def generate_review_guidance(self, payload):
        self.calls += 1
        return "AI guidance"


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

        self.assertIn("Priority issues:", guidance)
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


if __name__ == "__main__":
    unittest.main()
