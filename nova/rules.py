"""
Detection rules for Atelier Nova CRM anomalies.
Each rule returns a list of (deal_id, code, description) tuples.

Exception for A1: a deal is NOT stagnant if it has BOTH:
  - a note with at < 7 days before as_of
  - a future meeting (at > as_of)
"""

import datetime


def _parse_date(s):
    if not s:
        return None
    return datetime.date.fromisoformat(s[:10])


def _parse_datetime(s):
    if not s:
        return None
    return datetime.datetime.fromisoformat(s)


def get_activities_by_deal(activities):
    """Index activities by deal_id."""
    by_deal = {}
    for a in activities:
        did = a["deal_id"]
        if did not in by_deal:
            by_deal[did] = []
        by_deal[did].append(a)
    return by_deal


def rule_A1_stagnant(deals, activities_by_deal, as_of):
    """
    A1: days in stage > 2× normal duration.
    Exception: skip if deal has a note < 7 days old AND a future meeting.
    """
    from .pipeline import STAGE_META

    results = []
    as_of_date = _parse_date(as_of)

    for deal in deals:
        if deal["status"] != "open":
            continue
        stage = deal["stage"]
        meta = STAGE_META.get(stage)
        if meta is None or meta["normal_days"] is None:
            continue

        normal_days = meta["normal_days"]
        stage_entered = _parse_date(deal.get("stage_entered_at"))
        if stage_entered is None:
            continue

        days_in_stage = (as_of_date - stage_entered).days
        if days_in_stage <= 2 * normal_days:
            continue

        # Check exception: recent note AND future meeting
        did = deal["id"]
        deal_acts = activities_by_deal.get(did, [])

        has_recent_note = False
        has_future_meeting = False
        for a in deal_acts:
            at_dt = _parse_datetime(a.get("at"))
            if at_dt is None:
                continue
            at_date = at_dt.date()
            if a["type"] == "note" and (as_of_date - at_date).days < 7:
                has_recent_note = True
            if a["type"] == "reunion" and at_date > as_of_date:
                has_future_meeting = True

        if has_recent_note and has_future_meeting:
            continue  # Leurre exception applies

        stage_label = meta["label"]
        results.append((
            did,
            "A1",
            f"En {stage_label} depuis {days_in_stage} j (normale {normal_days} j)"
        ))

    return results


def rule_A2_no_next_step(deals, activities_by_deal, as_of):
    """
    A2: no future task (tache) or future meeting (reunion) for open deal.
    """
    results = []
    as_of_date = _parse_date(as_of)

    for deal in deals:
        if deal["status"] != "open":
            continue
        did = deal["id"]
        deal_acts = activities_by_deal.get(did, [])

        has_next_step = False
        for a in deal_acts:
            if a["type"] not in ("tache", "reunion"):
                continue
            at_dt = _parse_datetime(a.get("at"))
            if at_dt is None:
                continue
            if at_dt.date() > as_of_date:
                has_next_step = True
                break

        if not has_next_step:
            results.append((did, "A2", "Aucune tâche ni réunion à venir"))

    return results


def rule_A3_close_date_passed(deals, as_of):
    """
    A3: close_date < as_of for open deals.
    """
    results = []
    as_of_date = _parse_date(as_of)

    for deal in deals:
        if deal["status"] != "open":
            continue
        close_date = _parse_date(deal.get("close_date"))
        if close_date is None:
            continue
        if close_date < as_of_date:
            days_past = (as_of_date - close_date).days
            results.append((
                deal["id"],
                "A3",
                f"Date de clôture dépassée : {close_date.isoformat()} (il y a {days_past} j)"
            ))

    return results


