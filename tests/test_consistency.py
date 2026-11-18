"""
Test consistency: rules.py applied to crm.json must find exactly the
"signaler" rows in truth.csv (same deal_ids and codes), and must NOT
flag any "ignorer" rows.
"""

import csv
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from nova.rules import run_all_rules

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "out")
CRM_PATH = os.path.join(OUT_DIR, "crm.json")
TRUTH_PATH = os.path.join(OUT_DIR, "truth.csv")


def load_crm():
    with open(CRM_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_truth():
    rows = []
    with open(TRUTH_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


class TestConsistency(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.crm = load_crm()
        cls.truth = load_truth()
        cls.as_of = cls.crm["meta"]["as_of"]

        cls.signaler_expected = {
            (r["deal_id"], r["code"])
            for r in cls.truth
            if r["attendu"] == "signaler"
        }
        cls.ignorer_expected = {
            (r["deal_id"], r["code"])
            for r in cls.truth
            if r["attendu"] == "ignorer"
        }

        cls.rule_results = run_all_rules(cls.crm, cls.as_of)
        cls.rule_found = {(deal_id, code) for deal_id, code, _ in cls.rule_results}

    def test_rules_find_all_signaler(self):
        """Rules must find ALL anomalies listed as 'signaler' in truth.csv."""
        missing = self.signaler_expected - self.rule_found
        self.assertEqual(
            missing, set(),
            f"Rules missed these anomalies: {sorted(missing)}"
        )

    def test_rules_no_extra_flags(self):
        """Rules must not flag anything beyond what's in truth.csv signaler rows."""
        extra = self.rule_found - self.signaler_expected
        self.assertEqual(
            extra, set(),
            f"Rules flagged unexpected items: {sorted(extra)}"
        )

    def test_rules_do_not_flag_leurres(self):
        """Rules must NOT flag any 'ignorer' rows from truth.csv."""
        false_positives = self.rule_found & self.ignorer_expected
        self.assertEqual(
            false_positives, set(),
            f"Rules incorrectly flagged leurres: {sorted(false_positives)}"
        )

    def test_signaler_count(self):
        """Exactly 38 'signaler' rows in truth.csv."""
        n = sum(1 for r in self.truth if r["attendu"] == "signaler")
        self.assertEqual(n, 38, f"Expected 38 signaler rows, got {n}")

    def test_ignorer_count(self):
        """Exactly 6 'ignorer' rows in truth.csv."""
        n = sum(1 for r in self.truth if r["attendu"] == "ignorer")
        self.assertEqual(n, 6, f"Expected 6 ignorer rows, got {n}")


if __name__ == "__main__":
    unittest.main()
