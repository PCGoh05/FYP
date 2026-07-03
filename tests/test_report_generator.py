import unittest
from types import SimpleNamespace

from modules.auto_fixer import ChangeRecord, PostFixValidationResult
from modules.report_generator import ReportGenerator


class ReportGeneratorTest(unittest.TestCase):
    def test_report_includes_post_fix_validation_summary(self):
        validation = PostFixValidationResult(
            is_safe=True,
            before_issues=4,
            after_issues=1,
            before_score=92.0,
            after_score=98.0,
            issue_delta=-3,
            score_delta=6.0,
            new_or_increased_categories={},
            message="Post-fix validation did not increase detected issues.",
        )
        post_fix_result = SimpleNamespace(
            issues_by_category={
                "references": [
                    SimpleNamespace(
                        location="Reference 1",
                        description="Reference publication source may need italic formatting",
                    )
                ]
            }
        )

        report = ReportGenerator(
            rules={},
            changes=[],
            check_result=None,
            post_fix_validation=validation,
            post_fix_result=post_fix_result,
        ).generate_comparison_report()

        text = "\n".join(paragraph.text for paragraph in report.paragraphs)

        self.assertIn("Post-Fix Validation", text)
        self.assertIn("Issues before auto-fix: 4", text)
        self.assertIn("Issues after auto-fix: 1", text)
        self.assertIn("Remaining Issues After Auto-Fix", text)

    def test_report_explains_highlighted_corrected_output(self):
        report = ReportGenerator(
            rules={},
            changes=[],
            check_result=None,
        ).generate_comparison_report()

        text = "\n".join(paragraph.text for paragraph in report.paragraphs)

        self.assertIn("How to Use This Report", text)
        self.assertIn("Highlighted Corrected Manuscript", text)
        self.assertIn("marks applied-change locations in yellow", text)
        self.assertIn("visible header text is unchanged", text)

    def test_report_includes_auto_fix_scope_limits(self):
        report = ReportGenerator(
            rules={},
            changes=[],
            check_result=None,
        ).generate_comparison_report()

        text = "\n".join(paragraph.text for paragraph in report.paragraphs)

        self.assertIn("Auto-Fix Scope", text)
        self.assertIn("Automatic fixes are limited to detected formatting properties", text)
        self.assertIn("manual review", text)

    def test_report_groups_repeated_reference_changes(self):
        changes = [
            ChangeRecord(
                paragraph_index=-1,
                location=f"Reference Content Control {index}",
                change_type="reference",
                before="0.49in",
                after="0.444444in",
                text_preview="[1] Example reference",
                property_name="hanging_indent",
                current_value="0.49in",
                target_value="0.444444in",
                paragraph_type="reference",
                evidence="Reference hanging indent did not match target rule",
            )
            for index in range(1, 6)
        ]

        grouped = ReportGenerator._group_repeated_changes(changes)

        self.assertEqual(len(grouped), 1)
        self.assertEqual(grouped[0]["location"], "Reference entries (5 changes)")
        self.assertEqual(grouped[0]["property_name"], "hanging_indent")


if __name__ == "__main__":
    unittest.main()
