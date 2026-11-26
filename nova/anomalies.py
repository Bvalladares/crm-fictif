"""
Anomaly and leurre (decoy) planting for Atelier Nova CRM.
All anomalies are planted in OPEN deals only.

Anomaly plan:
- 5 deals with BOTH A1 and A2 (10 rows)
- 3 deals with ONLY A1 (3 rows) → total A1 = 8
- 2 deals with ONLY A2 (2 rows) → total A2 = 7
- 6 deals with A3
- 4 deals with A4
- 3 deals with A5
- 3 deals with A6
- 3 deals with A7
- 2 deals with A8
- 2 deals with A9 (1 pair, same company)
= 30 unique anomaly deals
+ 6 leurres
"""

import datetime
from .pipeline import STAGES, STAGE_META


def plant_anomalies(rng, deals, contacts_by_company, as_of):
    """
    Plant anomalies and leurres into open deals.
    Returns:
      - modified deals list
      - anomaly_flags: dict deal_id -> set of codes
      - truth_rows: list of dicts for truth.csv
    """
    open_deals = [d for d in deals if d["status"] == "open"]
    open_deals_sorted = sorted(open_deals, key=lambda d: d["id"])

    if len(open_deals_sorted) < 36:
        raise ValueError(f"Not enough open deals: {len(open_deals_sorted)}")

    _AE_ANOMALY_WEIGHT = {"ae1": 0.4, "ae2": 1.0, "ae3": 1.0, "ae4": 2.5, "ae5": 1.5}
    pool = list(open_deals_sorted)
    priorities = [rng.expovariate(_AE_ANOMALY_WEIGHT.get(d.get("owner_id", ""), 1.0)) for d in pool]
    pool = [d for _, d in sorted(zip(priorities, pool), key=lambda x: x[0])]

    anomaly_flags = {}  # deal_id -> set of codes
    truth_rows = []

    idx = 0

    def next_deal():
        nonlocal idx
        d = pool[idx]
        idx += 1
        return d

    def add_flag(deal, code):
        did = deal["id"]
        if did not in anomaly_flags:
            anomaly_flags[did] = set()
        anomaly_flags[did].add(code)

    # --- A1+A2 combined: 5 deals ---
    a1a2_deals = [next_deal() for _ in range(5)]
    for d in a1a2_deals:
        add_flag(d, "A1")
        add_flag(d, "A2")

    # --- A1 only: 3 deals ---
    a1_only_deals = [next_deal() for _ in range(3)]
    for d in a1_only_deals:
        add_flag(d, "A1")

    # --- A2 only: 2 deals ---
    a2_only_deals = [next_deal() for _ in range(2)]
    for d in a2_only_deals:
        add_flag(d, "A2")

    # --- A3: 6 deals ---
    a3_deals = [next_deal() for _ in range(6)]
    for d in a3_deals:
        add_flag(d, "A3")

    # --- A4: 4 deals ---
    a4_deals = [next_deal() for _ in range(4)]
    for d in a4_deals:
        add_flag(d, "A4")

    # --- A5: 3 deals ---
    a5_deals = [next_deal() for _ in range(3)]
    for d in a5_deals:
        add_flag(d, "A5")

    # --- A6: 3 deals ---
    a6_deals = [next_deal() for _ in range(3)]
    for d in a6_deals:
        add_flag(d, "A6")

    # --- A7: 3 deals ---
    a7_deals = [next_deal() for _ in range(3)]
    for d in a7_deals:
        add_flag(d, "A7")

    # --- A8: 2 deals ---
    a8_deals = [next_deal() for _ in range(2)]
    for d in a8_deals:
        add_flag(d, "A8")

    # --- A9: 2 deals (same company) ---
    a9_d1 = next_deal()
    a9_d2 = next_deal()
    add_flag(a9_d1, "A9")
    add_flag(a9_d2, "A9")

    # --- Leurres: 6 deals ---
    l1_deal = next_deal()
    l2_deal = next_deal()
    l3_deal = next_deal()
    l4_deal = next_deal()
    l5_deal = next_deal()
    l6_deal = next_deal()

    add_flag(l1_deal, "L1")
    add_flag(l2_deal, "L2")
    add_flag(l3_deal, "L3")
    add_flag(l4_deal, "L4")
    add_flag(l5_deal, "L5")
    add_flag(l6_deal, "L6")

    # === Modify deals to match anomaly criteria ===

    def rebuild_history_with_stage_at(deal, stage, entered_date):
        """
        Rebuild history so that the given stage's entered_at = entered_date,
        and all previous stages are set proportionally earlier.
        """
        # Find the stage index in the history
        sh = deal["stage_history"]
        stage_idx_in_hist = None
        for i, entry in enumerate(sh):
            if entry["stage"] == stage:
                stage_idx_in_hist = i
                break

        if stage_idx_in_hist is None:
            # Rebuild entirely from created_at through stage
            created_at = datetime.date.fromisoformat(deal["created_at"])
            new_sh = []
            cur_date = created_at
            for s in STAGES:
                new_sh.append({"stage": s, "entered_at": cur_date.isoformat()})
                if s == stage:
                    break
                ndays = STAGE_META[s]["normal_days"]
                cur_date += datetime.timedelta(days=max(1, ndays // 2))
            # Now adjust last entry to entered_date
            if new_sh:
                new_sh[-1]["entered_at"] = entered_date.isoformat()
                # Push earlier entries back if needed
                for i in range(len(new_sh) - 2, -1, -1):
                    d_next = datetime.date.fromisoformat(new_sh[i+1]["entered_at"])
                    d_this = datetime.date.fromisoformat(new_sh[i]["entered_at"])
                    if d_this >= d_next:
                        new_sh[i]["entered_at"] = (d_next - datetime.timedelta(days=7)).isoformat()
            deal["stage_history"] = new_sh
        else:
            new_sh = list(sh[:stage_idx_in_hist + 1])
            new_sh[-1] = {"stage": stage, "entered_at": entered_date.isoformat()}

            # Ensure monotonicity: previous entries must be before entered_date
            for i in range(len(new_sh) - 2, -1, -1):
                d_next = datetime.date.fromisoformat(new_sh[i+1]["entered_at"])
                d_this = datetime.date.fromisoformat(new_sh[i]["entered_at"])
                if d_this >= d_next:
                    gap = max(1, (d_next - datetime.date.fromisoformat(deal["created_at"])).days // (len(new_sh)))
                    new_sh[i]["entered_at"] = (d_next - datetime.timedelta(days=gap)).isoformat()

            # Also update created_at if needed
            if new_sh:
                first_date = datetime.date.fromisoformat(new_sh[0]["entered_at"])
                created = datetime.date.fromisoformat(deal["created_at"])
                if first_date < created:
                    deal["created_at"] = new_sh[0]["entered_at"]

            deal["stage_history"] = new_sh

        deal["stage"] = stage
        deal["stage_entered_at"] = entered_date.isoformat()

    def set_stage_stagnant(deal):
        """Make a deal stagnant: days in current stage > 2× normal duration."""
        stage = deal["stage"]
        if stage not in STAGE_META or STAGE_META[stage]["normal_days"] is None:
            stage = "demo"
        normal_days = STAGE_META[stage]["normal_days"]
        # Put deal in stage for 2.5× normal duration
        excess_days = int(normal_days * 2.5) + rng.randint(5, 20)
        stage_entered = as_of - datetime.timedelta(days=excess_days)

        rebuild_history_with_stage_at(deal, stage, stage_entered)
        return excess_days, normal_days

    # Apply A1 stagnation
    all_a1_deals = a1a2_deals + a1_only_deals
    for d in all_a1_deals:
        excess_days, normal_days = set_stage_stagnant(d)
        stage_label = STAGE_META[d["stage"]]["label"]
        days_in_stage = (as_of - datetime.date.fromisoformat(d["stage_entered_at"])).days
        truth_rows.append({
            "deal_id": d["id"],
            "code": "A1",
            "attendu": "signaler",
            "preuve": f"En {stage_label} depuis {days_in_stage} j (normale {normal_days} j)",
            "owner": d["owner_id"],
        })

    # Apply A2: no future task or meeting
    all_a2_deals = a1a2_deals + a2_only_deals
    for d in all_a2_deals:
        truth_rows.append({
            "deal_id": d["id"],
            "code": "A2",
            "attendu": "signaler",
            "preuve": "Aucune tâche ni réunion à venir",
            "owner": d["owner_id"],
        })

    # Apply A3: close_date < as_of
    for d in a3_deals:
        days_past = rng.randint(5, 60)
        past_close = as_of - datetime.timedelta(days=days_past)
        d["close_date"] = past_close.isoformat()
        truth_rows.append({
            "deal_id": d["id"],
            "code": "A3",
            "attendu": "signaler",
            "preuve": f"Date de clôture dépassée : {past_close.isoformat()} (il y a {days_past} j)",
            "owner": d["owner_id"],
        })

    # Apply A4: amount >= 25000, last activity > 21 days ago
    for d in a4_deals:
        d["amount"] = rng.choice([25000, 30000, 35000, 40000, 45000, 50000])
        days_silent = rng.randint(22, 45)
        truth_rows.append({
            "deal_id": d["id"],
            "code": "A4",
            "attendu": "signaler",
            "preuve": f"Deal de {d['amount']}€ sans activité depuis {days_silent} j",
            "owner": d["owner_id"],
        })
        # Store the days_silent in anomaly_flags for activity generation
        anomaly_flags[d["id"]].add(f"A4_DAYS_{days_silent}")

    # Apply A5: amount null/0 from proposition stage onward
    for d in a5_deals:
        stage_idx = STAGES.index("proposition")
        later_stages = STAGES[stage_idx:]
        target_stage = rng.choice(later_stages)
        _rebuild_history_to_stage(deal=d, target_stage=target_stage, as_of=as_of, rng=rng)
        d["amount"] = None
        truth_rows.append({
            "deal_id": d["id"],
            "code": "A5",
            "attendu": "signaler",
            "preuve": f"Montant manquant en {STAGE_META[d['stage']]['label']}",
            "owner": d["owner_id"],
        })

    # Apply A6: close_date in as_of month but stage decouverte/qualification
    as_of_month_start = as_of.replace(day=1)
    as_of_month_end = _last_day_of_month(as_of)
    for d in a6_deals:
        d["stage"] = rng.choice(["decouverte", "qualification"])
        _rebuild_history_to_stage(deal=d, target_stage=d["stage"], as_of=as_of, rng=rng)
        # Set close_date within as_of month but NOT in the past (avoid also A3)
        # Range: as_of+1 to end of month
        start_range = as_of + datetime.timedelta(days=1)
        if start_range > as_of_month_end:
            start_range = as_of_month_end
        days_in_range = max(0, (as_of_month_end - start_range).days)
        day_offset = rng.randint(0, days_in_range)
        close = start_range + datetime.timedelta(days=day_offset)
        d["close_date"] = close.isoformat()
        truth_rows.append({
            "deal_id": d["id"],
            "code": "A6",
            "attendu": "signaler",
            "preuve": f"Clôture en {as_of.strftime('%Y-%m')} mais étape {STAGE_META[d['stage']]['label']}",
            "owner": d["owner_id"],
        })

    # Apply A7: amount >= 20000, stage negociation, only 1 contact
    for d in a7_deals:
        if d["amount"] is None or d["amount"] < 20000:
            d["amount"] = rng.choice([20000, 25000, 30000, 35000])
        d["stage"] = "negociation"
        _rebuild_history_to_stage(deal=d, target_stage="negociation", as_of=as_of, rng=rng)
        # Force single contact
        coy_contacts = contacts_by_company.get(d["company_id"], [])
        if coy_contacts:
            d["contact_ids"] = [coy_contacts[0]["id"]]
        else:
            d["contact_ids"] = []
        truth_rows.append({
            "deal_id": d["id"],
            "code": "A7",
            "attendu": "signaler",
            "preuve": f"Deal {d['amount']}€ en Négociation avec 1 seul interlocuteur",
            "owner": d["owner_id"],
        })

    # Apply A8: negociation but no meeting during demo stage period
    for d in a8_deals:
        d["stage"] = "negociation"
        _rebuild_history_full(deal=d, as_of=as_of, rng=rng)
        truth_rows.append({
            "deal_id": d["id"],
            "code": "A8",
            "attendu": "signaler",
            "preuve": "En Négociation sans réunion de démo dans l'historique",
            "owner": d["owner_id"],
        })

    # Apply A9: same company, 2 open deals with realistic near-identical names.
    # Different owners, different creation dates, different formatting — jamais "(copie)".
    a9_d2["company_id"] = a9_d1["company_id"]

    # Different owners
    a9_d1["owner_id"] = "ae1"
    a9_d2["owner_id"] = "ae3"

    # Stagger creation dates: d1 is 5-9 weeks older than d2
    gap_days = rng.randint(35, 63)
    d2_created = datetime.date.fromisoformat(a9_d2["created_at"])
    d1_created = d2_created - datetime.timedelta(days=gap_days)
    start_floor = datetime.date(2025, 5, 1)
    if d1_created < start_floor:
        d1_created = start_floor
    if d1_created != datetime.date.fromisoformat(a9_d1["created_at"]):
        # Shift stage_history of d1 by the same delta
        old_created = datetime.date.fromisoformat(a9_d1["created_at"])
        delta = old_created - d1_created  # positive if old_created > d1_created
        a9_d1["created_at"] = d1_created.isoformat()
        if datetime.date.fromisoformat(a9_d1["created_at"]) > as_of:
            a9_d1["created_at"] = as_of.isoformat()
        for sh in a9_d1["stage_history"]:
            sh_date = datetime.date.fromisoformat(sh["entered_at"])
            new_date = sh_date - delta
            if new_date < start_floor:
                new_date = start_floor
            if new_date > as_of:
                new_date = as_of
            sh["entered_at"] = new_date.isoformat()
        if a9_d1["stage_history"]:
            a9_d1["stage_entered_at"] = a9_d1["stage_history"][-1]["entered_at"]

    # Names: same product, different casing/abbreviation — both use
    # "Déploiement multi-sites" which contributes 3 stems on its own
    # ("deplo", "multi", "sites"), ensuring the A9 rule fires regardless
    # of what the company name happens to contribute.
    # Extract the company fragment from d1's existing name (already formatted
    # as "[short_co] – [theme]" by make_deal_name).
    _sep = " – " if " – " in a9_d1["name"] else " - "
    _co_frag = a9_d1["name"].split(_sep, 1)[0].strip()
    a9_d1["name"] = f"{_co_frag} – Déploiement multi-sites"
    a9_d2["name"] = f"{_co_frag.upper()} - deploy multi-sites"

    for d in [a9_d1, a9_d2]:
        truth_rows.append({
            "deal_id": d["id"],
            "code": "A9",
            "attendu": "signaler",
            "preuve": f"Doublon : même entreprise {d['company_id']}, noms quasi identiques",
            "owner": d["owner_id"],
        })

    # === Leurre modifications ===

    # L1, L2: Stagnant by duration BUT has recent note AND future meeting
    for leurre_code, d in [("L1", l1_deal), ("L2", l2_deal)]:
        stage = d["stage"]
        if stage not in STAGE_META or STAGE_META[stage]["normal_days"] is None:
            stage = "demo"
        normal_days = STAGE_META[stage]["normal_days"]
        excess_days = int(normal_days * 2.5) + rng.randint(5, 15)
        stage_entered = as_of - datetime.timedelta(days=excess_days)
        rebuild_history_with_stage_at(d, stage, stage_entered)
        days_in_stage = (as_of - datetime.date.fromisoformat(d["stage_entered_at"])).days
        stage_label = STAGE_META[stage]["label"]

        future_meeting_days = rng.randint(5, 20)
        future_date = as_of + datetime.timedelta(days=future_meeting_days)

        truth_rows.append({
            "deal_id": d["id"],
            "code": leurre_code,
            "attendu": "ignorer",
            "preuve": f"Long en {stage_label} mais RDV calé le {future_date.isoformat()}",
            "owner": d["owner_id"],
        })

    # L3, L4: amount >= 25000, last activity exactly 20 days ago (< 21 threshold)
    for leurre_code, d in [("L3", l3_deal), ("L4", l4_deal)]:
        d["amount"] = rng.choice([25000, 30000, 35000])
        truth_rows.append({
            "deal_id": d["id"],
            "code": leurre_code,
            "attendu": "ignorer",
            "preuve": f"Deal {d['amount']}€ mais dernière activité il y a 20 j (seuil 21 j)",
            "owner": d["owner_id"],
        })

    # L5: negociation, 1 contact, amount = 15000 (< 20000 threshold)
    l5_deal["stage"] = "negociation"
    _rebuild_history_to_stage(deal=l5_deal, target_stage="negociation", as_of=as_of, rng=rng)
    l5_deal["amount"] = 15000
    coy_contacts = contacts_by_company.get(l5_deal["company_id"], [])
    if coy_contacts:
        l5_deal["contact_ids"] = [coy_contacts[0]["id"]]
    truth_rows.append({
        "deal_id": l5_deal["id"],
        "code": "L5",
        "attendu": "ignorer",
        "preuve": "Négociation 1 contact mais montant 15 000€ (seuil A7 = 20 000€)",
        "owner": l5_deal["owner_id"],
    })

    # L6: close_date = as_of exactly
    l6_deal["close_date"] = as_of.isoformat()
    truth_rows.append({
        "deal_id": l6_deal["id"],
        "code": "L6",
        "attendu": "ignorer",
        "preuve": f"Date de clôture = as_of ({as_of.isoformat()}), pas encore dépassée",
        "owner": l6_deal["owner_id"],
    })

    return deals, anomaly_flags, truth_rows


def _last_day_of_month(d):
    """Return the last day of the month for a given date."""
    if d.month == 12:
        return d.replace(day=31)
    return d.replace(month=d.month + 1, day=1) - datetime.timedelta(days=1)


def _rebuild_history_to_stage(deal, target_stage, as_of, rng):
    """
    Rebuild stage_history so deal ends at target_stage.
    Ensures monotonic dates.
    """
    created_at = datetime.date.fromisoformat(deal["created_at"])
    history = []
    cur_date = created_at

    # Ensure created_at is old enough for all stages
    stages_to_pass = STAGES[:STAGES.index(target_stage)]
    min_days_needed = sum(max(1, STAGE_META[s]["normal_days"] // 2) for s in stages_to_pass)
    if (as_of - created_at).days < min_days_needed + 2:
        created_at = as_of - datetime.timedelta(days=min_days_needed + 2 + rng.randint(0, 10))
        if created_at < datetime.date(2025, 5, 1):
            created_at = datetime.date(2025, 5, 1)
        deal["created_at"] = created_at.isoformat()
        cur_date = created_at

    for stage in STAGES:
        entered = cur_date
        history.append({"stage": stage, "entered_at": entered.isoformat()})
        if stage == target_stage:
            break
        normal_days = STAGE_META[stage]["normal_days"]
        days_spent = rng.randint(max(1, int(normal_days * 0.5)), int(normal_days * 1.2))
        cur_date = cur_date + datetime.timedelta(days=days_spent)
        if cur_date >= as_of:
            cur_date = as_of - datetime.timedelta(days=1)

    deal["stage"] = target_stage
    deal["stage_entered_at"] = history[-1]["entered_at"]
    deal["stage_history"] = history


def _rebuild_history_full(deal, as_of, rng):
    """Rebuild full history through all STAGES for A8 deals (up to negociation)."""
    created_at = datetime.date.fromisoformat(deal["created_at"])

    # Total min days for all stages up to negociation
    stages_before_negociation = STAGES[:STAGES.index("negociation")]
    total_min_days = sum(max(1, STAGE_META[s]["normal_days"] // 2) for s in stages_before_negociation)

    if (as_of - created_at).days < total_min_days + 10:
        created_at = as_of - datetime.timedelta(days=total_min_days + 30)
        if created_at < datetime.date(2025, 5, 1):
            created_at = datetime.date(2025, 5, 1)
        deal["created_at"] = created_at.isoformat()

    history = []
    cur_date = created_at

    for stage in STAGES:
        entered = cur_date
        history.append({"stage": stage, "entered_at": entered.isoformat()})
        if stage == "negociation":
            break
        normal_days = STAGE_META[stage]["normal_days"]
        days_spent = rng.randint(max(1, int(normal_days * 0.6)), int(normal_days * 1.1))
        cur_date = cur_date + datetime.timedelta(days=days_spent)
        if cur_date >= as_of:
            cur_date = as_of - datetime.timedelta(days=1)

    deal["stage"] = "negociation"
    deal["stage_entered_at"] = history[-1]["entered_at"]
    deal["stage_history"] = history
