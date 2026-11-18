#!/usr/bin/env python3
"""
Atelier Nova CRM Generator — Phase 1
Usage: python3 generate.py --seed 42 --as-of 2026-11-18 [--public]
"""

import argparse
import csv
import datetime
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(__file__))

from nova.companies import select_companies, make_public_companies
from nova.people import gen_contacts
from nova.deals import gen_deals
from nova.activities import gen_all_activities
from nova.anomalies import plant_anomalies
from nova.pipeline import OWNERS, STAGES, STAGE_META


def parse_args():
    parser = argparse.ArgumentParser(description="Atelier Nova CRM Generator")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--as-of", type=str, default=None,
                        help="Reference date YYYY-MM-DD (default: today)")
    parser.add_argument("--public", action="store_true",
                        help="Replace real company data with invented data")
    return parser.parse_args()


def build_activities_by_deal(activities):
    by_deal = {}
    for a in activities:
        did = a["deal_id"]
        if did not in by_deal:
            by_deal[did] = []
        by_deal[did].append(a)
    return by_deal


def postprocess_activities(activities_by_deal, deals, anomaly_flags, as_of):
    """
    Apply all post-processing to activities:
    1. A4 anomaly: ensure last past activity > days_silent ago
    2. L3/L4 leurres: ensure last past activity = exactly 20 days ago
    3. A2 anomaly: remove all future tache/reunion
    4. L1/L2 leurres: ensure recent note + future reunion
    5. A8 anomaly: remove meetings during demo period
    6. Clean negociation deals: add meeting in demo period (A8 prevention)
    7. Clean open deals with big amounts: add recent activity (A4 prevention)
    8. Clean open deals: ensure at least 1 future next step (A2 prevention)
    9. Won/lost deals: enforce Rule 2 (delete after close_date, ensure closing note)
    """
    deals_by_id = {d["id"]: d for d in deals}
    flagged_deals = set(anomaly_flags.keys())

    for did, flags in anomaly_flags.items():
        deal = deals_by_id.get(did)
        if not deal:
            continue
        owner_id = deal["owner_id"]

        # --- A4 anomaly: enforce silence ---
        if "A4" in flags:
            days_silent = 22
            for flag in flags:
                if flag.startswith("A4_DAYS_"):
                    days_silent = int(flag.split("_")[-1])
                    break
            cutoff = as_of - datetime.timedelta(days=days_silent)
            deal_acts = activities_by_deal.get(did, [])
            new_acts = []
            for a in deal_acts:
                at_date = datetime.datetime.fromisoformat(a["at"]).date()
                if at_date > as_of or at_date <= cutoff:
                    new_acts.append(a)
            activities_by_deal[did] = new_acts

        # --- L3/L4: last activity = exactly 20 days ago ---
        if "L3" in flags or "L4" in flags:
            target_date = as_of - datetime.timedelta(days=20)
            deal_acts = activities_by_deal.get(did, [])
            new_acts = []
            has_target_act = False
            for a in deal_acts:
                at_date = datetime.datetime.fromisoformat(a["at"]).date()
                if at_date > as_of:
                    new_acts.append(a)
                elif at_date <= target_date:
                    new_acts.append(a)
                    if at_date == target_date:
                        has_target_act = True
            if not has_target_act:
                at_dt_target = datetime.datetime(target_date.year, target_date.month, target_date.day, 10, 0, 0)
                new_acts.append({
                    "deal_id": did,
                    "contact_id": deal["contact_ids"][0] if deal["contact_ids"] else None,
                    "owner_id": owner_id,
                    "type": "appel",
                    "at": at_dt_target.isoformat(),
                    "subject": "Appel de suivi",
                    "body": "Point de suivi avec le client.",
                })
            activities_by_deal[did] = new_acts

        # --- A1 anomaly: remove recent notes to prevent accidental L1/L2 exception ---
        if "A1" in flags and "L1" not in flags and "L2" not in flags:
            deal_acts = activities_by_deal.get(did, [])
            activities_by_deal[did] = [
                a for a in deal_acts
                if not (a["type"] == "note"
                        and 0 <= (as_of - datetime.datetime.fromisoformat(a["at"]).date()).days < 7)
            ]

        # --- A2 anomaly: remove all future tache/reunion ---
        if "A2" in flags:
            deal_acts = activities_by_deal.get(did, [])
            new_acts = [
                a for a in deal_acts
                if not (datetime.datetime.fromisoformat(a["at"]).date() > as_of
                        and a["type"] in ("tache", "reunion"))
            ]
            activities_by_deal[did] = new_acts

        # --- L1/L2: ensure recent note + future reunion ---
        if "L1" in flags or "L2" in flags:
            deal_acts = activities_by_deal.get(did, [])
            has_recent_note = any(
                a["type"] == "note"
                and (as_of - datetime.datetime.fromisoformat(a["at"]).date()).days < 7
                and datetime.datetime.fromisoformat(a["at"]).date() <= as_of
                for a in deal_acts
            )
            has_future_reunion = any(
                a["type"] == "reunion"
                and datetime.datetime.fromisoformat(a["at"]).date() > as_of
                for a in deal_acts
            )
            # Determine future_date for the reunion (and note body)
            future_date = as_of + datetime.timedelta(days=14)
            # If a future reunion already exists, extract its date for note coherence
            existing_reunion_dates = [
                datetime.datetime.fromisoformat(a["at"]).date()
                for a in deal_acts
                if a["type"] == "reunion"
                and datetime.datetime.fromisoformat(a["at"]).date() > as_of
            ]
            if existing_reunion_dates:
                future_date = min(existing_reunion_dates)
            if not has_recent_note:
                note_date = as_of - datetime.timedelta(days=3)
                rdv_str = future_date.strftime("%-d/%m")
                deal_acts.append({
                    "deal_id": did,
                    "contact_id": deal["contact_ids"][0] if deal["contact_ids"] else None,
                    "owner_id": owner_id,
                    "type": "note",
                    "at": datetime.datetime(note_date.year, note_date.month, note_date.day, 10, 0, 0).isoformat(),
                    "subject": "Note de suivi",
                    "body": f"client ok, RDV dc le {rdv_str} – relance ok",
                })
            if not has_future_reunion:
                deal_acts.append({
                    "deal_id": did,
                    "contact_id": deal["contact_ids"][0] if deal["contact_ids"] else None,
                    "owner_id": owner_id,
                    "type": "reunion",
                    "at": datetime.datetime(future_date.year, future_date.month, future_date.day, 10, 0, 0).isoformat(),
                    "subject": "Réunion de suivi",
                    "body": f"RDV calé le {future_date.isoformat()}.",
                })
            activities_by_deal[did] = deal_acts

        # --- A8 anomaly: remove meetings during demo period ---
        if "A8" in flags:
            demo_start, prop_start = _get_demo_period(deal["stage_history"])
            if demo_start:
                if prop_start is None:
                    prop_start = demo_start + datetime.timedelta(days=90)
                deal_acts = activities_by_deal.get(did, [])
                new_acts = [
                    a for a in deal_acts
                    if not (a["type"] == "reunion"
                            and demo_start <= datetime.datetime.fromisoformat(a["at"]).date() < prop_start)
                ]
                activities_by_deal[did] = new_acts

    # === Post-process clean (non-anomaly) open deals ===
    for deal in deals:
        if deal["status"] != "open":
            continue
        did = deal["id"]
        if did in flagged_deals:
            continue

        deal_acts = activities_by_deal.get(did, [])
        owner_id = deal["owner_id"]
        contact_id = deal["contact_ids"][0] if deal["contact_ids"] else None

        # A8 prevention: clean negociation deals need meeting in demo period
        if deal["stage"] == "negociation":
            demo_start, prop_start = _get_demo_period(deal["stage_history"])
            if demo_start and prop_start:
                has_demo_meeting = any(
                    a["type"] == "reunion"
                    and demo_start <= datetime.datetime.fromisoformat(a["at"]).date() < prop_start
                    for a in deal_acts
                )
                if not has_demo_meeting:
                    # Add a meeting in the demo period
                    mid = demo_start + (prop_start - demo_start) // 2
                    at_dt = datetime.datetime(mid.year, mid.month, mid.day, 10, 0, 0)
                    deal_acts.append({
                        "deal_id": did,
                        "contact_id": contact_id,
                        "owner_id": owner_id,
                        "type": "reunion",
                        "at": at_dt.isoformat(),
                        "subject": "Réunion de démo",
                        "body": "Démo réalisée. Client très intéressé.",
                    })
                    activities_by_deal[did] = deal_acts

        # A4 prevention: big deals need recent activity (within 21 days)
        amount = deal.get("amount")
        if amount and amount >= 25000:
            last_past = None
            for a in deal_acts:
                at_date = datetime.datetime.fromisoformat(a["at"]).date()
                if at_date <= as_of:
                    if last_past is None or at_date > last_past:
                        last_past = at_date
            if last_past is None or (as_of - last_past).days > 21:
                # Add recent activity
                recent_date = as_of - datetime.timedelta(days=5)
                at_dt = datetime.datetime(recent_date.year, recent_date.month, recent_date.day, 10, 0, 0)
                deal_acts.append({
                    "deal_id": did,
                    "contact_id": contact_id,
                    "owner_id": owner_id,
                    "type": "appel",
                    "at": at_dt.isoformat(),
                    "subject": "Appel de suivi",
                    "body": "Point de suivi avec le client.",
                })
                activities_by_deal[did] = deal_acts

        # A2 prevention: ensure at least 1 future next step for clean open deals
        has_next_step = any(
            a["type"] in ("tache", "reunion")
            and datetime.datetime.fromisoformat(a["at"]).date() > as_of
            for a in deal_acts
        )
        if not has_next_step:
            future_date = as_of + datetime.timedelta(days=7)
            at_dt = datetime.datetime(future_date.year, future_date.month, future_date.day, 9, 0, 0)
            deal_acts.append({
                "deal_id": did,
                "contact_id": contact_id,
                "owner_id": owner_id,
                "type": "tache",
                "at": at_dt.isoformat(),
                "subject": "Relancer le contact",
                "body": "Relance à faire avant fin de semaine.",
            })
            activities_by_deal[did] = deal_acts

    # === Rule 2: enforce won/lost closing discipline ===
    from nova.activities import LOST_REASON_BODIES as _LOST_REASON_BODIES
    for deal in deals:
        if deal["status"] not in ("won", "lost"):
            continue
        did = deal["id"]
        close_date_str = deal.get("close_date")
        if not close_date_str:
            continue
        close_date = datetime.date.fromisoformat(close_date_str)
        owner_id = deal["owner_id"]
        contact_id = deal["contact_ids"][0] if deal["contact_ids"] else None
        close_dt = datetime.datetime(close_date.year, close_date.month, close_date.day, 18, 0, 0)

        deal_acts = activities_by_deal.get(did, [])

        # Delete all activities whose at date > close_date
        deal_acts = [
            a for a in deal_acts
            if datetime.datetime.fromisoformat(a["at"]).date() <= close_date
        ]

        # Check if closing note already exists (type=note, date=close_date, special subject)
        closing_subjects = {"Deal gagné", "Deal perdu"}
        has_closing_note = any(
            a["type"] == "note"
            and datetime.datetime.fromisoformat(a["at"]).date() == close_date
            and a.get("subject") in closing_subjects
            for a in deal_acts
        )

        if not has_closing_note:
            if deal["status"] == "won":
                closing_subject = "Deal gagné"
                closing_body = "Contrat signé. Bon deal."
            else:
                lost_reason = deal.get("lost_reason", "")
                closing_subject = "Deal perdu"
                closing_body = _LOST_REASON_BODIES.get(
                    lost_reason, f"Perdu – {lost_reason}."
                )
            deal_acts.append({
                "deal_id": did,
                "contact_id": contact_id,
                "owner_id": owner_id,
                "type": "note",
                "at": close_dt.isoformat(),
                "subject": closing_subject,
                "body": closing_body,
            })

        activities_by_deal[did] = deal_acts

    return activities_by_deal


