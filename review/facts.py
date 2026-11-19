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
        short_cd = _short_date_fr(close_date.isoformat()) if close_date else ""
        return f"Date de clôture dépassée : {short_cd} (il y a {days} j)"

    if code == "A4":
        # Need last activity days — will be computed later; return placeholder
        # We handle A4 specially in build_facts
        return None  # handled separately

    if code == "A5":
        return f"Montant manquant en {stage_label}"

    if code == "A6":
        close_date = _parse_date(deal.get("close_date"))
        yyyy_mm = (f"{MONTH_ABBR[close_date.month]} {close_date.year}"
                   if close_date else "")
        return f"Clôture prévue en {yyyy_mm} mais étape {stage_label}"

    if code == "A7":
        amt_str = f"{amount:,}".replace(",", " ")
        return f"{amt_str} € en Négociation avec un seul interlocuteur"

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

MONTH_ABBR = {
    1: "janv.", 2: "févr.", 3: "mars", 4: "avr.",
    5: "mai", 6: "juin", 7: "juil.", 8: "août",
    9: "sept.", 10: "oct.", 11: "nov.", 12: "déc.",
}

def _variants_for_int(n):
    """All written forms for integer n (amount, day count, deal count)."""
    variants = [str(n)]
    # Spaced thousands
    if n >= 1000:
        s = f"{n:,}".replace(",", "\u202f")  # narrow non-break space
        variants.append(f"{n:,}".replace(",", " "))  # regular space
        # Add leading digit as standalone (e.g. "9" from "9 500")
        leading = str(n)[0]
        variants.append(leading)
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
        f"{d.day} {MONTH_ABBR[d.month]}",     # 2 oct.
        str(d.day),                            # standalone day number
    ]
    return variants


