"""Advance the local Atelier Nova CRM by whole weeks."""

import argparse
from collections import defaultdict
import csv
from datetime import date, datetime, timedelta
import fcntl
import io
import json
import os
from pathlib import Path
import random
from tempfile import NamedTemporaryFile

from nova.activities import (
    ACTIVITY_TYPES_PAST, AE5_FACTOR, LOST_REASON_BODIES, STAGE_DENSITY,
    _fill_budget_placeholders, _get_demo_period,
)
from nova.deals import log_normal_amount
from nova.pipeline import AE_IDS, LOST_REASONS, SDR_IDS, STAGES, STAGE_META
from nova.rules import get_activities_by_deal, run_all_rules
from nova.texts import get_stage_at_date, pick_template


TRUTH_FIELDS = ("deal_id", "code", "attendu", "preuve", "owner")
ONE_DAY = timedelta(days=1)


def day(value):
    return date.fromisoformat(value[:10])


def next_id(rows):
    return max((int(row["id"].split("-")[1]) for row in rows), default=0) + 1


def flags(crm):
    return {(deal_id, code) for deal_id, code, _ in run_all_rules(crm)}


class Week:
    def __init__(self, crm, seed):
        self.crm = crm
        self.start = day(crm["meta"]["as_of"])
        self.end = self.start + timedelta(days=7)
        number = crm["meta"].get("tick_week", 0) + 1
        self.rng = random.Random(seed + number)
        self.before = flags(crm)
        crm["meta"].update(as_of=self.end.isoformat(), tick_week=number)
        self.deals = {deal["id"]: deal for deal in crm["deals"]}
        self.companies = {company["id"]: company for company in crm["companies"]}
        self.contacts = defaultdict(list)
        for contact in crm["contacts"]:
            self.contacts[contact["company_id"]].append(contact["id"])
        self.activities = get_activities_by_deal(crm["activities"])
        self.deal_id = next_id(crm["deals"])
        self.activity_id = next_id(crm["activities"])
        self.first_new_activity = self.activity_id
        self.past = 0
        self.future = 0
        self.events = defaultdict(list)
        self.decoys = {}
        self.planted = set()

    def repair_initial_stage_dates(self):
        # A legacy duplicate has a future initial stage despite past activity.
        # A one-stage history starts at creation, which supplies the date.
        for deal in self.open_deals():
            history = deal["stage_history"]
            entered = deal["stage_entered_at"]
            if len(history) == 1 and day(entered) > self.start:
                created = deal["created_at"]
                deal["stage_entered_at"] = history[0]["entered_at"] = created
                self.events["Dates d’entrée en étape rectifiées"].append(
                    f"{deal['id']} — {entered} → {created}"
                )

    def open_deals(self):
        return [deal for deal in self.deals.values() if deal["status"] == "open"]

    def week_date(self):
        return self.start + timedelta(days=self.rng.randint(1, 7))

    def amount(self, deal):
        return log_normal_amount(self.rng, self.companies[deal["company_id"]]["segment"])

    def activities_for(self, deal):
        return self.activities.setdefault(deal["id"], [])

    def activity_body(self, deal, body, replacing=None):
        body = _fill_budget_placeholders(body, deal)
        used = {a["body"] for a in self.activities_for(deal) if a is not replacing}
        variant = body
        counter = 1
        while variant in used:
            variant = f"{body} (cf. suivi {counter})"
            counter += 1
        return variant

    def add_activity(self, deal, kind, when, text=None):
        activities = self.activities_for(deal)
        if text is None:
            stage = get_stage_at_date(deal["stage_history"], when)
            text = pick_template(
                self.rng, kind, stage, {activity["body"] for activity in activities}
            )
        subject, body = text
        activity = {
            "id": f"A-{self.activity_id:04d}",
            "deal_id": deal["id"],
            "contact_id": self.rng.choice(deal["contact_ids"]),
            "owner_id": deal["owner_id"],
            "type": kind,
            "at": datetime.combine(when, datetime.min.time()).replace(
                hour=18 if deal["status"] != "open" else self.rng.randint(9, 16)
            ).isoformat(),
            "subject": subject,
            "body": self.activity_body(deal, body),
        }
        self.activity_id += 1
        activities.append(activity)
        self.crm["activities"].append(activity)
        if when > self.end:
            self.future += 1
        else:
            self.past += 1

    def cancel_activities(self, deal, cancelled):
        activities = self.activities_for(deal)
        activities[:] = [entry for entry in activities if entry["id"] not in cancelled]
        self.crm["activities"][:] = [
            entry for entry in self.crm["activities"] if entry["id"] not in cancelled
        ]

    def schedule(self, deal, kind="tache"):
        when = self.end + timedelta(days=self.rng.randint(5, 24))
        self.add_activity(deal, kind, when)
        return when

    def create_deals(self):
        occupied = {deal["company_id"] for deal in self.open_deals()}
        companies = [cid for cid in self.companies if cid not in occupied and self.contacts[cid]]
        for cid in self.rng.sample(companies, self.rng.randint(4, 7)):
            when = self.week_date()
            deal_id = f"D-{self.deal_id:04d}"
            self.deal_id += 1
            company = self.companies[cid]
            name = company.get("display_name", company["name"])
            deal = {
                "id": deal_id, "company_id": cid,
                "contact_ids": [self.rng.choice(self.contacts[cid])],
                "owner_id": self.rng.choice(SDR_IDS),
                "name": f"{name} — Planification des interventions ({deal_id})",
                "status": "open", "stage": "decouverte",
                "created_at": when.isoformat(), "stage_entered_at": when.isoformat(),
                "stage_history": [{"stage": "decouverte", "entered_at": when.isoformat()}],
                "close_date": (when + timedelta(days=self.rng.randint(45, 90))).isoformat(),
                "lost_reason": None,
            }
            deal["amount"] = self.amount(deal)
            self.deals[deal_id] = deal
            self.crm["deals"].append(deal)
            self.add_activity(deal, "appel", when)
            self.schedule(deal)
            self.events["Deals créés"].append(f"{deal_id} — {deal['owner_id']}, {when}")

    def transition(self, deal, stage, when):
        old_stage = deal["stage"]
        deal.update(stage=stage, stage_entered_at=when.isoformat())
        deal["stage_history"].append({"stage": stage, "entered_at": when.isoformat()})
        if deal["owner_id"] in SDR_IDS and stage == "qualification":
            deal["owner_id"] = self.rng.choice(AE_IDS)
        if stage in ("gagne", "perdu"):
            self.cancel_activities(deal, {entry["id"] for entry in self.activities_for(deal)
                                          if day(entry["at"]) > when})
            won = stage == "gagne"
            reason = None if won else self.rng.choice(LOST_REASONS)
            deal.update(status="won" if won else "lost", close_date=when.isoformat(),
                        lost_reason=reason)
            if not deal["amount"]:
                deal["amount"] = self.amount(deal)
            note = ("Deal gagné", "Contrat signé.") if won else (
                "Deal perdu", LOST_REASON_BODIES[reason]
            )
            self.add_activity(deal, "note", when, note)
            label = "Deals gagnés" if won else "Deals perdus"
            detail = deal["owner_id"] if won else f"{deal['owner_id']}, {reason}"
        else:
            label = "Deals avancés"
            detail = f"{old_stage} → {stage}, {deal['owner_id']}"
        self.events[label].append(f"{deal['id']} — {detail}, {when}")

    def missing_demo(self, deal):
        start, end = _get_demo_period(deal["stage_history"])
        return start is None or not any(
            a["type"] == "reunion" and start <= day(a["at"]) < end
            for a in self.activities_for(deal)
        )

    def evolve(self, previous_decoys):
        pool = self.open_deals()
        plant_a8 = self.crm["meta"]["tick_week"] % 3 == 1
        # A deal moves at most once per week. Prefer the existing pipeline for
        # transitions so new deals start the next week in Découverte.
        for event, count in (("gagne", self.rng.randint(1, 3)),
                             ("perdu", self.rng.randint(2, 4)),
                             ("avance", self.rng.randint(8, 12))):
            for _ in range(count):
                candidates = [
                    deal for deal in pool
                    if deal["id"] not in previous_decoys
                    and (event != "gagne" or deal["stage"] == "negociation")
                    and (event != "avance" or deal["stage"] != "negociation")
                ]
                if event == "gagne":
                    weights = [{"ae1": 1.5, "ae4": 0.35}.get(d["owner_id"], 1)
                               for d in candidates]
                elif event == "perdu":
                    weights = [2 if d["owner_id"] == "ae4" else 1 for d in candidates]
                else:
                    weights = [0.45 if d["owner_id"] == "ae4" else 1 for d in candidates]
                if not candidates:
                    break
                deal = self.rng.choices(candidates, weights=weights)[0]
                if event == "avance" and plant_a8:
                    missing = [d for d in candidates if d["stage"] == "proposition"
                               and self.missing_demo(d)]
                    if missing:
                        deal = self.rng.choice(missing)
                        self.planted.add((deal["id"], "A8"))
                        plant_a8 = False
                pool.remove(deal)
                when = self.week_date()
                stage = event
                if event == "avance":
                    stage = STAGES[STAGES.index(deal["stage"]) + 1]
                    if deal["stage"] == "demo":
                        demo_start = day(deal["stage_entered_at"])
                        if not any(a["type"] == "reunion" and demo_start <= day(a["at"]) < when
                                   for a in self.activities_for(deal)):
                            when = max(when, self.start + 2 * ONE_DAY)
                            self.add_activity(deal, "reunion", when - ONE_DAY)
                self.transition(deal, stage, when)
        self.create_deals()

    def last_activity(self, deal):
        return max(
            (activity for activity in self.activities_for(deal) if day(activity["at"]) <= self.end),
            key=lambda activity: activity["at"], default=None,
        )

    def long_stage(self, deal):
        normal = STAGE_META[deal["stage"]]["normal_days"]
        return (self.end - day(deal["stage_entered_at"])).days > 2 * normal

    def push_close_date(self, deal):
        deal["close_date"] = (self.end + timedelta(days=45)).isoformat()

    def decoy(self, code, deal, proof):
        self.decoys[deal["id"]] = (code, proof)

    def plant_decoys(self, previous_decoys):
        # Keeping a still-valid example is preferable to overwriting its history.
        pool = self.open_deals()
        self.rng.shuffle(pool)

        def available():
            return [d for d in pool if d["id"] not in self.decoys]

        def compatible(current, deal, repairable):
            return all(did != deal["id"] or code in repairable for did, code in current)

        def preferred(deal, code):
            return previous_decoys.get(deal["id"]) == code

        for code in ("L1", "L2"):
            current = flags(self.crm)
            candidates = [d for d in available() if self.long_stage(d)
                          and compatible(current, d, {"A1", "A2", "A3", "A4", "A6"})]
            deal = min(candidates, key=lambda d: not preferred(d, code))
            if any((deal["id"], flag) in current for flag in ("A3", "A6")):
                self.push_close_date(deal)
            when = self.schedule(deal, "reunion")
            self.add_activity(deal, "note", self.end, (
                "Note de suivi", f"Interlocuteur indisponible cette semaine, RDV calé le {when:%d/%m}."
            ))
            self.decoy(code, deal, f"Long en {STAGE_META[deal['stage']]['label']}, note du {self.end} et RDV le {when}")

        for code in ("L3", "L4"):
            cutoff = self.end - timedelta(days=20)
            current = flags(self.crm)
            candidates = []
            for deal in available():
                latest = self.last_activity(deal)
                if latest is None or day(latest["at"]) > cutoff:
                    continue
                if any(did == deal["id"] and flag not in {"A2", "A3", "A4", "A6"}
                       for did, flag in current):
                    continue
                if deal["stage"] == "negociation" and len(deal["contact_ids"]) == 1:
                    continue
                if get_stage_at_date(deal["stage_history"], cutoff) != get_stage_at_date(
                        deal["stage_history"], latest["at"]):
                    continue
                candidates.append((deal, latest))
            deal, latest = min(candidates, key=lambda pair: (
                (cutoff - day(pair[1]["at"])).days, not preferred(pair[0], code)
            ))
            if day(latest["at"]) != cutoff:
                # Correct the date of an existing entry in the same stage.
                # The exact 20-day boundary can precede the simulated week.
                self.events["Dates de journal rectifiées pour les leurres"].append(
                    f"{deal['id']} / {latest['id']} — {day(latest['at'])} → {cutoff}"
                )
                latest["at"] = cutoff.isoformat() + latest["at"][10:]
            if (deal["id"], "A2") in current:
                self.schedule(deal)
            if any((deal["id"], flag) in current for flag in ("A3", "A6")):
                self.push_close_date(deal)
            deal["amount"] = max(deal["amount"] or 0, 25000)
            self.decoy(code, deal, f"Deal de {deal['amount']} € ; dernière activité le {cutoff}, il y a 20 j")

        current = flags(self.crm)
        deal = min(
            (d for d in available() if d["stage"] == "negociation"
             and compatible(current, d, {"A1", "A2", "A3", "A4", "A5", "A7"})),
            key=lambda d: (not preferred(d, "L5"), len(d["contact_ids"]) != 1),
        )
        deal["amount"] = 15000
        deal["contact_ids"] = deal["contact_ids"][:1]
        for flag in ("A1", "A2", "A3"):
            if (deal["id"], flag) in flags(self.crm):
                self.repair(deal, flag)
        self.decoy("L5", deal, "Négociation avec un seul interlocuteur, montant de 15 000 €")

        current = flags(self.crm)
        deal = min(
            (d for d in available() if d["stage"] in STAGES[2:]
             and compatible(current, d, {"A3"})),
            key=lambda d: not preferred(d, "L6"),
        )
        deal["close_date"] = self.end.isoformat()
        self.decoy("L6", deal, f"Date de clôture égale au jour de revue ({self.end})")

    def repair(self, deal, code):
        if code == "A1":
            meeting = next((a for a in self.activities_for(deal)
                            if a["type"] == "reunion" and day(a["at"]) > self.end), None)
            if meeting is None and self.future >= 20:
                return
            when = day(meeting["at"]) if meeting else self.schedule(deal, "reunion")
            self.add_activity(deal, "note", self.end, (
                "Note de suivi", f"Client en déplacement, reprise prévue le {when:%d/%m}."
            ))
        elif code == "A2":
            if self.future < 20:
                self.schedule(deal)
        elif code in ("A3", "A6"):
            self.push_close_date(deal)
        elif code == "A4":
            self.add_activity(deal, "appel", self.end)
        elif code == "A5":
            deal["amount"] = self.amount(deal)
        elif code == "A7":
            others = [cid for cid in self.contacts[deal["company_id"]]
                      if cid not in deal["contact_ids"]]
            if others:
                deal["contact_ids"] = [*deal["contact_ids"], self.rng.choice(others)]

    def repair_anomalies(self):
        target = round(0.30 * len(self.before))
        current = flags(self.crm)
        candidates = sorted(self.before & current)
        self.rng.shuffle(candidates)
        for did, code in candidates:
            if len(self.before - current) >= target:
                break
            if (did, code) in current:
                self.repair(self.deals[did], code)
                current = flags(self.crm)

    def log_activities(self):
        protected = {did for did, (code, _) in self.decoys.items() if code in ("L3", "L4")}
        candidates = [d for d in self.open_deals() if d["id"] not in protected and (d["id"], "A4") not in self.planted]
        weights = [
            (sum(STAGE_DENSITY[d["stage"]]) / 2)
            * (AE5_FACTOR if d["owner_id"] == "ae5" else 1)
            for d in candidates
        ]
        target = self.rng.randint(68, 78)
        while self.past < target:
            deal = self.rng.choices(candidates, weights=weights)[0]
            when = max(self.week_date(), day(deal["created_at"]))
            # Only explicit follow-ups renew an existing stagnation exception.
            kinds = ACTIVITY_TYPES_PAST
            if self.long_stage(deal):
                kinds = [kind for kind in kinds if kind != "note"]
            self.add_activity(deal, self.rng.choice(kinds), when)

    def plant_anomalies(self):
        # Rotate the first choice so rarer opportunities are tried across weeks.
        codes = ["A2", "A5", "A7", "A3", "A6", "A9", "A4", "A1"]
        offset = (self.crm["meta"]["tick_week"] - 1) * 3 % len(codes)
        codes = codes[offset:] + codes[:offset]
        pool = [d for d in self.open_deals() if d["id"] not in self.decoys]
        self.rng.shuffle(pool)
        for code in codes:
            current = flags(self.crm)
            if len(self.planted) >= 4 or len(current) >= 45:
                break
            for deal in pool:
                if (deal["id"], code) in current | self.before:
                    continue
                original = deal.copy()
                if code in ("A1", "A2") and any(did == deal["id"] for did, _ in current):
                    continue
                converted = None
                if code in ("A1", "A2"):
                    future = [a for a in self.activities_for(deal) if day(a["at"]) > self.end]
                    if code == "A1":
                        if not self.long_stage(deal):
                            continue
                        has_task = any(a["type"] == "tache" for a in future)
                        future = [a for a in future if a["type"] == "reunion"]
                    elif self.long_stage(deal):
                        continue
                    if not future or any(int(a["id"].split("-")[1]) >= self.first_new_activity
                                         for a in future):
                        continue
                    if code == "A1" and not has_task:
                        step = future.pop()
                        converted = (step, step.copy())
                        subject, body = pick_template(self.rng, "tache", deal["stage"])
                        step.update(type="tache", subject=subject,
                                    body=self.activity_body(deal, body, replacing=step))
                    self.cancel_activities(deal, {a["id"] for a in future})
                elif code == "A3":
                    if day(deal["created_at"]) >= self.end:
                        continue
                    deal["close_date"] = max(self.start + ONE_DAY, day(deal["created_at"])).isoformat()
                elif code == "A4":
                    deal["amount"] = max(deal["amount"] or 0, 25000)
                elif code == "A5":
                    deal["amount"] = None
                elif code == "A6":
                    deal["close_date"] = self.end.isoformat()
                elif code == "A7":
                    deal["contact_ids"] = deal["contact_ids"][:1]
                elif code == "A9":
                    peer = next((d for d in pool if d is not deal
                                 and d["company_id"] == deal["company_id"]
                                 and not any(did == d["id"] for did, _ in current)), None)
                    if peer is None:
                        continue
                    deal["name"] = f"{peer['name']} — extension {deal['id']}"
                found = flags(self.crm)
                added = found - current
                if (deal["id"], code) in added and not (added & self.before) and all(
                        flag == code for _, flag in added):
                    if (len(added | self.planted) <= 6 and len(found) <= 45
                            and self.planted <= found
                            and all(did not in self.decoys for did, _ in added)):
                        self.planted.update(added)
                        break
                if code in ("A1", "A2"):
                    self.activities_for(deal).extend(future)
                    self.crm["activities"].extend(future)
                if converted:
                    step, prior = converted
                    step.update(prior)
                deal.update(original)

    def postpone_due_step(self, deal):
        due = [entry for entry in self.activities_for(deal)
               if entry["type"] in ("tache", "reunion")
               and self.start < day(entry["at"]) <= self.end]
        if not due:
            return False
        entry = max(due, key=lambda a: (a["type"] == "reunion", a["at"]))
        when = self.end + timedelta(days=self.rng.randint(14, 35))
        subject, body = pick_template(self.rng, entry["type"], deal["stage"])
        entry.update(at=when.isoformat() + entry["at"][10:], subject=subject,
                     body=self.activity_body(deal, body, replacing=entry))
        self.events["Prochaines étapes reportées"].append(
            f"{deal['id']} / {entry['id']} — {when}"
        )
        return True

    def balance_followups(self):
        current = flags(self.crm)
        # At the crossing of a large cohort's stage threshold, prioritize
        # renewing existing meetings and work through newly expired forecasts.
        for code in ("A1", "A3", "A6", "A4", "A7", "A5", "A2"):
            for did, flag in sorted(current - self.before - self.planted):
                if len(current) <= 40:
                    break
                if flag == code and did not in self.decoys:
                    self.repair(self.deals[did], code)
                    current = flags(self.crm)
        for did, code in sorted(current - self.before - self.planted):
            if len(current) <= 39:
                break
            if code == "A2" and (did, code) in current:
                deal = self.deals[did]
                if self.postpone_due_step(deal):
                    if (did, "A1") in current:
                        self.repair(deal, "A1")
                    current = flags(self.crm)
        candidates = [self.deals[did] for did, code in sorted(current - self.planted)
                      if code == "A2"]
        self.rng.shuffle(candidates)
        for deal in candidates:
            if self.future >= 20 or (self.future >= 10 and len(current) <= 40):
                break
            self.schedule(deal)
            current = flags(self.crm)
        pool = [deal for deal in self.open_deals() if deal["id"] not in self.decoys]
        while self.future < 10:
            self.schedule(self.rng.choice(pool))

    def run(self, previous_truth):
        previous_decoys = {r["deal_id"]: r["code"] for r in previous_truth
                           if r["attendu"] == "ignorer"}
        self.repair_initial_stage_dates()
        self.evolve(previous_decoys)
        self.plant_decoys(previous_decoys)
        self.repair_anomalies()
        self.balance_followups()
        self.plant_anomalies()
        self.log_activities()
        if len(self.planted) < 3:
            self.plant_anomalies()
        self.crm["activities"].sort(key=lambda activity: int(activity["id"].split("-")[1]))
        detected = run_all_rules(self.crm)
        after = {(did, code) for did, code, _ in detected}
        if not 25 <= len(detected) <= 45:
            raise ValueError(f"Nombre d'anomalies hors fourchette : {len(detected)}")
        if any(did in self.decoys for did, _ in after):
            raise ValueError("Un leurre déclenche une règle Nova")
        for title, pairs in (
            ("Anomalies résolues", self.before - after),
            ("Anomalies apparues naturellement", after - self.before - self.planted),
            ("Anomalies plantées", after & self.planted),
        ):
            self.events[title] = [f"{did} — {code}" for did, code in sorted(pairs)]
        self.events["Leurres"] = [f"{did} — {code}, {proof}"
                                 for did, (code, proof) in self.decoys.items()]
        rows = [(did, code, "signaler", proof) for did, code, proof in detected]
        rows.extend((did, code, "ignorer", proof) for did, (code, proof) in self.decoys.items())
        truth = [dict(zip(TRUTH_FIELDS, (*row, self.deals[row[0]]["owner_id"])))
                 for row in sorted(rows)]
        return truth

    def journal(self):
        lines = [f"# Semaine du {self.start + ONE_DAY} au {self.end}", "",
                 f"- Activités enregistrées dans la semaine : {self.past}",
                 f"- Tâches et réunions futures créées : {self.future}"]
        for title, entries in self.events.items():
            lines.extend(["", f"## {title} ({len(entries)})", ""])
            lines.extend(f"- {entry}" for entry in entries)
        return "\n".join(lines) + "\n"