def _get_demo_period(stage_history):
    """Extract demo start and proposition start dates from stage history."""
    demo_start = None
    prop_start = None
    for sh in stage_history:
        if sh["stage"] == "demo":
            demo_start = datetime.date.fromisoformat(sh["entered_at"])
        elif sh["stage"] == "proposition":
            prop_start = datetime.date.fromisoformat(sh["entered_at"])
    return demo_start, prop_start


def cleanup_accidental_anomalies(deals, activities_by_deal, anomaly_flags, as_of, rng, contacts_by_company):
    """
    Final cleanup pass: for each open deal, ensure no unassigned anomaly rule triggers.
    Covers both clean deals and anomaly deals that might accidentally trigger other rules.
    Must be idempotent: safe to call after postprocess_activities.
    """
    from nova.pipeline import STAGE_META

    as_of_date = as_of if isinstance(as_of, datetime.date) else datetime.date.fromisoformat(as_of)

    for deal in deals:
        if deal["status"] != "open":
            continue
        did = deal["id"]
        raw_flags = anomaly_flags.get(did, set())
        assigned = {c for c in raw_flags if not c.startswith("A4_DAYS_")}
        stage = deal["stage"]

        # === A1 prevention ===
        if "A1" not in assigned and "L1" not in assigned and "L2" not in assigned:
            meta = STAGE_META.get(stage)
            if meta and meta["normal_days"]:
                normal_days = meta["normal_days"]
                stage_entered = datetime.date.fromisoformat(deal["stage_entered_at"])
                days_in_stage = (as_of_date - stage_entered).days
                if days_in_stage > 2 * normal_days:
                    new_days = rng.randint(1, 2 * normal_days - 1)
                    new_entered = as_of_date - datetime.timedelta(days=new_days)
                    deal["stage_entered_at"] = new_entered.isoformat()
                    for sh in deal["stage_history"]:
                        if sh["stage"] == stage:
                            sh["entered_at"] = new_entered.isoformat()
                            break

        # === A3 prevention ===
        if "A3" not in assigned and "L6" not in assigned:
            cd = deal.get("close_date")
            if cd:
                close_date = datetime.date.fromisoformat(cd)
                if close_date < as_of_date:
                    deal["close_date"] = (as_of_date + datetime.timedelta(days=rng.randint(14, 90))).isoformat()

        # === A5 prevention ===
        if "A5" not in assigned:
            if stage in ("proposition", "negociation"):
                amount = deal.get("amount")
                if amount is None or amount == 0:
                    deal["amount"] = rng.choice([12000, 15000, 18000, 20000, 25000, 30000])

        # === A6 prevention ===
        # Also skip if A3 is assigned: an A3 close_date may fall in as_of month
        # (recently past), and we must NOT push it to the future.
        if "A6" not in assigned and "A3" not in assigned:
            if stage in ("decouverte", "qualification"):
                cd = deal.get("close_date")
                if cd:
                    close_date = datetime.date.fromisoformat(cd)
                    if close_date.year == as_of_date.year and close_date.month == as_of_date.month:
                        m = as_of_date.month + 1
                        y = as_of_date.year
                        if m > 12:
                            m = 1
                            y += 1
                        deal["close_date"] = datetime.date(y, m, rng.randint(5, 28)).isoformat()

        # === A7 prevention ===
        if "A7" not in assigned and "L5" not in assigned:
            if stage == "negociation":
                amount = deal.get("amount")
                if amount and amount >= 20000:
                    contact_ids = deal.get("contact_ids", [])
                    if len(contact_ids) == 1:
                        coy_contacts = contacts_by_company.get(deal["company_id"], [])
                        extra = [c for c in coy_contacts if c["id"] not in contact_ids]
                        if extra:
                            deal["contact_ids"].append(extra[0]["id"])
                        else:
                            deal["amount"] = 15000

        # === A4 prevention ===
        if "A4" not in assigned and "L3" not in assigned and "L4" not in assigned:
            amount = deal.get("amount")
            if amount and amount >= 25000:
                deal_acts = activities_by_deal.get(did, [])
                last_past = None
                for a in deal_acts:
                    at_date = datetime.datetime.fromisoformat(a["at"]).date()
                    if at_date <= as_of_date:
                        if last_past is None or at_date > last_past:
                            last_past = at_date
                if last_past is None or (as_of_date - last_past).days > 21:
                    recent_date = as_of_date - datetime.timedelta(days=5)
                    at_dt = datetime.datetime(recent_date.year, recent_date.month, recent_date.day, 10, 0, 0)
                    activities_by_deal.setdefault(did, []).append({
                        "deal_id": did,
                        "contact_id": deal["contact_ids"][0] if deal["contact_ids"] else None,
                        "owner_id": deal["owner_id"],
                        "type": "appel",
                        "at": at_dt.isoformat(),
                        "subject": "Appel de suivi",
                        "body": "Point de suivi avec le client.",
                    })

        # === A8 prevention ===
        if "A8" not in assigned and stage == "negociation":
            demo_start, prop_start = _get_demo_period(deal["stage_history"])
            if demo_start is None:
                eff_start = datetime.date.fromisoformat(deal["created_at"])
                eff_end = eff_start + datetime.timedelta(days=90)
            else:
                eff_start = demo_start
                eff_end = prop_start if prop_start else demo_start + datetime.timedelta(days=90)
            if eff_end > as_of_date:
                eff_end = as_of_date
            if eff_start >= eff_end:
                eff_start = eff_end - datetime.timedelta(days=14)

            deal_acts = activities_by_deal.get(did, [])
            has_demo_meeting = any(
                a["type"] == "reunion"
                and eff_start <= datetime.datetime.fromisoformat(a["at"]).date() < eff_end
                for a in deal_acts
            )
            if not has_demo_meeting:
                mid = eff_start + (eff_end - eff_start) // 2
                at_dt = datetime.datetime(mid.year, mid.month, mid.day, 10, 0, 0)
                activities_by_deal.setdefault(did, []).append({
                    "deal_id": did,
                    "contact_id": deal["contact_ids"][0] if deal["contact_ids"] else None,
                    "owner_id": deal["owner_id"],
                    "type": "reunion",
                    "at": at_dt.isoformat(),
                    "subject": "Réunion de démo",
                    "body": "Démo réalisée. Client très intéressé.",
                })

        # === A2 prevention ===
        if "A2" not in assigned and "L1" not in assigned and "L2" not in assigned:
            deal_acts = activities_by_deal.get(did, [])
            has_next_step = any(
                a["type"] in ("tache", "reunion")
                and datetime.datetime.fromisoformat(a["at"]).date() > as_of_date
                for a in deal_acts
            )
            if not has_next_step:
                future_date = as_of_date + datetime.timedelta(days=7)
                at_dt = datetime.datetime(future_date.year, future_date.month, future_date.day, 9, 0, 0)
                activities_by_deal.setdefault(did, []).append({
                    "deal_id": did,
                    "contact_id": deal["contact_ids"][0] if deal["contact_ids"] else None,
                    "owner_id": deal["owner_id"],
                    "type": "tache",
                    "at": at_dt.isoformat(),
                    "subject": "Relancer le contact",
                    "body": "Relance à faire avant fin de semaine.",
                })

    # === A9 prevention (second pass, cross-deal) ===
    # Ensure no two clean open deals for the same company share ≥ 3 stems.
    from nova.rules import _names_similar as _ns
    clean_open_by_company = {}
    for deal in deals:
        if deal["status"] != "open":
            continue
        did = deal["id"]
        if "A9" in {c for c in anomaly_flags.get(did, set()) if not c.startswith("A4_DAYS_")}:
            continue
        clean_open_by_company.setdefault(deal["company_id"], []).append(deal)

    for _cid, cdeals in clean_open_by_company.items():
        if len(cdeals) < 2:
            continue
        for i in range(len(cdeals)):
            for j in range(i + 1, len(cdeals)):
                d1, d2 = cdeals[i], cdeals[j]
                if _ns(d1["name"].lower(), d2["name"].lower()):
                    # Rename d2 to a theme that shares <3 stems with d1.
                    # Extract the company fragment already embedded in the name.
                    _sep = " – " if " – " in d2["name"] else " - "
                    _co_frag = d2["name"].split(_sep, 1)[0].strip()
                    _PROP_OR_LATER = {"proposition", "negociation", "gagne", "perdu"}
                    if d2.get("stage") in _PROP_OR_LATER:
                        d2["name"] = f"{_co_frag} – Extension utilisateurs"
                    else:
                        d2["name"] = f"{_co_frag} – Pilote agence"


