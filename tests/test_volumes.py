"""
Test volumes: each volume is within ±15% of target.
Exactly 38 anomalies and 6 leurres.
"""

import csv
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

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


class TestVolumes(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.crm = load_crm()
        cls.truth = load_truth()

    def _assert_in_range(self, actual, target, tolerance=0.15, label=""):
        lo = int(target * (1 - tolerance))
        hi = int(target * (1 + tolerance)) + 1
        self.assertGreaterEqual(
            actual, lo,
            f"{label}: {actual} < {lo} (target {target} ± {int(tolerance*100)}%)"
        )
        self.assertLessEqual(
            actual, hi,
            f"{label}: {actual} > {hi} (target {target} ± {int(tolerance*100)}%)"
        )

    def test_companies_count(self):
        n = len(self.crm["companies"])
        self._assert_in_range(n, 220, label="companies")

    def test_contacts_count(self):
        n = len(self.crm["contacts"])
        self._assert_in_range(n, 450, label="contacts")

    def test_open_deals_count(self):
        n = sum(1 for d in self.crm["deals"] if d["status"] == "open")
        self._assert_in_range(n, 110, label="open deals")

    def test_won_deals_count(self):
        n = sum(1 for d in self.crm["deals"] if d["status"] == "won")
        self._assert_in_range(n, 70, label="won deals")

    def test_lost_deals_count(self):
        n = sum(1 for d in self.crm["deals"] if d["status"] == "lost")
        self._assert_in_range(n, 120, label="lost deals")

    def test_activities_count(self):
        n = len(self.crm["activities"])
        self._assert_in_range(n, 5500, label="activities")

    def test_exactly_38_signaler(self):
        n = sum(1 for r in self.truth if r["attendu"] == "signaler")
        self.assertEqual(n, 38, f"Expected 38 signaler rows, got {n}")

    def test_exactly_6_ignorer(self):
        n = sum(1 for r in self.truth if r["attendu"] == "ignorer")
        self.assertEqual(n, 6, f"Expected 6 ignorer rows, got {n}")

    def test_anomaly_codes_distribution(self):
        """Check each anomaly code appears the right number of times."""
        from collections import Counter
        signaler = [r for r in self.truth if r["attendu"] == "signaler"]
        counts = Counter(r["code"] for r in signaler)
        expected = {"A1": 8, "A2": 7, "A3": 6, "A4": 4, "A5": 3,
                    "A6": 3, "A7": 3, "A8": 2, "A9": 2}
        for code, expected_count in expected.items():
            self.assertEqual(
                counts[code], expected_count,
                f"Code {code}: expected {expected_count}, got {counts[code]}"
            )

    def test_leurre_codes_distribution(self):
        """Check each leurre code appears exactly once."""
        from collections import Counter
        ignorer = [r for r in self.truth if r["attendu"] == "ignorer"]
        counts = Counter(r["code"] for r in ignorer)
        for code in ["L1", "L2", "L3", "L4", "L5", "L6"]:
            self.assertEqual(counts[code], 1, f"Leurre {code}: expected 1, got {counts[code]}")


if __name__ == "__main__":
    unittest.main()