def atomic_write(path, data):
    with NamedTemporaryFile(dir=path.parent, delete=False) as temporary:
        temporary.write(data)
        name = temporary.name
    try:
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def archive_file(path, data):
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError(f"Archive existante différente : {path}")
    else:
        atomic_write(path, data)


def tick(out, seed, weeks):
    out = Path(out)
    # Lock the directory itself so concurrent ticks cannot share a starting state.
    directory = os.open(out, os.O_RDONLY)
    try:
        fcntl.flock(directory, fcntl.LOCK_EX)
        for _ in range(weeks):
            crm_bytes = (out / "crm.json").read_bytes()
            week = Week(json.loads(crm_bytes), seed)
            previous = out / "history" / week.start.isoformat()
            following = out / "history" / week.end.isoformat()
            # The CRM is published last. If a write was interrupted, retry from
            # the archived truth, which still belongs to the current CRM date.
            archived_truth = previous / "truth.csv"
            truth_bytes = (archived_truth if archived_truth.exists()
                           else out / "truth.csv").read_bytes()
            rows = week.run(list(csv.DictReader(io.StringIO(truth_bytes.decode("utf-8")))))
            stream = io.StringIO(newline="")
            writer = csv.DictWriter(stream, fieldnames=TRUTH_FIELDS)
            writer.writeheader()
            writer.writerows(rows)

            previous.mkdir(parents=True, exist_ok=True)
            archive_file(previous / "crm.json", crm_bytes)
            archive_file(archived_truth, truth_bytes)
            facts_path = out / "facts.json"
            if facts_path.exists():
                facts = facts_path.read_bytes()
                if json.loads(facts).get("as_of") == week.start.isoformat():
                    archive_file(previous / "facts.json", facts)
            following.mkdir(parents=True, exist_ok=True)
            archive_file(following / "changes.md", week.journal().encode("utf-8"))
            atomic_write(out / "truth.csv", stream.getvalue().encode("utf-8"))
            atomic_write(out / "crm.json",
                         json.dumps(week.crm, ensure_ascii=False, indent=2).encode("utf-8"))
            print(f"{week.end} — {following / 'changes.md'}")
    finally:
        os.close(directory)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--weeks", type=int, default=1)
    args = parser.parse_args()
    if args.weeks < 1:
        parser.error("--weeks doit être supérieur ou égal à 1")
    tick(Path("out"), args.seed, args.weeks)


if __name__ == "__main__":
    main()
