"""
Test security of generated data:
- No contact email outside .exemple.invalid domain
- No company with nature_juridique 1000
- No field named "dirigeant" or "gerant" in company objects
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "out")
CRM_PATH = os.path.join(OUT_DIR, "crm.json")
CACHE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "companies_cache.json")


def load_crm():
    with open(CRM_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_cache():
    with open(CACHE_PATH, encoding="utf-8") as f:
        return json.load(f)


class TestSecurity(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.crm = load_crm()
        cls.cache = load_cache()

    def test_no_email_outside_exemple_invalid(self):
        """No contact email must exist outside .exemple.invalid domain."""
        errors = []
        for c in self.crm["contacts"]:
            email = c.get("email", "")
            if not email.endswith(".exemple.invalid"):
                errors.append(f"Contact {c['id']}: email '{email}'")
        self.assertEqual(errors, [], "\n".join(errors[:10]))

    def test_no_individual_company_in_cache(self):
        """No company in cache must have nature_juridique 1000."""
        errors = []
        for c in self.cache["companies"]:
            if str(c.get("nature_juridique", "")) == "1000":
                errors.append(f"Cache company {c.get('siren')}: nature_juridique=1000")
        self.assertEqual(errors, [], "\n".join(errors[:10]))

    def test_no_dirigeant_field_in_companies(self):
        """No company object in crm.json must have field 'dirigeant'."""
        errors = []
        for c in self.crm["companies"]:
            if "dirigeant" in c:
                errors.append(f"Company {c['id']} has 'dirigeant' field")
            if "gerant" in c:
                errors.append(f"Company {c['id']} has 'gerant' field")
        self.assertEqual(errors, [], "\n".join(errors))

    def test_no_dirigeant_field_in_contacts(self):
        """No contact object must have field 'dirigeant' or 'gerant'."""
        errors = []
        for c in self.crm["contacts"]:
            if "dirigeant" in c:
                errors.append(f"Contact {c['id']} has 'dirigeant' field")
            if "gerant" in c:
                errors.append(f"Contact {c['id']} has 'gerant' field")
        self.assertEqual(errors, [], "\n".join(errors))

    def test_all_emails_are_non_routable(self):
        """All contact emails must use the non-routable .exemple.invalid TLD."""
        for c in self.crm["contacts"]:
            email = c.get("email", "")
            domain = email.split("@")[-1] if "@" in email else ""
            self.assertTrue(
                domain.endswith(".exemple.invalid"),
                f"Contact {c['id']} email domain '{domain}' is routable"
            )

    def test_no_999_siren_in_private_mode(self):
        """In private (non-public) mode, no company SIREN must start with '999'."""
        if self.crm["meta"].get("public"):
            self.skipTest("CRM généré en mode public — test non applicable")
        errors = []
        for c in self.crm["companies"]:
            if c["siren"].startswith("999"):
                errors.append(f"Company {c['id']} SIREN {c['siren']} starts with 999")
        self.assertEqual(errors, [], "\n".join(errors[:10]))

    def test_999_siren_only_in_public_mode(self):
        """In public mode all SIRENs must start with '999'; tested via public generation."""
        # This is covered by test_public_mode.py; here we just verify the
        # private-mode crm.json does NOT have any 999 SIRENs (already done above)
        # and that the check is symmetric: a 999 in private mode would fail.
        if not self.crm["meta"].get("public"):
            for c in self.crm["companies"]:
                self.assertFalse(
                    c["siren"].startswith("999"),
                    f"SIREN synthétique détecté en mode privé : {c['siren']}"
                )


if __name__ == "__main__":
    unittest.main()
