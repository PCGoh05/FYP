import unittest

from modules.profile_loader import ProfileLoader


class ProfileAuthorTermsTest(unittest.TestCase):
    def test_jiwe_profile_provides_affiliation_role_terms(self):
        rules = ProfileLoader().default_rules(ProfileLoader().load("jiwe"))

        terms = rules.get("author_role_terms", {}).get("affiliation", [])

        self.assertIn("sdn bhd", terms)
        self.assertIn("medical centre", terms)


if __name__ == "__main__":
    unittest.main()
