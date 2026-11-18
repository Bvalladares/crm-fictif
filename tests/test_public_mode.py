"""
Test public mode:
- With --public flag, no SIREN from real cache appears in companies
- No company name from real cache appears
- All SIRENs start with "999"
"""

import datetime
import json
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

CACHE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "companies_cache.json")


def load_cache():
    with open(CACHE_PATH, encoding="utf-8") as f:
        return json.load(f)


def run_public_generation(seed=42, as_of="2026-11-18"):
    """Run generation with --public flag and return crm_data."""
    from nova.companies import select_companies, make_public_companies
    from nova.people import gen_contacts
    from nova.deals import gen_deals
    from nova.anomalies import plant_anomalies
    from nova.pipeline import OWNERS

    rng = random.Random(seed)
    as_of_date = datetime.date.fromisoformat(as_of)

    companies_raw = select_companies(rng, target=220)
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

    return {
        "meta": {"as_of": as_of, "seed": seed, "public": True},
        "owners": OWNERS,
        "companies": companies,
        "contacts": contacts,
        "deals": deals,
    }


class TestPublicMode(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        try:
            cls.cache = load_cache()
        except (FileNotFoundError, KeyError, json.JSONDecodeError):
            cls.cache = {"companies": []}
        try:
            cls.public_crm = run_public_generation()
        except RuntimeError as e:
            raise unittest.SkipTest(f"Cache non disponible : {e}")
        cls.cache_sirens = {c["siren"] for c in cls.cache["companies"]}
        cls.cache_names = {c["nom"].lower() for c in cls.cache["companies"]}

    def test_all_sirens_start_with_999(self):
        """All company SIRENs in public mode must start with '999'."""
        errors = []
        for c in self.public_crm["companies"]:
            if not c["siren"].startswith("999"):
                errors.append(f"Company {c['id']} has SIREN {c['siren']} (not 999...)")
        self.assertEqual(errors, [], "\n".join(errors[:10]))

    def test_no_real_siren_in_public_mode(self):
        """No SIREN from real cache must appear in public mode companies."""
        errors = []
        for c in self.public_crm["companies"]:
            if c["siren"] in self.cache_sirens:
                errors.append(f"Company {c['id']} SIREN {c['siren']} from real cache")
        self.assertEqual(errors, [], "\n".join(errors[:10]))

    def test_no_real_company_name_in_public_mode(self):
        """No company name from real cache must appear in public mode."""
        errors = []
        for c in self.public_crm["companies"]:
            name = c["name"].lower()
            if name in self.cache_names:
                errors.append(f"Company {c['id']} name '{c['name']}' from real cache")
        self.assertEqual(errors, [], "\n".join(errors[:10]))

    def test_public_flag_in_meta(self):
        """Meta must have public=True when generated in public mode."""
        self.assertTrue(self.public_crm["meta"]["public"])


if __name__ == "__main__":
    unittest.main()