def _fix_stage_coherence(activities_by_deal, deals, rng):
    """
    After all stage history modifications, ensure no activity body violates
    its stage's content rules.
    Rules:
      - decouverte, qualification, demo, proposition: no 'contrat' or 'signature'
      - decouverte, qualification, demo: no 'devis' or 'proposition commerciale'
    When a violation is found, replace the body (and subject) with a valid template
    for that stage and activity type.
    """
    from nova.texts import pick_template, get_stage_at_date, STAGE_TEMPLATES

    deals_by_id = {d["id"]: d for d in deals}

    # Forbidden words per stage group
    NO_CONTRACT_STAGES = {"decouverte", "qualification", "demo", "proposition"}
    NO_DEVIS_STAGES = {"decouverte", "qualification", "demo"}

    for did, acts in activities_by_deal.items():
        deal = deals_by_id.get(did)
        if not deal:
            continue
        stage_history = deal.get("stage_history", [])

        for a in acts:
            # Skip future activities (tache/reunion) and closing notes
            if a.get("subject") in ("Deal gagné", "Deal perdu"):
                continue
            at_date = datetime.datetime.fromisoformat(a["at"]).date()
            act_stage = get_stage_at_date(stage_history, at_date)
            if act_stage is None:
                continue

            body_lower = (a.get("body") or "").lower()
            has_contract_violation = (
                act_stage in NO_CONTRACT_STAGES
                and ("contrat" in body_lower or "signature" in body_lower)
            )
            has_devis_violation = (
                act_stage in NO_DEVIS_STAGES
                and ("devis" in body_lower or "proposition commerciale" in body_lower)
            )

            if has_contract_violation or has_devis_violation:
                act_type = a.get("type", "note")
                # Replace with a clean template for this stage
                # Use the used bodies from this deal to avoid creating duplicates
                current_bodies = {x.get("body") for x in acts if x is not a}
                new_subject, new_body = pick_template(rng, act_type, stage=act_stage,
                                                        exclude_bodies=current_bodies)
                # If the new template still violates (all templates exhausted),
                # use a generic safe fallback
                new_body_lower = new_body.lower()
                if (act_stage in NO_CONTRACT_STAGES and
                        ("contrat" in new_body_lower or "signature" in new_body_lower)):
                    new_subject, new_body = _safe_fallback_template(act_stage, act_type)
                elif (act_stage in NO_DEVIS_STAGES and
                        ("devis" in new_body_lower or "proposition commerciale" in new_body_lower)):
                    new_subject, new_body = _safe_fallback_template(act_stage, act_type)
                a["subject"] = new_subject
                a["body"] = new_body


