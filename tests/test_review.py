"""
tests/test_review.py — Tests for the review pipeline.
"""

import csv
import json
import os
import re
import sys
import unittest

# Ensure repo root is on the path
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

FACTS_PATH = os.path.join(_ROOT, "out", "facts.json")
TRUTH_PATH = os.path.join(_ROOT, "out", "truth.csv")
REVIEW_RAW_PATH = os.path.join(_ROOT, "out", "review_raw.md")
EVAL_PATH = os.path.join(_ROOT, "out", "eval_review_raw.json")


def _load_facts():
    with open(FACTS_PATH, encoding="utf-8") as f:
        return json.load(f)


def _load_truth():
    rows = []
    with open(TRUTH_PATH, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append(row)
    return rows


def _load_review():
    with open(REVIEW_RAW_PATH, encoding="utf-8") as f:
        return f.read()


def _load_eval():
    with open(EVAL_PATH, encoding="utf-8") as f:
        return json.load(f)


RULE_WEIGHTS = {
    "A4": 3, "A7": 3,
    "A1": 2, "A2": 2, "A3": 2,
}

STAGE_PRIORITY_WEIGHT = {
    "decouverte": 0.5, "qualification": 0.7, "demo": 1.0,
    "proposition": 1.5, "negociation": 2.0,
}

# Maps French labels (stored in facts.json entries) back to STAGE_PRIORITY_WEIGHT keys
STAGE_LABEL_TO_KEY = {
    "Découverte": "decouverte",
    "Qualification": "qualification",
    "Démo": "demo",
    "Proposition envoyée": "proposition",
    "Négociation": "negociation",
}


def _weight(code):
    return RULE_WEIGHTS.get(code, 1)


def _score(amount, codes, stage=None):
    stage_w = STAGE_PRIORITY_WEIGHT.get(stage, 1.0)
    return (amount or 0) * sum(_weight(c) for c in codes) * stage_w


class TestFactsFlaggedMatchesTruth(unittest.TestCase):
    """Every deal_id in by_owner[*].flagged must match 'signaler' in truth.csv exactly."""

    def test_facts_flagged_matches_truth(self):
        facts = _load_facts()
        truth_rows = _load_truth()

        signaler_ids = {r["deal_id"] for r in truth_rows if r["attendu"] == "signaler"}
        ignorer_ids = {r["deal_id"] for r in truth_rows if r["attendu"] == "ignorer"}

        flagged_ids = set()
        for owner in facts["by_owner"]:
            for entry in owner["flagged"]:
                flagged_ids.add(entry["deal_id"])

        # Every flagged deal must be in signaler
        in_flagged_not_signaler = flagged_ids - signaler_ids
        self.assertEqual(
            in_flagged_not_signaler, set(),
            f"Flagged deals not in truth signaler: {in_flagged_not_signaler}"
        )

        # Every signaler must be flagged
        in_signaler_not_flagged = signaler_ids - flagged_ids
        self.assertEqual(
            in_signaler_not_flagged, set(),
            f"Signaler deals missing from flagged: {in_signaler_not_flagged}"
        )

        # No ignorer deal in flagged
        ignorer_in_flagged = flagged_ids & ignorer_ids
        self.assertEqual(
            ignorer_in_flagged, set(),
            f"Ignorer deals wrongly flagged: {ignorer_in_flagged}"
        )


class TestFactsExcusedNotFlagged(unittest.TestCase):
    """No excused deal_id may appear in by_owner[*].flagged."""

    def test_facts_excused_not_flagged(self):
        facts = _load_facts()

        excused_ids = {e["deal_id"] for e in facts.get("excused", [])}
        flagged_ids = set()
        for owner in facts["by_owner"]:
            for entry in owner["flagged"]:
                flagged_ids.add(entry["deal_id"])

        overlap = excused_ids & flagged_ids
        self.assertEqual(
            overlap, set(),
            f"Excused deals appear in flagged: {overlap}"
        )


class TestPrioritiesFormula(unittest.TestCase):
    """Recompute priorities from facts.json and verify they match facts['priorities']."""

    def test_priorities_formula(self):
        facts = _load_facts()

        # Build all flagged deals with amounts and stage
        all_flagged = {}  # deal_id -> (amount, codes, stage_key)
        for owner in facts["by_owner"]:
            for entry in owner["flagged"]:
                stage_label = entry.get("stage", "")
                stage_key = STAGE_LABEL_TO_KEY.get(stage_label, stage_label.lower())
                all_flagged[entry["deal_id"]] = (entry["amount"], entry["codes"], stage_key)

        # Sort by score desc, then amount desc, then deal_id asc
        sorted_deals = sorted(
            all_flagged.keys(),
            key=lambda did: (
                -_score(all_flagged[did][0], all_flagged[did][1], all_flagged[did][2]),
                -all_flagged[did][0],
                did
            )
        )
        expected_priorities = sorted_deals[:3]

        self.assertEqual(
            facts["priorities"], expected_priorities,
            f"Priorities mismatch. Expected {expected_priorities}, got {facts['priorities']}"
        )


class TestAllowedNumbersCoverage(unittest.TestCase):
    """Every number in facts phrases and amounts must appear in allowed_numbers."""

    def _extract_bare_numbers(self, text):
        """Extract standalone numeric tokens from text, excluding ISO date sub-parts."""
        # Mark date positions
        date_positions = set()
        for m in re.finditer(r'\b\d{4}-\d{2}-\d{2}\b', text):
            for i in range(m.start(), m.end()):
                date_positions.add(i)

        found = set()
        for m in re.finditer(r'\b\d+\b', text):
            if any(i in date_positions for i in range(m.start(), m.end())):
                continue
            found.add(m.group(0))
        return found

    def test_allowed_numbers_coverage(self):
        facts = _load_facts()
        allowed = set(facts.get("allowed_numbers", []))

        missing = []

        for owner in facts["by_owner"]:
            for entry in owner["flagged"]:
                # Check amounts
                amt = entry["amount"]
                if amt:
                    for tok in [str(amt), f"{amt:,}".replace(",", " ")]:
                        # Just check if the raw amount string is covered
                        pass

                # Check fact phrases
                for phrase in entry.get("facts", []):
                    for tok in self._extract_bare_numbers(phrase):
                        if tok not in allowed:
                            missing.append((entry["deal_id"], phrase, tok))

        self.assertEqual(
            missing, [],
            f"Numbers not in allowed_numbers: {missing[:10]}"
        )


class TestRenderRawScoresPerfect(unittest.TestCase):
    """out/eval_review_raw.json must show perfect score."""

    def test_render_raw_scores_perfect(self):
        ev = _load_eval()
        self.assertEqual(ev["recall"], 1.0, f"recall={ev['recall']} != 1.0")
        self.assertEqual(ev["false_leurres"], 0, f"false_leurres={ev['false_leurres']} != 0")
        self.assertEqual(ev["invented_numbers"], 0, f"invented_numbers={ev['invented_numbers']} != 0")
        self.assertTrue(ev.get("one_on_one_present", False), "one_on_one_present should be True")
        self.assertTrue(ev.get("one_on_one_numbers_ok", True), "one_on_one_numbers_ok should be True")
        self.assertTrue(ev["pass"], f"pass={ev['pass']} != True")


class TestEvaluateDetectsErrors(unittest.TestCase):
    """Poisoned review should fail the scorer."""

    def test_evaluate_detects_errors(self):
        from review.evaluate import score_review

        facts = _load_facts()
        truth_rows = _load_truth()
        review_text = _load_review()

        # Collect flagged deal names
        all_flagged_names = []
        for owner in facts["by_owner"]:
            for entry in owner["flagged"]:
                all_flagged_names.append(entry["deal_name"])

        # Collect an ignorer deal name (not in excused)
        excused_ids = {e["deal_id"] for e in facts.get("excused", [])}
        ignorer_ids = {r["deal_id"] for r in truth_rows if r["attendu"] == "ignorer"}
        non_excused_ignorer = ignorer_ids - excused_ids

        # Get a deal name for a non-excused ignorer deal
        # Build id->name from crm (we'll need to load crm.json)
        import os as _os
        crm_path = _os.path.join(_ROOT, "out", "crm.json")
        with open(crm_path, encoding="utf-8") as f:
            crm = json.load(f)
        deals_by_id = {d["id"]: d for d in crm["deals"]}

        ignorer_name = None
        for iid in sorted(non_excused_ignorer):
            d = deals_by_id.get(iid)
            if d:
                ignorer_name = d["name"]
                break

        # Poison the review:
        # 1. Remove 5 flagged deal names (replace with XXXXXXX)
        poisoned = review_text
        removed = 0
        for name in all_flagged_names:
            if removed >= 5:
                break
            if name in poisoned:
                poisoned = poisoned.replace(name, "DEAL_REMOVED_" + str(removed))
                removed += 1

        # 2. Add one ignorer deal name in a non-excused section (Priorités)
        if ignorer_name:
            poisoned = poisoned.replace(
                "## Priorités",
                f"## Priorités\n{ignorer_name}\n"
            )

        # 3. Replace one real allowed number with 99999
        # Find first standalone number in facts that's not in name/dates
        real_number = None
        for n in facts["allowed_numbers"]:
            if re.match(r'^\d{4,6}$', n) and n in poisoned:
                real_number = n
                break
        if real_number:
            poisoned = poisoned.replace(real_number, "99999", 1)

        result = score_review(poisoned, facts, truth_rows)

        self.assertLess(result["recall"], 0.90,
                        f"Recall should be < 0.90 after removing 5 deals, got {result['recall']}")
        self.assertGreaterEqual(result["false_leurres"], 1,
                                f"false_leurres should be >= 1 after adding ignorer deal")
        self.assertGreaterEqual(result["invented_numbers"], 1,
                                f"invented_numbers should be >= 1 after adding 99999")


if __name__ == "__main__":
    unittest.main()
