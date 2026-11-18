"""
Activity generation for Atelier Nova CRM.
Types: appel, email, reunion, note, tache
Activities can be in the past or future (future = tache/reunion only).
Target: ~4000 activities total (5-25 per deal, denser in demo/negotiation).
"""

import datetime

from .texts import pick_subject, pick_body

ACTIVITY_TYPES_PAST = ["appel", "email", "reunion", "note"]
ACTIVITY_TYPES_ALL = ["appel", "email", "reunion", "note", "tache"]

# ae5 logs 3x fewer activities
AE5_FACTOR = 1.0 / 3.0

# Base activity counts per stage (targeting ~4000 total for 260 deals)
# 260 deals × avg ~18 activities = ~4680; ae5 reduces ~20 deals by 2/3
STAGE_DENSITY = {
    "decouverte":    (12, 22),
    "qualification": (14, 24),
    "demo":          (20, 32),
    "proposition":   (16, 28),
    "negociation":   (22, 36),
    "gagne":         (12, 22),
    "perdu":         (10, 16),
}


def gen_activities_for_deal(rng, deal, contacts_by_company, as_of,
                             force_future_meeting=False,
                             force_future_tache=False,
                             force_recent_note=False,
                             skip_demo_meeting=False):
    """
    Generate activities for a single deal.

    Parameters:
    - force_future_meeting: add a future reunion (for A2 fix and leurres)
    - force_future_tache: add a future tache (for clean deals A2 avoidance)
    - force_recent_note: add a note within 7 days of as_of (for leurres L1/L2)
    - skip_demo_meeting: do NOT add any meeting during demo stage period (for A8)
    """
    activities = []
    owner_id = deal["owner_id"]

    stage = deal["stage"]
    min_a, max_a = STAGE_DENSITY.get(stage, (6, 12))

    if owner_id == "ae5":
        min_a = max(1, int(min_a * AE5_FACTOR))
        max_a = max(2, int(max_a * AE5_FACTOR))

    n_activities = rng.randint(min_a, max_a)

    created_at = datetime.date.fromisoformat(deal["created_at"])
    stage_history = deal["stage_history"]

    company_id = deal["company_id"]
    contacts = contacts_by_company.get(company_id, [])
    contact_ids_in_deal = deal.get("contact_ids", [])
    deal_contacts = [c for c in contacts if c["id"] in contact_ids_in_deal]
    if not deal_contacts and contacts:
        deal_contacts = contacts[:1]

    def pick_contact():
        if deal_contacts:
            return rng.choice(deal_contacts)["id"]
        return None

    def pick_at_in_range(start_d, end_d):
        """Pick a datetime within a date range, ensuring it's in the past."""
        delta = (end_d - start_d).days
        if delta <= 0:
            delta = 1
        d = start_d + datetime.timedelta(days=rng.randint(0, delta))
        hour = rng.randint(8, 17)
        minute = rng.choice([0, 15, 30, 45])
        return datetime.datetime(d.year, d.month, d.day, hour, minute, 0)

    # Find demo period for A8 check
    demo_start, prop_start = _get_demo_period(stage_history)

    # Generate past activities
    for i in range(n_activities):
        act_type = rng.choice(ACTIVITY_TYPES_PAST)

        end_d = as_of
        start_d = created_at
        at_dt = pick_at_in_range(start_d, end_d)

        # For skip_demo_meeting: skip meetings during demo period
        if skip_demo_meeting and act_type == "reunion":
            if demo_start and prop_start:
                at_date = at_dt.date()
                if demo_start <= at_date < prop_start:
                    act_type = rng.choice(["appel", "email", "note"])

        activities.append({
            "deal_id": deal["id"],
            "contact_id": pick_contact(),
            "owner_id": owner_id,
            "type": act_type,
            "at": at_dt.isoformat(),
            "subject": pick_subject(rng, act_type),
            "body": pick_body(rng, act_type),
        })

    # Force recent note (< 7 days ago, for leurres L1/L2)
    if force_recent_note:
        note_date = as_of - datetime.timedelta(days=rng.randint(1, 6))
        at_dt = datetime.datetime(note_date.year, note_date.month, note_date.day,
                                   rng.randint(9, 17), 0, 0)
        activities.append({
            "deal_id": deal["id"],
            "contact_id": pick_contact(),
            "owner_id": owner_id,
            "type": "note",
            "at": at_dt.isoformat(),
            "subject": "Note de suivi",
            "body": "Client en congés jusqu'au 5/01, RDV calé. Pas d'inquiétude.",
        })

    # Force future meeting (for leurres L1/L2 and clean deals)
    if force_future_meeting:
        future_date = as_of + datetime.timedelta(days=rng.randint(5, 30))
        at_dt = datetime.datetime(future_date.year, future_date.month, future_date.day, 10, 0, 0)
        activities.append({
            "deal_id": deal["id"],
            "contact_id": pick_contact(),
            "owner_id": owner_id,
            "type": "reunion",
            "at": at_dt.isoformat(),
            "subject": "Réunion de suivi",
            "body": f"RDV calé le {future_date.isoformat()}.",
        })

    # Force future tache (for clean deals that need A2 avoidance)
    if force_future_tache:
        future_date = as_of + datetime.timedelta(days=rng.randint(2, 20))
        at_dt = datetime.datetime(future_date.year, future_date.month, future_date.day, 9, 0, 0)
        activities.append({
            "deal_id": deal["id"],
            "contact_id": pick_contact(),
            "owner_id": owner_id,
            "type": "tache",
            "at": at_dt.isoformat(),
            "subject": pick_subject(rng, "tache"),
            "body": pick_body(rng, "tache"),
        })

    return activities


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


def gen_all_activities(rng, deals, contacts_by_company, as_of,
                        anomaly_flags=None):
    """
    Generate activities for all deals.

    anomaly_flags: dict of deal_id -> set of anomaly codes
    """
    if anomaly_flags is None:
        anomaly_flags = {}

    all_activities = []
    as_of_date = as_of if isinstance(as_of, datetime.date) else datetime.date.fromisoformat(as_of)

    for deal in deals:
        did = deal["id"]
        flags = anomaly_flags.get(did, set())

        force_future_meeting = False
        force_future_tache = False
        force_recent_note = False
        skip_demo_meeting = "A8" in flags

        if "L1" in flags or "L2" in flags:
            force_future_meeting = True
            force_recent_note = True
        elif "A2" not in flags and deal["status"] == "open":
            # Clean open deals always get a next step (A2 avoidance)
            if rng.random() < 0.6:
                force_future_meeting = True
            else:
                force_future_tache = True

        acts = gen_activities_for_deal(
            rng, deal, contacts_by_company, as_of_date,
            force_future_meeting=force_future_meeting,
            force_future_tache=force_future_tache,
            force_recent_note=force_recent_note,
            skip_demo_meeting=skip_demo_meeting,
        )
        all_activities.extend(acts)

    return all_activities