def rule_A4_big_silent_deal(deals, activities_by_deal, as_of):
    """
    A4: amount >= 25000 AND last past activity > 21 days ago.
    """
    results = []
    as_of_date = _parse_date(as_of)

    for deal in deals:
        if deal["status"] != "open":
            continue
        amount = deal.get("amount")
        if amount is None or amount < 25000:
            continue

        did = deal["id"]
        deal_acts = activities_by_deal.get(did, [])

        # Find last past activity date
        last_past = None
        for a in deal_acts:
            at_dt = _parse_datetime(a.get("at"))
            if at_dt is None:
                continue
            if at_dt.date() <= as_of_date:
                if last_past is None or at_dt.date() > last_past:
                    last_past = at_dt.date()

        if last_past is None:
            # No past activity at all → definitely silent
            results.append((did, "A4", f"Deal de {amount}€ sans aucune activité passée"))
            continue

        days_silent = (as_of_date - last_past).days
        if days_silent > 21:
            results.append((
                did,
                "A4",
                f"Deal de {amount}€ sans activité depuis {days_silent} j"
            ))

    return results


def rule_A5_missing_amount(deals, as_of):
    """
    A5: amount null/0 from proposition stage onward.
    """
    from .pipeline import STAGES
    proposition_idx = STAGES.index("proposition")
    late_stages = set(STAGES[proposition_idx:]) | {"gagne"}

    results = []

    for deal in deals:
        if deal["status"] != "open":
            continue
        stage = deal.get("stage")
        if stage not in late_stages:
            continue
        amount = deal.get("amount")
        if amount is None or amount == 0:
            from .pipeline import STAGE_META
            label = STAGE_META.get(stage, {}).get("label", stage)
            results.append((deal["id"], "A5", f"Montant manquant en {label}"))

    return results


def rule_A6_unrealistic_forecast(deals, as_of):
    """
    A6: close_date in as_of month but stage is decouverte or qualification.
    """
    results = []
    as_of_date = _parse_date(as_of)

    for deal in deals:
        if deal["status"] != "open":
            continue
        stage = deal.get("stage")
        if stage not in ("decouverte", "qualification"):
            continue
        close_date = _parse_date(deal.get("close_date"))
        if close_date is None:
            continue
        # Check if close_date is in same month as as_of AND still in the future
        # (if past, A3 is the appropriate rule)
        if (close_date >= as_of_date
                and close_date.year == as_of_date.year
                and close_date.month == as_of_date.month):
            from .pipeline import STAGE_META
            label = STAGE_META.get(stage, {}).get("label", stage)
            results.append((
                deal["id"],
                "A6",
                f"Clôture en {as_of_date.strftime('%Y-%m')} mais étape {label}"
            ))

    return results


def rule_A7_single_contact(deals, as_of):
    """
    A7: amount >= 20000, stage negociation, only 1 contact.
    """
    results = []

    for deal in deals:
        if deal["status"] != "open":
            continue
        if deal.get("stage") != "negociation":
            continue
        amount = deal.get("amount")
        if amount is None or amount < 20000:
            continue
        contact_ids = deal.get("contact_ids", [])
        if len(contact_ids) == 1:
            results.append((
                deal["id"],
                "A7",
                f"Deal {amount}€ en Négociation avec 1 seul interlocuteur"
            ))

    return results


def rule_A8_stage_skip(deals, activities_by_deal, as_of):
    """
    A8: stage negociation, no meeting during the demo stage period.
    Demo period = entered demo until entered proposition.
    """
    results = []

    for deal in deals:
        if deal["status"] != "open":
            continue
        if deal.get("stage") != "negociation":
            continue

        stage_history = deal.get("stage_history", [])

        # Find demo start and proposition start
        demo_start = None
        prop_start = None
        for sh in stage_history:
            if sh["stage"] == "demo":
                demo_start = _parse_date(sh["entered_at"])
            elif sh["stage"] == "proposition":
                prop_start = _parse_date(sh["entered_at"])

        if demo_start is None:
            # No demo stage at all in history
            results.append((deal["id"], "A8", "En Négociation sans réunion de démo dans l'historique"))
            continue

        if prop_start is None:
            # demo stage but never reached proposition... unusual for negociation deal
            # Use demo_start + 90 days as upper bound
            prop_start = demo_start + datetime.timedelta(days=90)

        # Check if any meeting happened during demo period
        did = deal["id"]
        deal_acts = activities_by_deal.get(did, [])

        has_demo_meeting = False
        for a in deal_acts:
            if a["type"] != "reunion":
                continue
            at_dt = _parse_datetime(a.get("at"))
            if at_dt is None:
                continue
            at_date = at_dt.date()
            if demo_start <= at_date < prop_start:
                has_demo_meeting = True
                break

        if not has_demo_meeting:
            results.append((
                deal["id"],
                "A8",
                "En Négociation sans réunion de démo dans l'historique"
            ))

    return results