def _short_date_fr(date_str):
    """Return '6 oct.' style short French date from ISO string."""
    d = _parse_date(date_str)
    if d is None:
        return date_str
    return f"{d.day} {MONTH_ABBR[d.month]}"


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
        deal_acts = acts_by_deal.get(did, [])
        last_best = None
        for a in deal_acts:
            at_dt = _parse_datetime(a.get("at"))
            if at_dt and at_dt.date() <= as_of_date:
                if last_best is None or at_dt > _parse_datetime(last_best["at"]):
                    last_best = a
        if last_best is None:
            return "Aucune activité passée", None, None, None
        last_date = last_best["at"][:10]
        last_type = last_best.get("type", "")
        days_silent = (as_of_date - _parse_date(last_date)).days
        short_last = _short_date_fr(last_date)
        phrase = f"Aucune activité depuis {days_silent} jours (dernière : {short_last}, {last_type})"
        return phrase, days_silent, last_date, last_type

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
                phrase, days_silent, last_date, last_type = a4_phrase(deal)
                if days_silent is not None:
                    all_days.add(days_silent)
                if last_date:
                    all_dates.add(_parse_date(last_date))
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
            "company": company.get("display_name") or company.get("name", ""),
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
               f"mais note du {_short_date_fr(recent_note_date.isoformat())} "
               f"et RDV prévu le {_short_date_fr(future_meeting_date.isoformat())}")
        # Collect numbers from excused deals
        all_days.add(days_in_stage)
        all_dates.add(recent_note_date)
        all_dates.add(future_meeting_date)
        excused.append({
            "deal_id": did,
            "deal_name": deal["name"],
            "company": company.get("display_name") or company.get("name", ""),
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
                allowed.add(tok)  # always add the raw token (e.g. "000" from "35 000 €")
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

    # Add numbers from deal names, company names, and last_activity summaries.
    # Summaries are verbatim snippets of activity bodies; any number in them
    # is a known fact and must appear in allowed_numbers.
    import re as _re
    all_text_sources = []
    for did, entry in deal_entries.items():
        all_text_sources.append(entry["deal_name"])
        all_text_sources.append(entry["company"])
        la = entry.get("last_activity")
        if la:
            all_text_sources.append(la.get("summary", ""))
    for exc in excused:
        all_text_sources.append(exc["deal_name"])
        all_text_sources.append(exc["company"])
    for src in all_text_sources:
        for tok in _re.findall(r'\b\d+\b', src):
            allowed.add(tok)
            n = int(tok)
            for v in _variants_for_days(n):
                allowed.add(v)
            if n >= 1000:
                for v in _variants_for_int(n):
                    allowed.add(v)

    allowed_numbers = sorted(allowed)

    # Build a deal_names lookup: deal_id -> deal_name for all deals
    # (useful for evaluator to identify any deal mentioned in a review)
    all_deal_names = {d["id"]: d["name"] for d in deals}

    # ── patterns (A2) ───────────────────────────────────────────────────────
    LATE_STAGES = {"proposition", "negociation"}

    # by_code: count of flagged deals per anomaly code
    by_code = {}
    for did, codes in flags_by_deal.items():
        for code in codes:
            by_code[code] = by_code.get(code, 0) + 1

    # by_owner: per-owner stats for owners with flagged deals
    patterns_by_owner = {}
    for ow in by_owner:
        oid = ow["owner_id"]
        flagged_amt = sum(e["amount"] for e in ow["flagged"])
        patterns_by_owner[oid] = {
            "name": ow["owner_name"],
            "flagged": len(ow["flagged"]),
            "flagged_amount": flagged_amt,
        }

    # multi_anomaly_deals: deals with >= 2 anomaly codes
    multi_anomaly_deals = sum(1 for codes in flags_by_deal.values() if len(codes) >= 2)

    # a2_in_late_stages: A2 deals in proposition or negociation
    a2_in_late_stages = sum(
        1 for did, codes in flags_by_deal.items()
        if "A2" in codes and deals_by_id[did].get("stage") in LATE_STAGES
    )

    # a3_overdue_days_avg: average days overdue across all A3 deals
    a3_days = []
    for did, codes in flags_by_deal.items():
        if "A3" in codes:
            close_date = _parse_date(deals_by_id[did].get("close_date"))
            if close_date:
                a3_days.append((as_of_date - close_date).days)
    a3_overdue_days_avg = int(sum(a3_days) / len(a3_days)) if a3_days else 0

    # a5_a7_combined: deals that have BOTH A5 and A7
    a5_a7_combined = sum(
        1 for codes in flags_by_deal.values()
        if "A5" in codes and "A7" in codes
    )

    # contract_mention_no_amount: deals in proposition/negociation with amount=0 or None
    # AND last_activity summary contains "contrat" or "devis"
    contract_mention_no_amount = []
    for did, codes in flags_by_deal.items():
        deal = deals_by_id[did]
        if deal.get("stage") not in LATE_STAGES:
            continue
        amt = deal.get("amount") or 0
        if amt != 0:
            continue
        la = last_activity(did)
        if la:
            summary_lower = (la.get("summary") or "").lower()
            if "contrat" in summary_lower or "devis" in summary_lower:
                entry = deal_entries.get(did, {})
                contract_mention_no_amount.append({
                    "deal_id": did,
                    "deal_name": deal.get("name", ""),
                    "stage": STAGE_LABEL.get(deal.get("stage", ""), deal.get("stage", "")),
                    "amount": amt,
                })

    # ── 1:1 questions ───────────────────────────────────────────────────────
    # Build factual questions for each AE, one per unique owner, in priority order.
    # Questions use only facts already in allowed_numbers.
    one_on_one = []
    seen_1on1_owners = set()
    for did in all_flagged_sorted:
        if len(one_on_one) >= 3:
            break
        deal = deals_by_id[did]
        oid = deal.get("owner_id")
        if oid in seen_1on1_owners:
            continue
        owner_name = owners_by_id.get(oid, {}).get("name", oid)
        codes = flags_by_deal[did]
        entry = deal_entries[did]
        amount = deal.get("amount") or 0
        stage_label = STAGE_LABEL.get(deal.get("stage", ""), deal.get("stage", ""))
        amt_str = f"{amount:,}".replace(",", "\u202f") + "\u202f€" if amount else "montant manquant"

        q = None
        if "A4" in codes:
            _, days_silent, _, _ = a4_phrase(deal)
            if days_silent:
                q = (f"{owner_name} — {entry['deal_name']} ({entry['company']}, {stage_label}) : "
                     f"aucune activité depuis {days_silent} j. Quel est l'état d'avancement ?")
        elif "A7" in codes:
            q = (f"{owner_name} — {entry['deal_name']} ({entry['company']}, {stage_label}) : "
                 f"{amt_str} avec un seul interlocuteur. D'autres contacts ont-ils été approchés ?")
        elif "A3" in codes:
            close_date = _parse_date(deal.get("close_date"))
            if close_date:
                days_over = (as_of_date - close_date).days
                q = (f"{owner_name} — {entry['deal_name']} ({entry['company']}, {stage_label}) : "
                     f"date de clôture dépassée depuis {days_over} j. La date est-elle encore réaliste ?")
        elif "A2" in codes:
            q = (f"{owner_name} — {entry['deal_name']} ({entry['company']}, {stage_label}) : "
                 f"aucune tâche planifiée. Quelle est la prochaine étape prévue ?")
        elif "A1" in codes:
            stage_entered = _parse_date(deal.get("stage_entered_at"))
            days_in = (as_of_date - stage_entered).days if stage_entered else 0
            normal = STAGE_NORMAL_DAYS.get(deal.get("stage"), 0)
            q = (f"{owner_name} — {entry['deal_name']} ({entry['company']}, {stage_label}) : "
                 f"en {stage_label} depuis {days_in} j (norme : {normal} j). Ce dossier avance-t-il ?")
        else:
            q = (f"{owner_name} — {entry['deal_name']} ({entry['company']}, {stage_label}) : "
                 f"signalement à {amt_str}. Quel est le statut actuel ?")

        if q:
            one_on_one.append({"owner_name": owner_name, "question": q, "deal_id": did})
            seen_1on1_owners.add(oid)

    # concentrations_ae: AEs with more than one of the top-3 priority deals
    priority_owner_counts = {}
    for did in priorities:
        oid = deals_by_id[did].get("owner_id")
        priority_owner_counts[oid] = priority_owner_counts.get(oid, 0) + 1
    concentrations_ae = {
        owners_by_id.get(oid, {}).get("name", oid): cnt
        for oid, cnt in priority_owner_counts.items()
        if cnt > 1
    }

    patterns = {
        "by_code": by_code,
        "by_owner": patterns_by_owner,
        "multi_anomaly_deals": multi_anomaly_deals,
        "a2_in_late_stages": a2_in_late_stages,
        "a3_overdue_days_avg": a3_overdue_days_avg,
        "a5_a7_combined": a5_a7_combined,
        "contract_mention_no_amount": contract_mention_no_amount,
        "concentrations_ae": concentrations_ae,
    }

    # Add pattern numbers to allowed_numbers
    for n in [multi_anomaly_deals, a2_in_late_stages, a3_overdue_days_avg, a5_a7_combined]:
        for v in _variants_for_days(n):
            allowed.add(v)
    for code, cnt in by_code.items():
        for v in _variants_for_days(cnt):
            allowed.add(v)
    for oid, stats in patterns_by_owner.items():
        for v in _variants_for_days(stats["flagged"]):
            allowed.add(v)
        for v in _variants_for_int(stats["flagged_amount"]):
            allowed.add(v)

    # Scan 1:1 questions for any numbers they introduce
    import re as _re2
    for item in one_on_one:
        q = item["question"]
        for tok in _re2.findall(r'\b\d+\b', q):
            allowed.add(tok)
            n = int(tok)
            for v in _variants_for_days(n):
                allowed.add(v)
            if n >= 1000:
                for v in _variants_for_int(n):
                    allowed.add(v)

    allowed_numbers = sorted(allowed)

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
        "one_on_one": one_on_one,
        "by_owner": by_owner,
        "excused": excused,
        "patterns": patterns,
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