def _safe_fallback_template(stage, act_type):
    """Return a guaranteed-safe subject/body for stages before negociation."""
    safe = {
        "appel": ("Point rapide", "échange de suivi ok. client toujours engagé."),
        "email": ("Suivi demande", "Je reviens vers vous pour faire le point. Bonne journée."),
        "reunion": ("Point projet", "réunion de suivi réalisée. prochaine étape à définir."),
        "note": ("Note de suivi", "suivi en cours. rien de bloquant à ce stade."),
        "tache": ("Rappeler le contact", "Rappeler le contact cette semaine."),
    }
    return safe.get(act_type, ("Note de suivi", "suivi en cours."))


def _deduplicate_activity_bodies(activities_by_deal, rng):
    """
    For each deal, ensure no two activities share the same body text.
    Duplicates are resolved by appending a small unique suffix.
    This preserves stage-awareness already applied during generation.
    """
    for did, acts in activities_by_deal.items():
        seen_bodies = {}  # body -> first activity index
        for idx, a in enumerate(acts):
            body = a.get("body", "")
            if body in seen_bodies:
                # Create a unique variant by appending a brief note
                counter = 1
                new_body = body
                while new_body in seen_bodies:
                    new_body = body + f" (cf. suivi {counter})"
                    counter += 1
                a["body"] = new_body
                seen_bodies[new_body] = idx
            else:
                seen_bodies[body] = idx


