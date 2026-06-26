import unittest
from unittest.mock import Mock, patch

from modules.llm_integration import LLMIntegration, fallback_explain_issue
from modules.review_guidance import ReviewGuidanceBuilder


class CapturingLLM(LLMIntegration):
    def __init__(self, response=""):
        self._available = True
        self.last_prompt = ""
        self.last_system_prompt = ""
        self.response = response

    def generate(self, prompt: str, system_prompt: str = None) -> str:
        self.last_prompt = prompt
        self.last_system_prompt = system_prompt or ""
        return self.response


def _issue():
    return {
        "category": "body_text",
        "location": "Paragraph 208",
        "description": "Body text font does not match template",
        "current_value": "Calibri",
        "expected_value": "Times New Roman",
        "severity": "warning",
        "text_preview": "The data that support the findings of this study...",
    }


def _pre_fix_payload():
    return {
        "profile": "JIWE",
        "total_issues": 2,
        "compliance_index": 88.0,
        "groups": [
            {
                "category": "references",
                "description": "Reference numbering is not continuous",
                "severity": "warning",
                "count": 1,
                "examples": ["Reference Numbering: [1], [3]"],
                "auto_fix_supported": False,
                "property_name": None,
                "review_reason": "Renumbering may break cross-references.",
                "priority": 2,
            }
        ],
    }


def _post_fix_payload():
    return {
        "profile": "JIWE",
        "issues_before": 5,
        "issues_after": 2,
        "safe": True,
        "change_groups": [
            {"type": "body", "property": "font_name", "count": 3}
        ],
        "remaining_groups": _pre_fix_payload()["groups"],
    }


class LLMExplanationTest(unittest.TestCase):
    def test_fallback_explanation_uses_fixed_useful_sections(self):
        llm = LLMIntegration.__new__(LLMIntegration)
        llm._available = False
        explanation = llm.explain_error(_issue())

        for heading in [
            "Problem:",
            "Why it matters:",
            "How to fix:",
            "Rule used:",
            "Confidence:",
        ]:
            self.assertIn(heading, explanation)
        self.assertIn("Calibri", explanation)
        self.assertIn("Times New Roman", explanation)

    def test_llm_prompt_limits_ai_to_explanation_only(self):
        llm = CapturingLLM()
        llm.explain_error(_issue())

        self.assertIn("Do not decide whether the issue is correct", llm.last_prompt)
        self.assertIn("rule-based checker already detected", llm.last_prompt)
        self.assertIn("Problem:", llm.last_prompt)
        self.assertIn("Confidence:", llm.last_prompt)

    def test_fallback_helper_explains_without_api_key(self):
        explanation = fallback_explain_issue(_issue())

        self.assertIn("Problem:", explanation)
        self.assertIn("Rule used: Calibri -> Times New Roman.", explanation)

    def test_review_guidance_uses_structured_response_and_rule_first_prompt(self):
        response = "\n".join([
            "Most important issues: Review reference numbering.",
            "Safe auto-fix candidates: None.",
            "Needs manual checking: Renumber references carefully.",
            "Recommended review order: Review citations before submission.",
            "What this guidance cannot decide: Formatting guidance only.",
        ])
        llm = CapturingLLM(response)

        guidance = llm.generate_review_guidance(_pre_fix_payload())

        self.assertEqual(guidance, response)
        self.assertIn(
            "Do not add, remove, validate, or contradict issues",
            llm.last_prompt,
        )
        self.assertIn("deterministic rules", llm.last_system_prompt)
        self.assertIn(
            "do not recommend acceptance or rejection",
            llm.last_system_prompt.lower(),
        )

    def test_invalid_review_guidance_uses_deterministic_fallback(self):
        llm = CapturingLLM("Here is a general review.")

        guidance = llm.generate_review_guidance(_pre_fix_payload())

        self.assertEqual(
            guidance,
            ReviewGuidanceBuilder().build_pre_fix_fallback(_pre_fix_payload()),
        )

    def test_post_fix_summary_uses_fixed_sections_and_fallback(self):
        llm = CapturingLLM("")

        summary = llm.generate_post_fix_summary(_post_fix_payload())

        for heading in [
            "Auto-fixed items:",
            "Issues still needing review:",
            "Why these were not auto-fixed:",
            "What to check next:",
            "Auto-fix safety check:",
        ]:
            self.assertIn(heading, summary)
        self.assertIn("must not reinterpret", llm.last_prompt)

    def test_client_initialization_does_not_send_verification_completion(self):
        client = Mock()
        client.chat.completions.create = Mock()

        with patch("modules.llm_integration.OPENAI_AVAILABLE", True), patch(
            "modules.llm_integration.OpenAI",
            return_value=client,
        ):
            llm = LLMIntegration(api_key="nvapi-test-key")

        self.assertTrue(llm.is_available())
        client.chat.completions.create.assert_not_called()


if __name__ == "__main__":
    unittest.main()
