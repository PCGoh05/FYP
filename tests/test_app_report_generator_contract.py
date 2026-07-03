import unittest
from unittest.mock import patch

import app
from app import build_report_generator, group_changes_for_display
from modules.auto_fixer import ChangeRecord


class LegacyReportGenerator:
    def __init__(self, rules, changes, check_result=None):
        self.rules = rules
        self.changes = changes
        self.check_result = check_result


class AppReportGeneratorContractTest(unittest.TestCase):
    def test_build_report_generator_works_with_legacy_constructor(self):
        report = build_report_generator(
            rules={"body_text": {"font": "Times New Roman"}},
            changes=[],
            check_result=None,
            post_fix_validation=object(),
            post_fix_result=object(),
            generator_cls=LegacyReportGenerator,
        )

        self.assertIsInstance(report, LegacyReportGenerator)

    def test_group_changes_for_display_handles_legacy_report_generator(self):
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
            for index in range(1, 4)
        ]

        with patch.object(app, "ReportGenerator", LegacyReportGenerator):
            grouped = group_changes_for_display(changes)

        self.assertEqual(len(grouped), 1)
        self.assertEqual(grouped[0]["location"], "Reference entries (3 changes)")


if __name__ == "__main__":
    unittest.main()
