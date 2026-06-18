import unittest

from modules.llm_integration import LLMIntegration


class CapturingLLM(LLMIntegration):
    def __init__(self):
        self._available = True
        self.last_prompt = ""
        self.last_system_prompt = ""

    def generate(self, prompt: str, system_prompt: str = None) -> str:
        self.last_prompt = prompt
        self.last_system_prompt = system_prompt or ""
        return ""


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


if __name__ == "__main__":
    unittest.main()