def rule_A9_duplicate(deals, as_of):
    """
    A9: same company, 2 open deals with near-identical names.
    Uses simple prefix matching: if one name starts with the other.
    """
    results = []

    open_deals = [d for d in deals if d["status"] == "open"]

    # Group by company_id
    by_company = {}
    for d in open_deals:
        cid = d["company_id"]
        if cid not in by_company:
            by_company[cid] = []
        by_company[cid].append(d)

    seen_pairs = set()

    for cid, company_deals in by_company.items():
        if len(company_deals) < 2:
            continue
        # Check all pairs
        for i, d1 in enumerate(company_deals):
            for j, d2 in enumerate(company_deals):
                if i >= j:
                    continue
                pair_key = (min(d1["id"], d2["id"]), max(d1["id"], d2["id"]))
                if pair_key in seen_pairs:
                    continue
                n1 = d1["name"].lower().strip()
                n2 = d2["name"].lower().strip()
                if _names_similar(n1, n2):
                    seen_pairs.add(pair_key)
                    for d in [d1, d2]:
                        results.append((
                            d["id"],
                            "A9",
                            f"Doublon : même entreprise {cid}, noms quasi identiques"
                        ))

    return results


def _names_similar(n1, n2):
    """
    Check if two deal names are near-identical (same product, different formatting).
    Strategy: normalize both names into a set of 5-char word stems (words ≥ 5 chars,
    lowercased, accents stripped).  Two names are similar if they share ≥ 3 stems.
    This threshold is high enough to avoid false positives when two clean deals share
    the same company-name fragment + the same product theme (at most 2 stems in common).
    """
    import re

    def stems(s):
        s = s.lower()
        for a, b in [('é','e'),('è','e'),('ê','e'),('ë','e'),
                     ('à','a'),('â','a'),('ä','a'),
                     ('î','i'),('ï','i'),
                     ('ô','o'),('ö','o'),
                     ('ù','u'),('û','u'),('ü','u'),
                     ('ç','c')]:
            s = s.replace(a, b)
        return {w[:5] for w in re.findall(r'[a-z]{5,}', s)}

    return len(stems(n1) & stems(n2)) >= 3


def run_all_rules(crm_data, as_of=None):
    """
    Run all 9 rules on crm_data dict.
    Returns list of (deal_id, code, description) tuples.
    """
    if as_of is None:
        as_of = crm_data["meta"]["as_of"]

    deals = crm_data["deals"]
    activities = crm_data["activities"]
    activities_by_deal = get_activities_by_deal(activities)

    results = []
    results.extend(rule_A1_stagnant(deals, activities_by_deal, as_of))
    results.extend(rule_A2_no_next_step(deals, activities_by_deal, as_of))
    results.extend(rule_A3_close_date_passed(deals, as_of))
    results.extend(rule_A4_big_silent_deal(deals, activities_by_deal, as_of))
    results.extend(rule_A5_missing_amount(deals, as_of))
    results.extend(rule_A6_unrealistic_forecast(deals, as_of))
    results.extend(rule_A7_single_contact(deals, as_of))
    results.extend(rule_A8_stage_skip(deals, activities_by_deal, as_of))
    results.extend(rule_A9_duplicate(deals, as_of))

    return results