def main():
    args = parse_args()

    if args.as_of:
        as_of = datetime.date.fromisoformat(args.as_of)
    else:
        as_of = datetime.date.today()

    seed = args.seed
    public = args.public

    print(f"Generating CRM data: seed={seed}, as_of={as_of}, public={public}")

    rng = random.Random(seed)

    # === 1. Companies ===
    print("Selecting companies...")
    try:
        companies_raw = select_companies(rng, target=220)
    except RuntimeError as e:
        print(f"\nERREUR : {e}\n")
        sys.exit(1)

    # Guard: ensure enough strategic companies to avoid a lopsided CRM.
    # select_companies targets round(220/3)=73 strategic; warn if cache falls short.
    MIN_STRAT = 73
    n_strat_selected = sum(1 for c in companies_raw if c.get("segment") == "strategique")
    if n_strat_selected < MIN_STRAT:
        print(
            f"\nERREUR : seulement {n_strat_selected} entreprises stratégiques dans le cache "
            f"(minimum requis : {MIN_STRAT}).\n"
            "Le cache ne contient pas assez d'entreprises 500+ salariés.\n"
            "Relancez la récupération des grandes entreprises :\n"
            "  python3 fetch_companies.py --only strat\n"
        )
        sys.exit(1)

    if public:
        companies_raw = make_public_companies(rng, companies_raw)

    companies = []
    for i, c in enumerate(companies_raw, 1):
        c["id"] = f"C-{i:04d}"
        companies.append(c)

    print(f"  {len(companies)} companies selected")

    # === 2. Contacts ===
    print("Generating contacts...")
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

    print(f"  {len(contacts)} contacts generated")

    # === 3. Deals ===
    print("Generating deals...")
    deals_raw = gen_deals(
        rng, companies, contacts_by_company, as_of,
        n_open=70, n_won=70, n_lost=120
    )

    deals = []
    for i, d in enumerate(deals_raw, 1):
        d["id"] = f"D-{i:04d}"
        deals.append(d)

    n_open = sum(1 for d in deals if d["status"] == "open")
    n_won = sum(1 for d in deals if d["status"] == "won")
    n_lost = sum(1 for d in deals if d["status"] == "lost")
    print(f"  {len(deals)} deals: {n_open} open, {n_won} won, {n_lost} lost")

    # === 4. Plant anomalies ===
    print("Planting anomalies and leurres...")
    deals, anomaly_flags, truth_rows = plant_anomalies(
        rng, deals, contacts_by_company, as_of
    )

    n_signaler = sum(1 for r in truth_rows if r["attendu"] == "signaler")
    n_ignorer = sum(1 for r in truth_rows if r["attendu"] == "ignorer")
    print(f"  {n_signaler} anomalies (signaler), {n_ignorer} leurres (ignorer)")

    # === 5. Activities ===
    print("Generating activities...")

    # Build activity flags for activity generator
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
        rng, deals, contacts_by_company, as_of,
        anomaly_flags=act_flags
    )

    # Index by deal
    activities_by_deal = build_activities_by_deal(activities_raw)

    # Ensure all deals have at least minimal activities
    for deal in deals:
        if deal["id"] not in activities_by_deal:
            created_at = datetime.date.fromisoformat(deal["created_at"])
            at_dt = datetime.datetime(created_at.year, created_at.month, created_at.day, 9, 0, 0)
            activities_by_deal[deal["id"]] = [{
                "deal_id": deal["id"],
                "contact_id": deal["contact_ids"][0] if deal["contact_ids"] else None,
                "owner_id": deal["owner_id"],
                "type": "appel",
                "at": at_dt.isoformat(),
                "subject": "Appel initial",
                "body": "Premier contact avec le client.",
            }]

    # Apply all post-processing
    activities_by_deal = postprocess_activities(
        activities_by_deal, deals, anomaly_flags, as_of
    )

    # Final cleanup: fix any accidental anomaly triggers on non-assigned deals
    cleanup_accidental_anomalies(
        deals, activities_by_deal, anomaly_flags, as_of, rng, contacts_by_company
    )

    # Stage coherence pass: fix any activity whose body violates its stage's rules
    _fix_stage_coherence(activities_by_deal, deals, rng)

    # Deduplication pass: ensure no two activities on the same deal share the same body
    _deduplicate_activity_bodies(activities_by_deal, rng)

    # Flatten and assign IDs
    all_activities = []
    for acts_list in activities_by_deal.values():
        all_activities.extend(acts_list)

    all_activities.sort(key=lambda a: (a["deal_id"], a["at"]))
    activities_final = []
    for i, a in enumerate(all_activities, 1):
        a["id"] = f"A-{i:04d}"
        activities_final.append(a)

    print(f"  {len(activities_final)} activities generated")

    # === 6. Build output ===
    out_dir = os.path.join(os.path.dirname(__file__), "out")
    os.makedirs(out_dir, exist_ok=True)

    crm_data = {
        "meta": {
            "as_of": as_of.isoformat(),
            "seed": seed,
            "public": public,
        },
        "owners": OWNERS,
        "companies": companies,
        "contacts": contacts,
        "deals": deals,
        "activities": activities_final,
    }

    crm_path = os.path.join(out_dir, "crm.json")
    with open(crm_path, "w", encoding="utf-8") as f:
        json.dump(crm_data, f, ensure_ascii=False, indent=2, default=str)
    print(f"  Written: {crm_path}")

    truth_path = os.path.join(out_dir, "truth.csv")
    with open(truth_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["deal_id", "code", "attendu", "preuve", "owner"])
        writer.writeheader()
        truth_rows_sorted = sorted(truth_rows, key=lambda r: (r["deal_id"], r["code"]))
        for row in truth_rows_sorted:
            writer.writerow(row)
    print(f"  Written: {truth_path}")

    summary_path = os.path.join(out_dir, "summary.md")
    _write_summary(summary_path, crm_data, truth_rows, as_of, seed, public)
    print(f"  Written: {summary_path}")

    print("Done!")
    return crm_data, truth_rows


