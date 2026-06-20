import unittest
from types import SimpleNamespace

import modules.auto_fixer as auto_fixer


class PostFixValidationTest(unittest.TestCase):
    def test_flags_corrected_document_when_issue_count_increases(self):
        self.assertTrue(hasattr(auto_fixer, "validate_post_fix_result"))

        before = SimpleNamespace(total_issues=2, compliance_score=95.0, issues_by_category={})
        after = SimpleNamespace(total_issues=5, compliance_score=90.0, issues_by_category={})

        validation = auto_fixer.validate_post_fix_result(before, after)

        self.assertFalse(validation.is_safe)
        self.assertEqual(validation.issue_delta, 3)
        self.assertIn("more issues", validation.message)

    def test_allows_corrected_document_when_issue_count_does_not_increase(self):
        self.assertTrue(hasattr(auto_fixer, "validate_post_fix_result"))

        before = SimpleNamespace(total_issues=5, compliance_score=88.0, issues_by_category={})
        after = SimpleNamespace(total_issues=3, compliance_score=92.0, issues_by_category={})

        validation = auto_fixer.validate_post_fix_result(before, after)

        self.assertTrue(validation.is_safe)
        self.assertEqual(validation.issue_delta, -2)
        self.assertIn("did not increase", validation.message)


if __name__ == "__main__":
    unittest.main()
