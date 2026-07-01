import tempfile
import unittest
from pathlib import Path

from evaluate_checker import (
    build_arg_parser,
    calculate_category_issue_metrics,
    console_safe,
    render_evaluation_markdown,
    validate_evaluation_inputs,
)


class EvaluateCheckerInputValidationTest(unittest.TestCase):
    def test_cli_does_not_default_to_removed_sample_files(self):
        parser = build_arg_parser()

        template_action = next(
            action for action in parser._actions if action.dest == "template"
        )
        samples_action = next(
            action for action in parser._actions if action.dest == "samples"
        )

        self.assertIsNone(template_action.default)
        self.assertIsNone(samples_action.default)

    def test_render_evaluation_markdown_includes_smoke_and_auto_fix_tables(self):
        summary = {
            "template": "JIWE_Template.docx",
            "samples": "PUBLISHED/TEST",
            "files_checked": 1,
            "invalid_samples": [],
            "smoke_rows": [
                {
                    "file": "sample.docx",
                    "score": 92.4,
                    "issues": 4,
                    "categories": {"structure": 1, "references": 3},
                    "post_fix": {
                        "before_issues": 4,
                        "after_issues": 1,
                        "before_score": 92.4,
                        "after_score": 98.1,
                        "is_safe": True,
                    },
                }
            ],
            "overall_issue_metrics": {
                "precision": 0.8,
                "recall": 0.75,
                "f1": 0.7742,
            },
            "overall_paragraph_metrics": {
                "accuracy": 0.9,
                "precision": 0.88,
                "recall": 0.86,
                "f1": 0.8699,
            },
            "category_issue_metrics": {
                "body_text": {
                    "true_positive": 1,
                    "false_positive": 0,
                    "false_negative": 1,
                    "precision": 1.0,
                    "recall": 0.5,
                    "f1": 0.6667,
                }
            },
        }

        markdown = render_evaluation_markdown(summary)

        self.assertIn("# Manuscript Checker Evaluation Summary", markdown)
        self.assertIn("| sample.docx | 92.4 | 4 |", markdown)
        self.assertIn("## Auto-Fix Before/After", markdown)
        self.assertIn("| sample.docx | 4 | 1 | 92.4 | 98.1 | Yes |", markdown)
        self.assertIn("## Manual-Label Metrics", markdown)
        self.assertIn("### Issue Metrics by Category", markdown)
        self.assertIn("| Body Text | 1.0 | 0.5 | 0.6667 | 1 | 0 | 1 |", markdown)

    def test_calculates_issue_metrics_by_category(self):
        predicted = {
            ("sample.docx", "body_text", "Paragraph 1", "Font mismatch"),
            ("sample.docx", "references", "Reference 1", "Missing citation"),
        }
        expected = {
            ("sample.docx", "body_text", "Paragraph 1", "Font mismatch"),
            ("sample.docx", "body_text", "Paragraph 2", "Size mismatch"),
        }

        metrics = calculate_category_issue_metrics(predicted, expected)

        self.assertEqual(metrics["body_text"]["true_positive"], 1)
        self.assertEqual(metrics["body_text"]["false_positive"], 0)
        self.assertEqual(metrics["body_text"]["false_negative"], 1)
        self.assertEqual(metrics["body_text"]["precision"], 1.0)
        self.assertEqual(metrics["body_text"]["recall"], 0.5)
        self.assertEqual(metrics["body_text"]["f1"], 0.6667)
        self.assertEqual(metrics["references"]["true_positive"], 0)
        self.assertEqual(metrics["references"]["false_positive"], 1)
        self.assertEqual(metrics["references"]["false_negative"], 0)

    def test_console_safe_replaces_unprintable_characters(self):
        text = console_safe("A\u2009B", encoding="cp1252")

        self.assertEqual(text, "A?B")

    def test_missing_template_returns_clear_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            template_path = Path(tmp) / "missing_template.docx"
            samples_dir = Path(tmp)

            message = validate_evaluation_inputs(template_path, samples_dir)

        self.assertEqual(
            message,
            f"Template file not found: {template_path}",
        )

    def test_missing_samples_directory_returns_clear_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            template_path = Path(tmp) / "template.docx"
            template_path.write_bytes(b"placeholder")
            samples_dir = Path(tmp) / "missing_samples"

            message = validate_evaluation_inputs(template_path, samples_dir)

        self.assertEqual(
            message,
            f"Samples directory not found: {samples_dir}",
        )


if __name__ == "__main__":
    unittest.main()
