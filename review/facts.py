"""
review/facts.py — Generate facts.json from crm.json + nova rules.

CLI: python3 -m review.facts [--crm out/crm.json] [--out out/facts.json]
"""

import argparse
import datetime
import json
import sys
import os


# ── helpers ────────────────────────────────────────────────────────────────

def _parse_date(s):
    if not s:
        return None
    return datetime.date.fromisoformat(s[:10])

def _parse_datetime(s):
    if not s:
        return None
    return datetime.datetime.fromisoformat(s)


STAGE_LABEL = {
    "decouverte":    "Découverte",
    "qualification": "Qualification",
    "demo":          "Démo",
    "proposition":   "Proposition envoyée",
    "negociation":   "Négociation",
    "gagne":         "Gagné",
    "perdu":         "Perdu",
}

STAGE_NORMAL_DAYS = {
    "decouverte":    14,
    "qualification": 14,
    "demo":          21,
    "proposition":   21,
    "negociation":   30,
}

RULE_WEIGHTS = {
    "A4": 3, "A7": 3,
    "A1": 2, "A2": 2, "A3": 2,
}

def _weight(code):
    return RULE_WEIGHTS.get(code, 1)

def _score(amount, codes):
    return (amount or 0) * sum(_weight(c) for c in codes)


# ── facts phrase builders ───────────────────────────────────────────────────

def _build_fact_phrase(code, deal, as_of_date):
    """Build a French factual phrase for the given rule code."""
    stage = deal.get("stage", "")
    stage_label = STAGE_LABEL.get(stage, stage)
    amount = deal.get("amount") or 0

    if code == "A1":
        normal = STAGE_NORMAL_DAYS.get(stage)
        stage_entered = _parse_date(deal.get("stage_entered_at"))
        days = (as_of_date - stage_entered).days if stage_entered else 0
        return f"En {stage_label} depuis {days} jours (durée normale {normal} jours)"

    if code == "A2":
        return "Aucune tâche ni réunion à venir"

    if code == "A3":
        close_date = _parse_date(deal.get("close_date"))
        days = (as_of_date - close_date).days if close_date else 0
        return f"Date de clôture dépassée : {close_date.isoformat()} (il y a {days} j)"

    if code == "A4":
        # Need last activity days — will be computed later; return placeholder
        # We handle A4 specially in build_facts
        return None  # handled separately

    if code == "A5":
        return f"Montant manquant en {stage_label}"

    if code == "A6":
        close_date = _parse_date(deal.get("close_date"))
        yyyy_mm = close_date.strftime("%Y-%m") if close_date else ""
        return f"Clôture en {yyyy_mm} mais étape {stage_label}"

    if code == "A7":
        return f"Deal {amount} € en Négociation avec 1 seul interlocuteur"

    if code == "A8":
        return "En Négociation sans réunion de démo dans l'historique"

    if code == "A9":
        return "Doublon : même entreprise, noms quasi identiques"

    return code


# ── allowed_numbers helpers ─────────────────────────────────────────────────

MONTH_NAMES = {
    1: "janvier", 2: "février", 3: "mars", 4: "avril",
    5: "mai", 6: "juin", 7: "juillet", 8: "août",
    9: "septembre", 10: "octobre", 11: "novembre", 12: "décembre",
}

def _variants_for_int(n):
    """All written forms for integer n (amount, day count, deal count)."""
    variants = [str(n)]
    # Spaced thousands
    if n >= 1000:
        s = f"{n:,}".replace(",", "\u202f")  # narrow non-break space
        variants.append(f"{n:,}".replace(",", " "))  # regular space
    # Euro variants for amounts
    if n >= 1000:
        variants.append(f"{n:,}".replace(",", " ") + " €")
    if n % 1000 == 0:
        k = n // 1000
        variants.append(f"{k} k€")
    return variants

def _variants_for_date(d):
    """All written forms for a date."""
    if isinstance(d, str):
        d = _parse_date(d)
    if d is None:
        return []
    variants = [
        d.isoformat(),                        # 2026-10-02
        f"{d.day}/{d.month}",                 # 2/10
        f"{d.day} {MONTH_NAMES[d.month]}",    # 2 octobre
        f"{d.day:02d}/{d.month:02d}/{d.year}", # 02/10/2026
    ]
    return variants

