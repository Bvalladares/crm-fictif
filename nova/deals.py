"""
Deal generation for Atelier Nova CRM.
Generates open, won, and lost deals with realistic stage histories.
Ensures clean deals don't accidentally trigger anomaly rules.
"""

import math
import datetime

from .pipeline import STAGES, STAGE_META, LOST_REASONS, AE_IDS, SDR_IDS


HISTORY_START = datetime.date(2025, 5, 1)

# Owner weights for deal assignment
OWNER_DEAL_WEIGHTS = {
    "ae1": 1.5,
    "ae2": 1.0,
    "ae3": 1.0,
    "ae4": 0.7,
    "ae5": 1.0,
}


def log_normal_amount(rng, segment):
    """
    Generate deal amount using log-normal distribution.
    Median 12000, bounds 3000-60000, rounded to 500.
    Strategic accounts: 30000-60000.
    """
    if segment == "strategique":
        lo, hi = 30000, 60000
        log_lo = math.log(lo)
        log_hi = math.log(hi)
        log_val = rng.uniform(log_lo, log_hi)
        amount = math.exp(log_val)
    else:
        mu = math.log(12000)
        sigma = 0.7
        u1 = rng.random()
        u2 = rng.random()
        z = math.sqrt(-2 * math.log(max(u1, 1e-10))) * math.cos(2 * math.pi * u2)
        log_val = mu + sigma * z
        amount = math.exp(log_val)
        amount = max(3000.0, min(60000.0, amount))

    amount = round(amount / 500) * 500
    amount = max(3000, min(60000, amount))
    return int(amount)


def gen_stage_history(rng, start_date, current_stage, as_of):
    """
    Generate stage history from start_date to current_stage.
    Returns list of {stage, entered_at} dicts.
    Ensures entries are monotonically increasing.
    """
    history = []
    current_date = start_date

    for stage in STAGES:
        entered_at = current_date
        history.append({"stage": stage, "entered_at": entered_at.isoformat()})

        if stage == current_stage:
            break

        normal_days = STAGE_META[stage]["normal_days"]
        days_spent = rng.randint(max(1, int(normal_days * 0.5)), int(normal_days * 1.3))
        current_date = current_date + datetime.timedelta(days=days_spent)
        if current_date >= as_of:
            current_date = as_of - datetime.timedelta(days=1)

    return history


def _stage_index(stage):
    return STAGES.index(stage) if stage in STAGES else -1


def _total_min_days_to_stage(target_stage):
    """Minimum days to reach target_stage from start."""
    total = 0
    for s in STAGES:
        if s == target_stage:
            break
        total += max(1, int(STAGE_META[s]["normal_days"] * 0.5))
    return total


