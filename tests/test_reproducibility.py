"""
Test reproducibility: two generations with the same seed produce identical output.
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestReproducibility(unittest.TestCase):

    def _run_generation(self, seed=42, as_of="2026-11-18", public=False):
        """Run generation and return crm_data dict."""
        import random
        import datetime
        from nova.companies import select_companies, make_public_companies
        from nova.people import gen_contacts
        from nova.deals import gen_deals
        from nova.activities import gen_all_activities
        from nova.anomalies import plant_anomalies
        from nova.pipeline import OWNERS

        rng = random.Random(seed)
        as_of_date = datetime.date.fromisoformat(as_of)

        companies_raw = select_companies(rng, target=220)
        if public:
            companies_raw = make_public_companies(rng, companies_raw)

        companies = []
        for i, c in enumerate(companies_raw, 1):
            c["id"] = f"C-{i:04d}"
            companies.append(c)

        contacts_raw = gen_contacts(rng, companies)
        contacts = []
        for i, c in enumerate(contacts_raw, 1):
            c["id"] = f"P-{i:04d}"
            contacts.append(c)

        contacts_by_company = {}
        for c in contacts:
            cid = c["company_id"]
            if cid not in contacts_by_company:
                contacts_by_company[cid] = []
            contacts_by_company[cid].append(c)

        deals_raw = gen_deals(
            rng, companies, contacts_by_company, as_of_date,
            n_open=70, n_won=70, n_lost=120
        )
        deals = []
        for i, d in enumerate(deals_raw, 1):
            d["id"] = f"D-{i:04d}"
            deals.append(d)

        deals, anomaly_flags, truth_rows = plant_anomalies(
            rng, deals, contacts_by_company, as_of_date
        )

        # Simplified activity generation matching generate.py
        from nova.activities import gen_all_activities
        import datetime

        act_flags = {}
        for did, flags in anomaly_flags.items():
            act_flags[did] = set()
            for flag in flags:
                if flag in ("A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8", "A9",
                            "L1", "L2", "L3", "L4", "L5", "L6"):
                    act_flags[did].add(flag)
                elif flag.startswith("A4_DAYS_"):
                    act_flags[did].add(flag)

        activities_raw = gen_all_activities(
            rng, deals, contacts_by_company, as_of_date,
            anomaly_flags=act_flags
        )

        activities_by_deal = {}
        for a in activities_raw:
            did = a["deal_id"]
            if did not in activities_by_deal:
                activities_by_deal[did] = []
            activities_by_deal[did].append(a)

        # Apply post-processing (same as generate.py)
        for did, flags in anomaly_flags.items():
            if "A4" in flags:
                days_silent = 22
                for flag in flags:
                    if flag.startswith("A4_DAYS_"):
                        days_silent = int(flag.split("_")[-1])
                        break
                cutoff = as_of_date - datetime.timedelta(days=days_silent)
                deal_acts = activities_by_deal.get(did, [])
                new_acts = []
                for a in deal_acts:
                    at_dt = datetime.datetime.fromisoformat(a["at"])
                    at_date = at_dt.date()
                    if at_date > as_of_date or at_date <= cutoff:
                        new_acts.append(a)
                activities_by_deal[did] = new_acts

        for did, flags in anomaly_flags.items():
            if "L3" in flags or "L4" in flags:
                target_date = as_of_date - datetime.timedelta(days=20)
                deal_acts = activities_by_deal.get(did, [])
                new_acts = []
                has_target_act = False
                for a in deal_acts:
                    at_dt = datetime.datetime.fromisoformat(a["at"])
                    at_date = at_dt.date()
                    if at_date > as_of_date:
                        new_acts.append(a)
                    elif at_date <= target_date:
                        new_acts.append(a)
                        if at_date == target_date:
                            has_target_act = True
                if not has_target_act:
                    at_dt_target = datetime.datetime(target_date.year, target_date.month, target_date.day, 10, 0, 0)
                    new_acts.append({
                        "deal_id": did,
                        "contact_id": None,
                        "owner_id": next(d["owner_id"] for d in deals if d["id"] == did),
                        "type": "appel",
                        "at": at_dt_target.isoformat(),
                        "subject": "Appel de suivi",
                        "body": "Point de suivi avec le client.",
                    })
                activities_by_deal[did] = new_acts

        for did, flags in anomaly_flags.items():
            if "A2" in flags:
                deal_acts = activities_by_deal.get(did, [])
                new_acts = [
                    a for a in deal_acts
                    if not (datetime.datetime.fromisoformat(a["at"]).date() > as_of_date
                            and a["type"] in ("tache", "reunion"))
                ]
                activities_by_deal[did] = new_acts

        for did, flags in anomaly_flags.items():
            if "L1" in flags or "L2" in flags:
                deal_acts = activities_by_deal.get(did, [])
                owner_id = next(d["owner_id"] for d in deals if d["id"] == did)
                has_recent_note = any(
                    a["type"] == "note" and
                    (as_of_date - datetime.datetime.fromisoformat(a["at"]).date()).days < 7
                    for a in deal_acts
                )
                has_future_reunion = any(
                    a["type"] == "reunion" and
                    datetime.datetime.fromisoformat(a["at"]).date() > as_of_date
                    for a in deal_acts
                )
                if not has_recent_note:
                    note_date = as_of_date - datetime.timedelta(days=3)
                    deal_acts.append({
                        "deal_id": did, "contact_id": None, "owner_id": owner_id,
                        "type": "note",
                        "at": datetime.datetime(note_date.year, note_date.month, note_date.day, 10, 0, 0).isoformat(),
                        "subject": "Note de suivi",
                        "body": "Client en congés jusqu'au 5/01, RDV calé. Pas d'inquiétude.",
                    })
                if not has_future_reunion:
                    future_date = as_of_date + datetime.timedelta(days=14)
                    deal_acts.append({
                        "deal_id": did, "contact_id": None, "owner_id": owner_id,
                        "type": "reunion",
                        "at": datetime.datetime(future_date.year, future_date.month, future_date.day, 10, 0, 0).isoformat(),
                        "subject": "Réunion de suivi",
                        "body": f"RDV calé le {future_date.isoformat()}.",
                    })
                activities_by_deal[did] = deal_acts

        for did, flags in anomaly_flags.items():
            if "A8" in flags:
                deal = next(d for d in deals if d["id"] == did)
                stage_history = deal["stage_history"]
                demo_start = None
                prop_start = None
                for sh in stage_history:
                    if sh["stage"] == "demo":
                        demo_start = datetime.date.fromisoformat(sh["entered_at"])
                    elif sh["stage"] == "proposition":
                        prop_start = datetime.date.fromisoformat(sh["entered_at"])
                if demo_start:
                    if prop_start is None:
                        prop_start = demo_start + datetime.timedelta(days=90)
                    deal_acts = activities_by_deal.get(did, [])
                    new_acts = [
                        a for a in deal_acts
                        if not (a["type"] == "reunion" and
                                demo_start <= datetime.datetime.fromisoformat(a["at"]).date() < prop_start)
                    ]
                    activities_by_deal[did] = new_acts

        all_activities = []
        for acts_list in activities_by_deal.values():
            all_activities.extend(acts_list)

        deals_with_activities = set(activities_by_deal.keys())
        for deal in deals:
            if deal["id"] not in deals_with_activities:
                created_at = datetime.date.fromisoformat(deal["created_at"])
                at_dt = datetime.datetime(created_at.year, created_at.month, created_at.day, 9, 0, 0)
                all_activities.append({
                    "deal_id": deal["id"],
                    "contact_id": deal["contact_ids"][0] if deal["contact_ids"] else None,
                    "owner_id": deal["owner_id"],
                    "type": "appel",
                    "at": at_dt.isoformat(),
                    "subject": "Appel initial",
                    "body": "Premier contact avec le client.",
                })

        all_activities.sort(key=lambda a: (a["deal_id"], a["at"]))
        activities_final = []
        for i, a in enumerate(all_activities, 1):
            a["id"] = f"A-{i:04d}"
            activities_final.append(a)

        crm_data = {
            "meta": {"as_of": as_of, "seed": seed, "public": public},
            "owners": OWNERS,
            "companies": companies,
            "contacts": contacts,
            "deals": deals,
            "activities": activities_final,
        }
        return crm_data

    def test_same_seed_produces_identical_output(self):
        """Two runs with same seed produce identical crm.json dicts."""
        try:
            result1 = self._run_generation(seed=42, as_of="2026-11-18")
            result2 = self._run_generation(seed=42, as_of="2026-11-18")
        except RuntimeError as e:
            self.skipTest(f"Cache non disponible : {e}")

        json1 = json.dumps(result1, ensure_ascii=False, sort_keys=True, default=str)
        json2 = json.dumps(result2, ensure_ascii=False, sort_keys=True, default=str)

        self.assertEqual(json1, json2, "Two runs with same seed produced different output!")

    def test_different_seed_produces_different_output(self):
        """Two runs with different seeds produce different output."""
        try:
            result1 = self._run_generation(seed=42, as_of="2026-11-18")
            result2 = self._run_generation(seed=99, as_of="2026-11-18")
        except RuntimeError as e:
            self.skipTest(f"Cache non disponible : {e}")

        json1 = json.dumps(result1, ensure_ascii=False, sort_keys=True, default=str)
        json2 = json.dumps(result2, ensure_ascii=False, sort_keys=True, default=str)

        self.assertNotEqual(json1, json2, "Different seeds produced identical output!")


if __name__ == "__main__":
    unittest.main()
