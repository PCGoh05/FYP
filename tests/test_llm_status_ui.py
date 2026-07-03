import unittest
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import app
from app import (
    get_default_template_rules,
    get_download_result_labels,
    get_issue_explanation_button_label,
    get_llm_status_notice,
    get_review_guidance_mode_notice,
    get_server_nvidia_api_key,
    get_system_capability_sections,
    run_llm_smoke_test,
)


class EmptySecrets:
    def get(self, name, default=None):
        return default


class FakeLLM:
    def __init__(self, available=True, response="AI_READY", last_error=""):
        self.available = available
        self.response = response
        self.last_error = last_error

    def is_available(self):
        return self.available

    def generate(self, prompt, system_prompt=None):
        return self.response


class LLMStatusUITest(unittest.TestCase):
    def test_disabled_ai_status_explains_core_checking(self):
        level, message = get_llm_status_notice(
            ai_enabled=False,
            connected=False,
            key_configured=False,
            attempted=False,
        )

        self.assertEqual(level, "info")
        self.assertIn("AI explanations are disabled", message)
        self.assertIn("Core checking is rule-based", message)

    def test_connected_ai_status_says_ai_is_explanation_only(self):
        level, message = get_llm_status_notice(
            ai_enabled=True,
            connected=True,
            key_configured=True,
            attempted=True,
        )

        self.assertEqual(level, "success")
        self.assertIn("AI explanations are connected", message)
        self.assertIn("format checking remains rule-based", message)

    def test_missing_server_key_status_is_clear_for_normal_users(self):
        level, message = get_llm_status_notice(
            ai_enabled=True,
            connected=False,
            key_configured=False,
            attempted=True,
        )

        self.assertEqual(level, "warning")
        self.assertIn("not configured on this deployment", message)
        self.assertIn("You do not need to enter an API key", message)

    def test_failed_server_key_status_suggests_retry_after_secret_update(self):
        level, message = get_llm_status_notice(
            ai_enabled=True,
            connected=False,
            key_configured=True,
            attempted=True,
        )

        self.assertEqual(level, "warning")
        self.assertIn("could not connect", message)
        self.assertIn("Retry AI connection", message)

    def test_server_key_can_be_loaded_from_local_env_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmp)
                Path(".env").write_text("NVIDIA_API_KEY=local-test-key\n", encoding="utf-8")
                with patch.dict(os.environ, {}, clear=True), patch.object(app.st, "secrets", EmptySecrets()):
                    self.assertEqual(get_server_nvidia_api_key(), "local-test-key")
            finally:
                os.chdir(original_cwd)

    def test_llm_smoke_test_reports_success_only_after_generation(self):
        level, message = run_llm_smoke_test(FakeLLM(response="AI_READY"))

        self.assertEqual(level, "success")
        self.assertIn("test response", message)

    def test_llm_smoke_test_accepts_token_with_punctuation(self):
        level, message = run_llm_smoke_test(FakeLLM(response="AI_READY."))

        self.assertEqual(level, "success")
        self.assertIn("test response", message)

    def test_llm_smoke_test_reports_unexpected_response(self):
        level, message = run_llm_smoke_test(FakeLLM(response="something else"))

        self.assertEqual(level, "warning")
        self.assertIn("unexpected response", message)

    def test_llm_smoke_test_reports_generation_error_reason(self):
        level, message = run_llm_smoke_test(
            FakeLLM(response="", last_error="TimeoutError: request timed out")
        )

        self.assertEqual(level, "warning")
        self.assertIn("TimeoutError", message)

    def test_download_result_labels_are_user_friendly(self):
        labels = get_download_result_labels("DOCX (Word)")

        self.assertEqual(labels["corrected"], "Download Corrected Manuscript (DOCX)")
        self.assertEqual(labels["highlighted"], "Download Highlighted Corrected Manuscript (DOCX)")
        self.assertEqual(labels["report"], "Download Fix Summary Report (DOCX)")

    def test_default_jiwe_rules_include_structure_metadata(self):
        rules = get_default_template_rules()

        self.assertIn("required_declarations", rules["_profile"])
        self.assertIn("acknowledgement", rules["_profile"]["required_declarations"])
        self.assertIn("ethics_statements", rules["_profile"]["required_declarations"])

    def test_issue_explanation_button_is_available_without_ai(self):
        self.assertEqual(
            get_issue_explanation_button_label(ai_enabled=False, connected=False),
            "Explain with Rule-Based Guidance",
        )

    def test_issue_explanation_button_shows_ai_when_connected(self):
        self.assertEqual(
            get_issue_explanation_button_label(ai_enabled=True, connected=True),
            "Explain with AI",
        )

    def test_review_guidance_mode_notice_explains_active_source(self):
        level, message = get_review_guidance_mode_notice(
            ai_enabled=True,
            connected=False,
            key_configured=True,
        )

        self.assertEqual(level, "warning")
        self.assertIn("Rule-based guidance", message)
        self.assertIn("AI is enabled but not connected", message)

    def test_system_capability_sections_explain_scope_and_limits(self):
        sections = get_system_capability_sections()
        titles = [section["title"] for section in sections]
        combined_text = " ".join(
            item
            for section in sections
            for item in section["items"]
        )

        self.assertIn("Best Supported Use", titles)
        self.assertIn("Auto-Fix Can Change", titles)
        self.assertIn("Needs Manual Review", titles)
        self.assertIn("PDF and AI Boundaries", titles)
        self.assertIn("JIWE", combined_text)
        self.assertIn("rule-detected formatting", combined_text)
        self.assertIn("does not decide manuscript acceptance", combined_text)
        self.assertNotIn("Precision, Recall, and F1", combined_text)


if __name__ == "__main__":
    unittest.main()