def _write_summary(path, crm_data, truth_rows, as_of, seed, public):
    deals = crm_data["deals"]
    activities = crm_data["activities"]
    companies = crm_data["companies"]
    contacts = crm_data["contacts"]

    ae_stats = {}
    for d in deals:
        oid = d["owner_id"]
        if oid not in ae_stats:
            ae_stats[oid] = {"open": 0, "won": 0, "lost": 0}
        ae_stats[oid][d.get("status", "open")] += 1

    anomalies = [r for r in truth_rows if r["attendu"] == "signaler"]
    leurres = [r for r in truth_rows if r["attendu"] == "ignorer"]

    lines = [
        "# Résumé CRM Atelier Nova",
        "",
        f"- **Date de référence (as_of)** : {as_of}",
        f"- **Graine aléatoire** : {seed}",
        f"- **Mode public** : {'oui' if public else 'non'}",
        "",
        "## Volumes",
        "",
        "| Objet | Nombre |",
        "| --- | --- |",
        f"| Entreprises | {len(companies)} |",
        f"| Contacts | {len(contacts)} |",
        f"| Deals (total) | {len(deals)} |",
        f"| Deals ouverts | {sum(1 for d in deals if d['status'] == 'open')} |",
        f"| Deals gagnés | {sum(1 for d in deals if d['status'] == 'won')} |",
        f"| Deals perdus | {sum(1 for d in deals if d['status'] == 'lost')} |",
        f"| Activités | {len(activities)} |",
        "",
        "## Répartition par étape (deals ouverts)",
        "",
        "| Étape | Nombre |",
        "| --- | --- |",
    ]
    for stage in STAGES:
        cnt = sum(1 for d in deals if d["status"] == "open" and d["stage"] == stage)
        lines.append(f"| {stage} | {cnt} |")

    lines += [
        "",
        "## Répartition par AE",
        "",
        "| AE | Ouverts | Gagnés | Perdus |",
        "| --- | --- | --- | --- |",
    ]
    from nova.pipeline import AE_IDS
    for ae in AE_IDS:
        stats = ae_stats.get(ae, {"open": 0, "won": 0, "lost": 0})
        lines.append(f"| {ae} | {stats['open']} | {stats['won']} | {stats['lost']} |")

    lines += [
        "",
        f"## Anomalies plantées ({len(anomalies)} signaler)",
        "",
        "| Deal | Code | Preuve |",
        "| --- | --- | --- |",
    ]
    for r in sorted(anomalies, key=lambda x: (x["code"], x["deal_id"])):
        lines.append(f"| {r['deal_id']} | {r['code']} | {r['preuve']} |")

    lines += [
        "",
        f"## Leurres ({len(leurres)} ignorer)",
        "",
        "| Deal | Code | Preuve |",
        "| --- | --- | --- |",
    ]
    for r in sorted(leurres, key=lambda x: (x["code"], x["deal_id"])):
        lines.append(f"| {r['deal_id']} | {r['code']} | {r['preuve']} |")

    lines += [
        "",
        "## TODOs",
        "",
        "- TODO: Vérifier les plages téléphoniques réservées à la fiction par l'Arcep. Actuellement en 01 99 00 XX XX.",
        "- TODO: Phase 2 — import.py vers HubSpot, reset.py, tick.py.",
        "- TODO: Ajouter de la saisonnalité (creux août, pics juin/décembre).",
    ]

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
