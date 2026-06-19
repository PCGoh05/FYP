import tempfile
import unittest
from pathlib import Path

from evaluate_checker import validate_evaluation_inputs


class EvaluateCheckerInputValidationTest(unittest.TestCase):
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
