import unittest

from app import build_report_generator


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


if __name__ == "__main__":
    unittest.main()
