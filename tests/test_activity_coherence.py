"""
Test activity coherence: stage-aware content, closing discipline,
no duplicates, etc.
All tests read from out/crm.json + out/truth.csv.
Skip if crm.json is missing.
"""

import csv
import datetime
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "out")
CRM_PATH = os.path.join(OUT_DIR, "crm.json")
TRUTH_PATH = os.path.join(OUT_DIR, "truth.csv")


def _load_crm():
    with open(CRM_PATH, encoding="utf-8") as f:
        return json.load(f)


def _load_truth():
    rows = []
    with open(TRUTH_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def _get_stage_at_date(stage_history, activity_date):
    """
    Determine which pipeline stage the deal was in at the given activity_date.
    Iterates stage_history and returns the last entry whose entered_at <= activity_date.
    """
    if isinstance(activity_date, str):
        activity_date = datetime.date.fromisoformat(activity_date[:10])
    stage_at = None
    for entry in stage_history:
        entered = datetime.date.fromisoformat(entry["entered_at"][:10])
        if entered <= activity_date:
            stage_at = entry["stage"]
    return stage_at


def _skip_if_missing():
    if not os.path.exists(CRM_PATH):
        raise unittest.SkipTest("crm.json not found — run generate.py first")


class TestActivityCoherence(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if not os.path.exists(CRM_PATH):
            cls._skip = True
            return
        cls._skip = False
        cls.crm = _load_crm()
        cls.truth = _load_truth()
        cls.as_of = datetime.date.fromisoformat(cls.crm["meta"]["as_of"])

        # Index deals by id
        cls.deals_by_id = {d["id"]: d for d in cls.crm["deals"]}

        # Index activities by deal
        cls.acts_by_deal = {}
        for a in cls.crm["activities"]:
            cls.acts_by_deal.setdefault(a["deal_id"], []).append(a)

    def setUp(self):
        if getattr(self, "_skip", False):
            self.skipTest("crm.json not found — run generate.py first")

    def test_no_contract_before_negociation(self):
        """
        For every activity on an open or won deal, if the stage at that activity's date
        was decouverte, qualification, demo, or proposition, the body must not contain
        'contrat' or 'signature' (case-insensitive).
        """
        FORBIDDEN_STAGES = {"decouverte", "qualification", "demo", "proposition"}
        FORBIDDEN_WORDS = ["contrat", "signature"]
        errors = []

        for deal in self.crm["deals"]:
            if deal["status"] not in ("open", "won"):
                continue
            did = deal["id"]
            stage_history = deal.get("stage_history", [])
            for a in self.acts_by_deal.get(did, []):
                act_date = datetime.date.fromisoformat(a["at"][:10])
                stage_at = _get_stage_at_date(stage_history, act_date)
                if stage_at not in FORBIDDEN_STAGES:
                    continue
                body_lower = (a.get("body") or "").lower()
                for word in FORBIDDEN_WORDS:
                    if word in body_lower:
                        errors.append(
                            f"Deal {did} activity {a.get('id','?')} at {a['at'][:10]} "
                            f"(stage={stage_at}): body contains '{word}': {a['body'][:80]}"
                        )
                        break

        self.assertEqual(errors, [], f"{len(errors)} violations:\n" + "\n".join(errors[:10]))

    def test_no_devis_before_proposition(self):
        """
        For every activity on an open or won deal, if the stage at that activity's date
        was decouverte, qualification, or demo, the body must not contain 'devis' or
        'proposition commerciale' (case-insensitive).
        """
        FORBIDDEN_STAGES = {"decouverte", "qualification", "demo"}
        FORBIDDEN_PHRASES = ["devis", "proposition commerciale"]
        errors = []

        for deal in self.crm["deals"]:
            if deal["status"] not in ("open", "won"):
                continue
            did = deal["id"]
            stage_history = deal.get("stage_history", [])
            for a in self.acts_by_deal.get(did, []):
                act_date = datetime.date.fromisoformat(a["at"][:10])
                stage_at = _get_stage_at_date(stage_history, act_date)
                if stage_at not in FORBIDDEN_STAGES:
                    continue
                body_lower = (a.get("body") or "").lower()
                for phrase in FORBIDDEN_PHRASES:
                    if phrase in body_lower:
                        errors.append(
                            f"Deal {did} activity {a.get('id','?')} at {a['at'][:10]} "
                            f"(stage={stage_at}): body contains '{phrase}': {a['body'][:80]}"
                        )
                        break

        self.assertEqual(errors, [], f"{len(errors)} violations:\n" + "\n".join(errors[:10]))

    def test_no_activity_after_close_date_for_closed_deals(self):
        """
        For won and lost deals, no activity's date (date part only) must be
        strictly after close_date.
        """
        errors = []
        for deal in self.crm["deals"]:
            if deal["status"] not in ("won", "lost"):
                continue
            did = deal["id"]
            close_date_str = deal.get("close_date")
            if not close_date_str:
                continue
            close_date = datetime.date.fromisoformat(close_date_str[:10])
            for a in self.acts_by_deal.get(did, []):
                act_date = datetime.date.fromisoformat(a["at"][:10])
                if act_date > close_date:
                    errors.append(
                        f"Deal {did} ({deal['status']}): activity {a.get('id','?')} "
                        f"at {a['at'][:10]} is after close_date {close_date}"
                    )
        self.assertEqual(errors, [], f"{len(errors)} violations:\n" + "\n".join(errors[:10]))

    def test_closing_note_exists(self):
        """
        Every won and lost deal must have exactly one activity with type='note'
        and at date == close_date (the closing note with the right subject).
        """
        errors = []
        closing_subjects = {"Deal gagné", "Deal perdu"}
        for deal in self.crm["deals"]:
            if deal["status"] not in ("won", "lost"):
                continue
            did = deal["id"]
            close_date_str = deal.get("close_date")
            if not close_date_str:
                errors.append(f"Deal {did} ({deal['status']}) has no close_date")
                continue
            close_date = datetime.date.fromisoformat(close_date_str[:10])
            closing_notes = [
                a for a in self.acts_by_deal.get(did, [])
                if a["type"] == "note"
                and datetime.date.fromisoformat(a["at"][:10]) == close_date
                and a.get("subject") in closing_subjects
            ]
            if len(closing_notes) != 1:
                errors.append(
                    f"Deal {did} ({deal['status']}, close={close_date}): "
                    f"expected 1 closing note, found {len(closing_notes)}"
                )
        self.assertEqual(errors, [], f"{len(errors)} violations:\n" + "\n".join(errors[:10]))

    def test_no_duplicate_body_on_same_deal(self):
        """
        For each deal, no two activities may share the exact same body text.
        """
        errors = []
        for did, acts in self.acts_by_deal.items():
            seen = {}
            for a in acts:
                body = a.get("body", "")
                if body in seen:
                    errors.append(
                        f"Deal {did}: duplicate body on activities "
                        f"{seen[body]} and {a.get('id','?')}: {body[:60]}"
                    )
                else:
                    seen[body] = a.get("id", "?")
        self.assertEqual(errors, [], f"{len(errors)} violations:\n" + "\n".join(errors[:10]))


if __name__ == "__main__":
    unittest.main()