def _variants_for_days(n):
    """All written forms for a day count."""
    return [str(n), f"{n} j", f"{n} jours"]


# ── main build function ─────────────────────────────────────────────────────

def build_facts(crm_data):
    as_of_str = crm_data["meta"]["as_of"]
    as_of_date = _parse_date(as_of_str)

    deals = crm_data["deals"]
    activities = crm_data["activities"]
    owners_list = crm_data["owners"]

    # Index data
    owners_by_id = {o["id"]: o for o in owners_list}
    deals_by_id = {d["id"]: d for d in deals}
    companies_by_id = {c["id"]: c for c in crm_data["companies"]}

    # Activities by deal
    acts_by_deal = {}
    for a in activities:
        did = a["deal_id"]
        if did not in acts_by_deal:
            acts_by_deal[did] = []
        acts_by_deal[did].append(a)

    # Run rules
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from nova.rules import run_all_rules
    raw_flags = run_all_rules(crm_data, as_of=as_of_str)

    # Group flags by deal_id
    flags_by_deal = {}  # deal_id -> list of codes
    for did, code, desc in raw_flags:
        if did not in flags_by_deal:
            flags_by_deal[did] = []
        flags_by_deal[did].append(code)

    # Build A4 silent days per deal (needed for fact phrase)
    def a4_phrase(deal):
        did = deal["id"]
        amount = deal.get("amount") or 0
        deal_acts = acts_by_deal.get(did, [])
        last_past = None
        for a in deal_acts:
            at_dt = _parse_datetime(a.get("at"))
            if at_dt and at_dt.date() <= as_of_date:
                if last_past is None or at_dt.date() > last_past:
                    last_past = at_dt.date()
        if last_past is None:
            return f"Deal de {amount} € sans aucune activité passée", None
        days_silent = (as_of_date - last_past).days
        return f"Deal de {amount} € sans activité depuis {days_silent} jours", days_silent

    # Last activity per deal (past activities only)
    def last_activity(deal_id):
        deal_acts = acts_by_deal.get(deal_id, [])
        best = None
        for a in deal_acts:
            at_dt = _parse_datetime(a.get("at"))
            if at_dt and at_dt.date() <= as_of_date:
                if best is None or at_dt > _parse_datetime(best["at"]):
                    best = a
        if best is None:
            return None
        body = (best.get("body") or "").replace("\n", " ").replace("\r", " ")
        return {
            "date": best["at"][:10],
            "type": best.get("type", ""),
            "summary": body[:80],
        }

    # Build flagged deal entries
    # Collect all numbers for allowed_numbers as we go
    all_amounts = set()
    all_days = set()
    all_dates = set()

    # Totals
    open_deals_list = [d for d in deals if d["status"] == "open"]
    open_deals_count = len(open_deals_list)
    open_amount_total = sum(d.get("amount") or 0 for d in open_deals_list)
    all_amounts.add(open_amount_total)

    flagged_deal_ids = set(flags_by_deal.keys())
    flagged_deals_count = len(flagged_deal_ids)
    flagged_amount_total = sum(deals_by_id[did].get("amount") or 0 for did in flagged_deal_ids)
    all_amounts.add(flagged_amount_total)

    # Add totals counts
    all_days.add(open_deals_count)
    all_days.add(flagged_deals_count)

    # Build deal entries with facts
    deal_entries = {}  # deal_id -> entry dict

    for did, codes in flags_by_deal.items():
        deal = deals_by_id[did]
        company = companies_by_id.get(deal.get("company_id"), {})
        amount = deal.get("amount") or 0
        all_amounts.add(amount)

        facts_phrases = []
        for code in codes:
            if code == "A4":
                phrase, days_silent = a4_phrase(deal)
                if days_silent is not None:
                    all_days.add(days_silent)
                facts_phrases.append(phrase)
            else:
                phrase = _build_fact_phrase(code, deal, as_of_date)
                if phrase:
                    facts_phrases.append(phrase)
                # Collect numbers from phrase
                if code == "A1":
                    stage_entered = _parse_date(deal.get("stage_entered_at"))
                    if stage_entered:
                        days = (as_of_date - stage_entered).days
                        all_days.add(days)
                        normal = STAGE_NORMAL_DAYS.get(deal.get("stage"))
                        if normal:
                            all_days.add(normal)
                elif code == "A3":
                    close_date = _parse_date(deal.get("close_date"))
                    if close_date:
                        days = (as_of_date - close_date).days
                        all_days.add(days)
                        all_dates.add(close_date)

        la = last_activity(did)
        if la:
            all_dates.add(_parse_date(la["date"]))

        entry = {
            "deal_id": did,
            "deal_name": deal["name"],
            "company": company.get("name", ""),
            "stage": STAGE_LABEL.get(deal.get("stage", ""), deal.get("stage", "")),
            "amount": amount,
            "codes": codes,
            "facts": facts_phrases,
            "last_activity": la,
        }
        deal_entries[did] = entry

    # Compute scores and priorities
    def deal_score(did):
        codes = flags_by_deal[did]
        amount = deals_by_id[did].get("amount") or 0
        return _score(amount, codes)

    all_flagged_sorted = sorted(
        flagged_deal_ids,
        key=lambda did: (-deal_score(did), -(deals_by_id[did].get("amount") or 0), did)
    )
    priorities = all_flagged_sorted[:3]

    # Group by owner
    owner_flagged = {}  # owner_id -> [deal_ids]
    for did in flagged_deal_ids:
        oid = deals_by_id[did].get("owner_id")
        if oid not in owner_flagged:
            owner_flagged[oid] = []
        owner_flagged[oid].append(did)

    by_owner = []
    for oid in sorted(owner_flagged.keys()):
        owner_info = owners_by_id.get(oid, {})
        owner_open = [d for d in open_deals_list if d.get("owner_id") == oid]
        owner_open_amount = sum(d.get("amount") or 0 for d in owner_open)
        # Sort flagged by score desc
        flagged_sorted = sorted(
            owner_flagged[oid],
            key=lambda did: (-deal_score(did), -(deals_by_id[did].get("amount") or 0), did)
        )
        by_owner.append({
            "owner_id": oid,
            "owner_name": owner_info.get("name", oid),
            "open_deals": len(owner_open),
            "open_amount": owner_open_amount,
            "flagged": [deal_entries[did] for did in flagged_sorted],
        })

    # Build excused deals: days_in_stage > 2× normal but NOT flagged by A1
    # because they have recent note AND future meeting
    excused = []
    from nova.rules import get_activities_by_deal
    acts_idx = get_activities_by_deal(activities)

    for deal in open_deals_list:
        stage = deal.get("stage")
        normal = STAGE_NORMAL_DAYS.get(stage)
        if normal is None:
            continue
        stage_entered = _parse_date(deal.get("stage_entered_at"))
        if stage_entered is None:
            continue
        days_in_stage = (as_of_date - stage_entered).days
        if days_in_stage <= 2 * normal:
            continue
        did = deal["id"]
        # Must NOT be flagged by A1
        if did in flags_by_deal and "A1" in flags_by_deal[did]:
            continue
        # Must have recent note AND future meeting
        deal_acts = acts_idx.get(did, [])
        recent_note_date = None
        future_meeting_date = None
        for a in deal_acts:
            at_dt = _parse_datetime(a.get("at"))
            if at_dt is None:
                continue
            at_date = at_dt.date()
            if a["type"] == "note" and (as_of_date - at_date).days < 7:
                if recent_note_date is None or at_date > recent_note_date:
                    recent_note_date = at_date
            if a["type"] == "reunion" and at_date > as_of_date:
                if future_meeting_date is None or at_date < future_meeting_date:
                    future_meeting_date = at_date
        if recent_note_date is None or future_meeting_date is None:
            continue
        # Build excused entry
        stage_label = STAGE_LABEL.get(stage, stage)
        company = companies_by_id.get(deal.get("company_id"), {})
        owner_info = owners_by_id.get(deal.get("owner_id"), {})
        why = (f"En {stage_label} depuis {days_in_stage} jours, "
               f"mais note du {recent_note_date.isoformat()} "
               f"et RDV prévu le {future_meeting_date.isoformat()}")
        # Collect numbers from excused deals
        all_days.add(days_in_stage)
        all_dates.add(recent_note_date)
        all_dates.add(future_meeting_date)
        excused.append({
            "deal_id": did,
            "deal_name": deal["name"],
            "company": company.get("name", ""),
            "owner_id": deal.get("owner_id"),
            "owner_name": owner_info.get("name", deal.get("owner_id", "")),
            "codes": ["A1"],
            "why": why,
        })

    # Build allowed_numbers
    allowed = set()

    # As_of date
    for v in _variants_for_date(as_of_date):
        allowed.add(v)

    # Totals counts
    for n in [open_deals_count, flagged_deals_count]:
        for v in _variants_for_days(n):
            allowed.add(v)

    # All amounts
    for n in all_amounts:
        if n == 0:
            allowed.add("0")
            continue
        for v in _variants_for_int(n):
            allowed.add(v)

    # All day counts
    for n in all_days:
        if isinstance(n, int):
            for v in _variants_for_days(n):
                allowed.add(v)

    # All dates
    for d in all_dates:
        if d is not None:
            for v in _variants_for_date(d):
                allowed.add(v)

    # Also collect from facts phrases themselves (all numeric tokens)
    import re
    for did, entry in deal_entries.items():
        for phrase in entry["facts"]:
            for tok in re.findall(r'\b\d+\b', phrase):
                n = int(tok)
                # day counts
                for v in _variants_for_days(n):
                    allowed.add(v)
                # amounts (if large enough to have k€)
                if n >= 1000:
                    for v in _variants_for_int(n):
                        allowed.add(v)
                else:
                    allowed.add(str(n))
        # Amount
        amt = entry["amount"]
        if amt:
            for v in _variants_for_int(amt):
                allowed.add(v)

    # Also add owner deal counts from by_owner
    for ow in by_owner:
        n = ow["open_deals"]
        for v in _variants_for_days(n):
            allowed.add(v)
        amt = ow["open_amount"]
        for v in _variants_for_int(amt):
            allowed.add(v)

    # Add numbers from deal names and company names (numbers in proper names are ok)
    import re as _re
    all_text_sources = []
    for did, entry in deal_entries.items():
        all_text_sources.append(entry["deal_name"])
        all_text_sources.append(entry["company"])
    for exc in excused:
        all_text_sources.append(exc["deal_name"])
        all_text_sources.append(exc["company"])
    for src in all_text_sources:
        for tok in _re.findall(r'\b\d+\b', src):
            allowed.add(tok)
            # Also day variants in case they appear standalone
            n = int(tok)
            for v in _variants_for_days(n):
                allowed.add(v)

    allowed_numbers = sorted(allowed)

    # Build a deal_names lookup: deal_id -> deal_name for all deals
    # (useful for evaluator to identify any deal mentioned in a review)
    all_deal_names = {d["id"]: d["name"] for d in deals}

    result = {
        "as_of": as_of_str,
        "team": "Atelier Nova",
        "totals": {
            "open_deals": open_deals_count,
            "open_amount": open_amount_total,
            "flagged_deals": flagged_deals_count,
            "flagged_amount": flagged_amount_total,
        },
        "priorities": priorities,
        "by_owner": by_owner,
        "excused": excused,
        "allowed_numbers": allowed_numbers,
        "all_deal_names": all_deal_names,
    }
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--crm", default="out/crm.json")
    parser.add_argument("--out", default="out/facts.json")
    args = parser.parse_args()

    with open(args.crm) as f:
        crm_data = json.load(f)

    facts = build_facts(crm_data)

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(facts, f, ensure_ascii=False, indent=2)

    print(f"Written {args.out}")


if __name__ == "__main__":
    main()