def gen_deals(rng, companies, contacts_by_company, as_of,
              n_open=70, n_won=70, n_lost=120):
    """
    Generate all deals: open, won, and lost.
    Clean open deals are designed to NOT trigger any anomaly rules.
    """
    deals = []
    companies_sorted = sorted(companies, key=lambda c: c["id"])

    def pick_ae():
        weights = [OWNER_DEAL_WEIGHTS[ae] for ae in AE_IDS]
        total = sum(weights)
        r = rng.random() * total
        cumul = 0
        for ae, w in zip(AE_IDS, weights):
            cumul += w
            if r <= cumul:
                return ae
        return AE_IDS[-1]

    def pick_contacts(company_id, min_c=1, max_c=3):
        pool = contacts_by_company.get(company_id, [])
        if not pool:
            return []
        n = min(rng.randint(min_c, max_c), len(pool))
        return [c["id"] for c in rng.sample(pool, n)]

    # Legal-form tokens to strip from company names
    _LEGAL = {"SAS", "SARL", "SA", "SNC", "SCI", "EURL", "SASU", "GIE",
              "SE", "SCOP", "SCP", "SELARL", "LTD", "GMBH", "NV", "BV",
              "&", "ET", "AND"}

    def _co_short(company_name):
        """Return 1-2 significant words from company_name, stripped of legal forms."""
        words = []
        for w in company_name.split():
            if w.startswith("("):
                break
            if w.upper() not in _LEGAL:
                words.append(w)
        return words[:2] if words else company_name.split()[:1]

    def make_deal_name(company_name, stage=None, status=None):
        """
        Format: [Nom court entreprise] – [objet]
        Objects: Planification terrain, Licence Nova, Déploiement multi-sites,
                 Pilote agence, Extension utilisateurs (won only).
        Casing and abbreviations vary as a salesperson would type them.
        No "Mission" prefix, no internal IDs.
        """
        # --- Company fragment ---
        sig = _co_short(company_name)
        n_words = rng.choice([1, 1, 2, 2])
        sig = sig[:min(n_words, len(sig))]

        style = rng.choice(["orig", "orig", "title", "abbrev"])
        if style == "title":
            short_co = " ".join(w.capitalize() for w in sig)
        elif style == "abbrev" and len(sig) > 1:
            short_co = "".join(w[0].upper() for w in sig)
        else:
            short_co = " ".join(sig)   # keep original casing (usually caps for real data)

        # --- Object theme ---
        OBJECTS = [
            # each tuple: (formal, abbrev, upper, lower)
            ("Planification terrain", "Planif terrain",    "PLANIF TERRAIN",        "planif. terrain"),
            ("Licence Nova",          "Licence nova",       "LIC. NOVA",             "licence nova"),
            ("Déploiement multi-sites","Déploiement MS",   "DEPLOY MULTI-SITES",    "deploy multi-sites"),
            ("Pilote agence",         "Pilote agences",     "PILOTE AGENCE",         "pilote agence"),
        ]
        if status == "won":
            OBJECTS = OBJECTS + [
                ("Extension utilisateurs", "Ext. utilisateurs", "EXTENSION USERS", "extension utilisateurs"),
            ]

        variants = rng.choice(OBJECTS)
        obj = rng.choice(variants)

        sep = rng.choice([" – ", " – ", " - "])
        return f"{short_co}{sep}{obj}"

    # --- Open deals ---
    # Clean open deals must NOT trigger:
    # A1: days_in_stage <= 2 * normal_days
    # A2: must have a future tache or reunion
    # A3: close_date >= as_of
    # A4: if amount >= 25000, last activity <= 21 days ago
    # A5: if stage >= proposition, amount not null/0
    # A6: close_date not in as_of month if stage is decouverte/qualification
    # A7: if stage=negociation and amount>=20000, have >= 2 contacts
    # A8: if stage=negociation, must have meeting during demo period
    # A9: no duplicate name with same company

    for i in range(n_open):
        company = rng.choice(companies_sorted)
        cid = company["id"]
        ae = pick_ae()

        stage_weights = [4, 3, 2, 2, 1]
        stage = rng.choices(STAGES, weights=stage_weights, k=1)[0]

        # created_at must be old enough to build full history to current stage
        min_days_needed = _total_min_days_to_stage(stage) + 5
        days_range = (as_of - HISTORY_START).days
        min_days_ago = max(min_days_needed, 10)
        max_days_ago = max(min_days_ago + 1, min(days_range, 300))

        created_days_ago = rng.randint(min_days_ago, max_days_ago)
        created_at = as_of - datetime.timedelta(days=created_days_ago)
        if created_at < HISTORY_START:
            created_at = HISTORY_START

        stage_history = gen_stage_history(rng, created_at, stage, as_of)

        # Ensure stage entered_at is recent enough to avoid accidental A1
        stage_entered = datetime.date.fromisoformat(stage_history[-1]["entered_at"])
        normal_days = STAGE_META[stage]["normal_days"]
        days_in_stage = (as_of - stage_entered).days

        # If accidentally stagnant, shorten time in stage
        if days_in_stage > int(normal_days * 1.8):
            new_entered = as_of - datetime.timedelta(days=rng.randint(1, int(normal_days * 1.5)))
            stage_history[-1]["entered_at"] = new_entered.isoformat()
            stage_entered = new_entered

        # Amount: avoid A5 and A7 triggers
        if stage in ("proposition", "negociation"):
            # Must have amount
            amount = log_normal_amount(rng, company["segment"])
            # Ensure not accidentally A7: if negociation and amount>=20000, need 2+ contacts
            if stage == "negociation" and amount >= 20000:
                contact_ids = pick_contacts(cid, min_c=2, max_c=3)
                if len(contact_ids) < 2:
                    # Not enough contacts — reduce amount below threshold
                    amount = rng.choice([10000, 12000, 15000, 18000])
            else:
                contact_ids = pick_contacts(cid, 1, 3)
        else:
            amount = log_normal_amount(rng, company["segment"])
            contact_ids = pick_contacts(cid, 1, 3)

        # For A8: if negociation, ensure stage history has demo stage
        # (This is handled in anomalies.py for anomaly deals, clean deals get proper history)

        # close_date: avoid A3 (past) and A6 (this month if decouverte/qualification)
        # close_date must be >= as_of for open deals
        # For A6 avoidance: if stage is decouverte/qualification, don't close this month
        if stage in ("decouverte", "qualification"):
            # Close date next month or later
            next_month = as_of.replace(day=1)
            if next_month.month == 12:
                next_month = next_month.replace(year=next_month.year + 1, month=1)
            else:
                next_month = next_month.replace(month=next_month.month + 1)
            delta = rng.randint(0, 90)
            close_date = next_month + datetime.timedelta(days=delta)
        else:
            # Future close date, at least as_of or later
            delta = rng.randint(1, 90)
            close_date = as_of + datetime.timedelta(days=delta)

        deals.append({
            "company_id": cid,
            "contact_ids": contact_ids,
            "owner_id": ae,
            "name": make_deal_name(company["name"], stage=stage, status="open"),
            "amount": amount,
            "stage": stage,
            "stage_entered_at": stage_history[-1]["entered_at"],
            "created_at": created_at.isoformat(),
            "close_date": close_date.isoformat(),
            "lost_reason": None,
            "stage_history": stage_history,
            "status": "open",
        })

    # --- Won deals ---
    for i in range(n_won):
        company = rng.choice(companies_sorted)
        cid = company["id"]
        ae = pick_ae()
        if rng.random() < 0.3:
            ae = "ae1"

        days_range = (as_of - HISTORY_START).days
        min_needed = _total_min_days_to_stage("negociation") + 15
        created_days_ago = rng.randint(min_needed, min(days_range, 400))
        created_at = as_of - datetime.timedelta(days=created_days_ago)
        if created_at < HISTORY_START:
            created_at = HISTORY_START

        history = []
        cur_date = created_at
        for stage in STAGES:
            history.append({"stage": stage, "entered_at": cur_date.isoformat()})
            normal_days = STAGE_META[stage]["normal_days"]
            days_spent = rng.randint(max(1, int(normal_days * 0.5)), int(normal_days * 1.2))
            cur_date = cur_date + datetime.timedelta(days=days_spent)

        gagne_date = cur_date
        if gagne_date > as_of:
            # Compress the entire history so all dates fit within as_of.
            # Walk backwards: each stage must be strictly before its successor.
            gagne_date = as_of
            prev_ceiling = gagne_date
            for idx in range(len(history) - 1, -1, -1):
                stage_date = datetime.date.fromisoformat(history[idx]["entered_at"])
                latest_allowed = prev_ceiling - datetime.timedelta(days=1)
                if stage_date > latest_allowed:
                    history[idx]["entered_at"] = latest_allowed.isoformat()
                    stage_date = latest_allowed
                prev_ceiling = stage_date

        history.append({"stage": "gagne", "entered_at": gagne_date.isoformat()})
        close_date = gagne_date

        contact_ids = pick_contacts(cid, 1, 3)
        amount = log_normal_amount(rng, company["segment"])

        deals.append({
            "company_id": cid,
            "contact_ids": contact_ids,
            "owner_id": ae,
            "name": make_deal_name(company["name"], stage="gagne", status="won"),
            "amount": amount,
            "stage": "gagne",
            "stage_entered_at": history[-1]["entered_at"],
            "created_at": created_at.isoformat(),
            "close_date": close_date.isoformat(),
            "lost_reason": None,
            "stage_history": history,
            "status": "won",
        })

    # --- Lost deals ---
    for i in range(n_lost):
        company = rng.choice(companies_sorted)
        cid = company["id"]
        ae = pick_ae()
        if rng.random() < 0.25:
            ae = "ae4"

        days_range = (as_of - HISTORY_START).days
        created_days_ago = rng.randint(30, min(days_range, 400))
        created_at = as_of - datetime.timedelta(days=created_days_ago)
        if created_at < HISTORY_START:
            created_at = HISTORY_START

        lost_stage_idx = rng.randint(0, len(STAGES) - 1)
        lost_at_stage = STAGES[lost_stage_idx]

        history = []
        cur_date = created_at
        for stage in STAGES[:lost_stage_idx + 1]:
            history.append({"stage": stage, "entered_at": cur_date.isoformat()})
            if stage == lost_at_stage:
                break
            normal_days = STAGE_META[stage]["normal_days"]
            days_spent = rng.randint(max(1, int(normal_days * 0.5)), int(normal_days * 1.5))
            cur_date = cur_date + datetime.timedelta(days=days_spent)
            if cur_date >= as_of:
                cur_date = as_of - datetime.timedelta(days=1)

        days_to_lose = rng.randint(1, 20)
        lose_date = cur_date + datetime.timedelta(days=days_to_lose)
        if lose_date > as_of:
            lose_date = as_of - datetime.timedelta(days=1)
        # Ensure lose_date > cur_date for monotonicity
        if lose_date <= cur_date:
            lose_date = cur_date + datetime.timedelta(days=1)
        if lose_date > as_of:
            lose_date = as_of

        history.append({"stage": "perdu", "entered_at": lose_date.isoformat()})
        close_date = lose_date

        contact_ids = pick_contacts(cid, 1, 2)
        amount = log_normal_amount(rng, company["segment"])
        lost_reason = rng.choice(LOST_REASONS)

        deals.append({
            "company_id": cid,
            "contact_ids": contact_ids,
            "owner_id": ae,
            "name": make_deal_name(company["name"], stage=lost_at_stage, status="lost"),
            "amount": amount,
            "stage": "perdu",
            "stage_entered_at": history[-1]["entered_at"],
            "created_at": created_at.isoformat(),
            "close_date": close_date.isoformat(),
            "lost_reason": lost_reason,
            "stage_history": history,
            "status": "lost",
        })

    return deals
