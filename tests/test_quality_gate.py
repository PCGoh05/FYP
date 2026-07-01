import unittest
from pathlib import Path

from run_quality_checks import (
    build_command_checks,
    find_non_english_markers,
    find_secret_markers,
    is_scannable_text_file,
)


class QualityGateTest(unittest.TestCase):
    def test_builds_core_quality_commands_without_evaluation_paths(self):
        checks = build_command_checks("python")
        names = [check.name for check in checks]
        commands = [" ".join(check.command) for check in checks]

        self.assertEqual(names, ["unit tests", "compile check"])
        self.assertIn("python -m unittest discover -s tests -p test_*.py", commands)
        self.assertIn("python -m compileall -q app.py config.py evaluate_checker.py modules tests", commands)

    def test_adds_evaluation_command_when_template_and_samples_are_given(self):
        checks = build_command_checks(
            "python",
            template_path="template.docx",
            samples_path="samples",
            summary_json="summary.json",
            summary_md="summary.md",
        )

        self.assertEqual(checks[-1].name, "evaluation smoke test")
        self.assertEqual(
            checks[-1].command,
            [
                "python",
                "evaluate_checker.py",
                "--template",
                "template.docx",
                "--samples",
                "samples",
                "--auto-fix-evaluation",
                "--summary-json",
                "summary.json",
                "--summary-md",
                "summary.md",
            ],
        )

    def test_detects_non_english_cjk_text(self):
        markers = find_non_english_markers("English text only.\n\u4e2d\u6587 text.")

        self.assertEqual(markers, [(2, "CJK character detected")])

    def test_detects_api_key_patterns_without_returning_secret(self):
        text = (
            'NVIDIA_API_KEY = "nvapi-' + '1234567890abcdef"\n'
            'OPENAI_API_KEY = "sk-' + 'test"'
        )

        markers = find_secret_markers(text)

        self.assertEqual(
            markers,
            [(1, "NVIDIA API key pattern"), (2, "OpenAI API key pattern")],
        )

    def test_scannable_text_file_filter_excludes_binary_outputs(self):
        self.assertTrue(is_scannable_text_file(Path("modules/checker.py")))
        self.assertTrue(is_scannable_text_file(Path("template_profiles/jiwe.json")))
        self.assertFalse(is_scannable_text_file(Path("docs/report.docx")))
        self.assertFalse(is_scannable_text_file(Path(".venv/Lib/site.py")))


if __name__ == "__main__":
    unittest.main()
