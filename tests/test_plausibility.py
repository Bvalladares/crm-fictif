"""
Test plausibility of generated data:
- dates in order
- future activities only tache or reunion
- amounts in bounds
- won/lost deals have close_date <= as_of
- lost deals have lost_reason
"""

import datetime
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
    import csv
    rows = []
    with open(TRUTH_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


class TestPlausibility(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.crm = load_crm()
        cls.truth = load_truth()
        cls.as_of = datetime.date.fromisoformat(cls.crm["meta"]["as_of"])
        # A5 deal IDs (amount can be null/0)
        cls.a5_deal_ids = {
            r["deal_id"] for r in cls.truth
            if r["attendu"] == "signaler" and r["code"] == "A5"
        }

    def test_deal_dates_order(self):
        """created_at <= all stage_history entries for each deal."""
        errors = []
        for d in self.crm["deals"]:
            created = datetime.date.fromisoformat(d["created_at"][:10])
            for sh in d.get("stage_history", []):
                entered = datetime.date.fromisoformat(sh["entered_at"][:10])
                if entered < created:
                    errors.append(
                        f"Deal {d['id']}: stage {sh['stage']} entered {entered} < created {created}"
                    )
        self.assertEqual(errors, [], "\n".join(errors[:10]))

    def test_future_activities_type(self):
        """Activities after as_of must be tache or reunion only."""
        errors = []
        for a in self.crm["activities"]:
            at_dt = datetime.datetime.fromisoformat(a["at"])
            if at_dt.date() > self.as_of:
                if a["type"] not in ("tache", "reunion"):
                    errors.append(
                        f"Activity {a['id']} is in the future ({a['at']}) but type={a['type']}"
                    )
        self.assertEqual(errors, [], "\n".join(errors[:10]))

    def test_amounts_in_bounds(self):
        """Amounts must be in [3000, 60000] or null (for A5 deals only)."""
        errors = []
        for d in self.crm["deals"]:
            amount = d.get("amount")
            if amount is None or amount == 0:
                if d["id"] not in self.a5_deal_ids:
                    errors.append(
                        f"Deal {d['id']} has null/0 amount but is not A5"
                    )
            else:
                if amount < 3000 or amount > 60000:
                    errors.append(
                        f"Deal {d['id']} has out-of-bounds amount {amount}"
                    )
                if amount % 500 != 0:
                    errors.append(
                        f"Deal {d['id']} amount {amount} not rounded to 500"
                    )
        self.assertEqual(errors, [], "\n".join(errors[:10]))

    def test_won_lost_close_date(self):
        """Won and lost deals must have close_date <= as_of."""
        errors = []
        for d in self.crm["deals"]:
            if d["status"] in ("won", "lost"):
                close = d.get("close_date")
                if close is None:
                    errors.append(f"Deal {d['id']} ({d['status']}) has no close_date")
                    continue
                close_date = datetime.date.fromisoformat(close[:10])
                if close_date > self.as_of:
                    errors.append(
                        f"Deal {d['id']} ({d['status']}) close_date {close_date} > as_of {self.as_of}"
                    )
        self.assertEqual(errors, [], "\n".join(errors[:10]))

    def test_lost_deals_have_reason(self):
        """All lost deals must have a non-null lost_reason."""
        errors = []
        for d in self.crm["deals"]:
            if d["status"] == "lost":
                reason = d.get("lost_reason")
                if not reason:
                    errors.append(f"Deal {d['id']} is lost but has no lost_reason")
        self.assertEqual(errors, [], "\n".join(errors[:10]))

    def test_open_deals_have_no_lost_reason(self):
        """Open deals must have lost_reason = null."""
        errors = []
        for d in self.crm["deals"]:
            if d["status"] == "open":
                reason = d.get("lost_reason")
                if reason is not None:
                    errors.append(f"Deal {d['id']} is open but has lost_reason={reason}")
        self.assertEqual(errors, [], "\n".join(errors[:10]))

    def test_stage_history_monotonic(self):
        """Stage history entries must be in chronological order."""
        errors = []
        for d in self.crm["deals"]:
            sh = d.get("stage_history", [])
            for i in range(1, len(sh)):
                prev = datetime.date.fromisoformat(sh[i-1]["entered_at"][:10])
                curr = datetime.date.fromisoformat(sh[i]["entered_at"][:10])
                if curr < prev:
                    errors.append(
                        f"Deal {d['id']}: stage history not monotonic at index {i}: "
                        f"{sh[i-1]['stage']} {prev} -> {sh[i]['stage']} {curr}"
                    )
        self.assertEqual(errors, [], "\n".join(errors[:10]))

    def test_no_open_deal_without_past_activity(self):
        """Every open deal must have at least one activity with at <= as_of."""
        as_of = self.crm["meta"]["as_of"]
        acts_by_deal = {}
        for a in self.crm["activities"]:
            acts_by_deal.setdefault(a["deal_id"], []).append(a)
        errors = []
        for d in self.crm["deals"]:
            if d["status"] != "open":
                continue
            past = [a for a in acts_by_deal.get(d["id"], [])
                    if a["at"][:10] <= as_of]
            if not past:
                errors.append(f"Deal {d['id']} ({d['stage']}) has no past activity")
        self.assertEqual(errors, [], "\n".join(errors[:10]))

    def test_deal_name_format(self):
        """
        Deal names must:
        - contain no internal ID pattern (C-NNNN, D-NNNN, P-NNNN)
        - not start with 'Mission '
        - contain a separator (' – ' or ' - ') separating company fragment from object
        """
        import re
        id_pattern = re.compile(r'\b[CDP]-\d{4}\b')
        errors = []
        for d in self.crm["deals"]:
            name = d["name"]
            if id_pattern.search(name):
                errors.append(f"Deal {d['id']} name contains internal ID: '{name}'")
            if name.startswith("Mission "):
                errors.append(f"Deal {d['id']} name starts with 'Mission': '{name}'")
            if " – " not in name and " - " not in name:
                errors.append(f"Deal {d['id']} name has no separator: '{name}'")
        self.assertEqual(errors, [], "\n".join(errors[:10]))

    def test_contact_emails_format(self):
        """Contact emails must end with .exemple.invalid."""
        errors = []
        for c in self.crm["contacts"]:
            email = c.get("email", "")
            if not email.endswith(".exemple.invalid"):
                errors.append(f"Contact {c['id']} email '{email}' not .exemple.invalid domain")
        self.assertEqual(errors, [], "\n".join(errors[:10]))


if __name__ == "__main__":
    unittest.main()
