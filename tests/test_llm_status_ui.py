import unittest
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import app
from app import (
    get_download_result_labels,
    get_llm_status_notice,
    get_server_nvidia_api_key,
    run_llm_smoke_test,
)


class EmptySecrets:
    def get(self, name, default=None):
        return default


class FakeLLM:
    def __init__(self, available=True, response="AI_READY"):
        self.available = available
        self.response = response

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
                Path(".env").write_text("NVIDIA_API_KEY=nvapi-local-test\n", encoding="utf-8")
                with patch.dict(os.environ, {}, clear=True), patch.object(app.st, "secrets", EmptySecrets()):
                    self.assertEqual(get_server_nvidia_api_key(), "nvapi-local-test")
            finally:
                os.chdir(original_cwd)

    def test_llm_smoke_test_reports_success_only_after_generation(self):
        level, message = run_llm_smoke_test(FakeLLM(response="AI_READY"))

        self.assertEqual(level, "success")
        self.assertIn("test response", message)

    def test_llm_smoke_test_reports_unexpected_response(self):
        level, message = run_llm_smoke_test(FakeLLM(response="something else"))

        self.assertEqual(level, "warning")
        self.assertIn("unexpected response", message)

    def test_download_result_labels_are_user_friendly(self):
        labels = get_download_result_labels("DOCX (Word)")

        self.assertEqual(labels["corrected"], "Download Corrected Manuscript (DOCX)")
        self.assertEqual(labels["highlighted"], "Download Marked Original for Review (DOCX)")
        self.assertEqual(labels["report"], "Download Fix Summary Report (DOCX)")


if __name__ == "__main__":
    unittest.main()
