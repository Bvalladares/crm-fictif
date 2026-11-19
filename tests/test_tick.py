"""Weekly simulation and review against isolated copies of the reference CRM."""

from collections import Counter, defaultdict
from contextlib import redirect_stdout
import csv
from datetime import date, timedelta
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from nova.pipeline import LOST_REASONS, SDR_IDS, STAGES, STAGE_META
from nova.rules import run_all_rules
from nova.texts import get_stage_at_date
import tick


ROOT = Path(__file__).resolve().parents[1]
FILES = ("crm.json", "truth.csv", "facts.json")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_truth(path):
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def copy_reference(directory):
    out = Path(directory) / "out"
    out.mkdir()
    for name in FILES:
        shutil.copyfile(ROOT / "out" / name, out / name)
    return out


def snapshot(out):
    return {path.relative_to(out): path.read_bytes() for path in out.rglob("*")
            if path.is_file()}


def run_ticks(out, weeks):
    with redirect_stdout(io.StringIO()):
        tick.tick(out, 42, weeks)


class TickTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        temporary = TemporaryDirectory()
        cls.addClassCleanup(temporary.cleanup)
        cls.out = copy_reference(temporary.name)
        cls.before = snapshot(cls.out)
        run_ticks(cls.out, 3)
        cls.history = cls.out / "history"
        cls.dates = sorted(path.name for path in cls.history.iterdir())
        cls.states = [cls.history / stamp for stamp in cls.dates[:-1]] + [cls.out]

    def test_truth_and_decoy_constructions_each_week(self):
        for state in self.states[1:]:
            crm = read_json(state / "crm.json")
            as_of = date.fromisoformat(crm["meta"]["as_of"])
            deals = {d["id"]: d for d in crm["deals"]}
            activities = defaultdict(list)
            for a in crm["activities"]:
                activities[a["deal_id"]].append(a)
            with self.subTest(as_of=as_of):
                truth = read_truth(state / "truth.csv")
                actual = Counter((r["deal_id"], r["code"], r["preuve"], r["owner"])
                                 for r in truth if r["attendu"] == "signaler")
                expected = Counter((did, code, proof, deals[did]["owner_id"])
                                   for did, code, proof in run_all_rules(crm))
                self.assertEqual(actual, expected)
                self.assertTrue(25 <= sum(actual.values()) <= 45)
                decoys = [r for r in truth if r["attendu"] == "ignorer"]
                self.assertCountEqual([r["code"] for r in decoys], [f"L{i}" for i in range(1, 7)])
                self.assertEqual(len({r["deal_id"] for r in decoys}), 6)
                for r in decoys:
                    did = r["deal_id"]
                    self.assertNotIn(did, {key[0] for key in actual})
                    d = deals[did]
                    self.assertEqual(d["status"], "open")
                    dates = [(a["type"], tick.day(a["at"])) for a in activities[did]]
                    if r["code"] in ("L1", "L2"):
                        age = (as_of - tick.day(d["stage_entered_at"])).days
                        self.assertGreater(age, 2 * STAGE_META[d["stage"]]["normal_days"])
                        self.assertTrue(any(t == "note" and 0 <= (as_of - at).days < 7
                                            for t, at in dates))
                        self.assertTrue(any(t == "reunion" and at > as_of for t, at in dates))
                    elif r["code"] in ("L3", "L4"):
                        self.assertGreaterEqual(d["amount"], 25000)
                        self.assertEqual(max(at for _, at in dates if at <= as_of),
                                         as_of - timedelta(days=20))
                    elif r["code"] == "L5":
                        self.assertEqual((d["stage"], d["amount"], len(d["contact_ids"])),
                                         ("negociation", 15000, 1))
                    else:
                        self.assertEqual(d["close_date"], as_of.isoformat())

    def test_temporal_coherence_and_closed_deals_each_week(self):
        for old, new in zip(self.states, self.states[1:]):
            before, after = (read_json(state / "crm.json") for state in (old, new))
            start, end = (tick.day(crm["meta"]["as_of"]) for crm in (before, after))
            prior = {d["id"]: d for d in before["deals"]}
            previous_acts = {a["id"]: a for a in before["activities"]}
            deals = {d["id"]: d for d in after["deals"]}
            activities = {a["id"]: a for a in after["activities"]}
            self.assertEqual(len(deals), len(after["deals"]))
            self.assertEqual(len(activities), len(after["activities"]))
            self.assertEqual((end - start).days, 7)
            for did, d in deals.items():
                history = d["stage_history"]
                dates = [tick.day(h["entered_at"]) for h in history]
                self.assertEqual(dates, sorted(dates), did)
                self.assertTrue(tick.day(d["created_at"]) <= dates[0] <= dates[-1] <= end, did)
                self.assertEqual(history[-1], {"stage": d["stage"], "entered_at": d["stage_entered_at"]})
                if did in prior:
                    old_history = prior[did]["stage_history"]
                    if len(old_history) == 1 and tick.day(old_history[0]["entered_at"]) > start:
                        self.assertEqual(history[0], {"stage": old_history[0]["stage"],
                                                      "entered_at": d["created_at"]}, did)
                    else:
                        self.assertEqual(history[:len(old_history)], old_history, did)
                    if len(history) > len(old_history):
                        self.assertGreater(dates[-1], start)
                if did in prior and prior[did]["status"] != "open":
                    self.assertEqual(d, prior[did], did)
                if d["status"] != "open":
                    self.assertEqual(d["close_date"], d["stage_entered_at"])
                    if d["status"] == "lost":
                        self.assertIn(d["lost_reason"], LOST_REASONS)
                    else:
                        self.assertEqual(history[-2]["stage"], "negociation")
            seen_bodies = defaultdict(set)
            for aid, a in activities.items():
                d = deals[a["deal_id"]]
                self.assertNotIn(a["body"], seen_bodies[d["id"]], aid)
                seen_bodies[d["id"]].add(a["body"])
                when = tick.day(a["at"])
                self.assertGreaterEqual(when, tick.day(d["created_at"]), aid)
                if aid not in previous_acts:
                    self.assertGreater(when, start, aid)
                if a != previous_acts.get(aid):
                    stage = get_stage_at_date(d["stage_history"], when)
                    body = a["body"].lower()
                    if stage in STAGES[:4]:
                        self.assertNotIn("contrat", body, aid)
                        self.assertNotIn("signature", body, aid)
                    if stage in STAGES[:3]:
                        self.assertNotIn("devis", body, aid)
                        self.assertNotIn("proposition commerciale", body, aid)
                if when > end:
                    self.assertIn(a["type"], ("tache", "reunion"))
                if d["status"] != "open":
                    self.assertLessEqual(when, tick.day(d["close_date"]), aid)
            for aid, a in previous_acts.items():
                if prior[a["deal_id"]]["status"] != "open":
                    self.assertEqual(activities[aid], a, aid)

    def test_volumes_and_journal_each_week(self):
        all_planted = set()
        for index, (old, new) in enumerate(zip(self.states, self.states[1:]), start=1):
            before, after = (read_json(state / "crm.json") for state in (old, new))
            prior = {d["id"]: d for d in before["deals"]}
            start, end = (tick.day(crm["meta"]["as_of"]) for crm in (before, after))
            counts = Counter()
            for d in after["deals"]:
                old_deal = prior.get(d["id"])
                if old_deal is None:
                    counts["created"] += 1
                    self.assertIn(d["owner_id"], SDR_IDS)
                    self.assertEqual(d["stage"], "decouverte")
                elif old_deal["status"] == "open":
                    if d["status"] != "open":
                        counts[d["status"]] += 1
                    elif d["stage"] != old_deal["stage"]:
                        counts["advanced"] += 1
                        self.assertEqual(STAGES.index(d["stage"]), STAGES.index(old_deal["stage"]) + 1)
            previous_ids = {a["id"] for a in before["activities"]}
            for a in after["activities"]:
                if a["id"] not in previous_ids:
                    when = tick.day(a["at"])
                    counts["future" if when > end else "past"] += 1
                    self.assertGreater(when, start)
            for key, low, high in (("created", 4, 7), ("advanced", 8, 12), ("won", 1, 3),
                                   ("lost", 2, 4), ("past", 60, 100), ("future", 10, 20)):
                self.assertTrue(low <= counts[key] <= high, (end, key, counts[key]))
            journal = (self.history / self.dates[index] / "changes.md").read_text(encoding="utf-8")

            def pairs(title):
                section = journal.split("## " + title, 1)[1].split("\n## ", 1)[0]
                return {tuple(line[2:].split(" — ")) for line in section.splitlines()
                        if line.startswith("- ")}

            original, detected = tick.flags(before), tick.flags(after)
            planted = pairs("Anomalies plantées")
            resolved = pairs("Anomalies résolues")
            self.assertTrue(3 <= len(planted) <= 6)
            self.assertEqual(resolved, original - detected)
            self.assertTrue(0.20 <= len(resolved) / len(original) <= 0.45)
            self.assertEqual(pairs("Anomalies apparues naturellement"), detected - original - planted)
            all_planted.update(code for _, code in planted)
        self.assertEqual(all_planted, {f"A{i}" for i in range(1, 10)})

    def test_archive_and_batch_equal_three_separate_ticks(self):
        initial = self.history / self.dates[0]
        for name in FILES:
            self.assertEqual((initial / name).read_bytes(), self.before[Path(name)])
        with TemporaryDirectory() as directory:
            out = copy_reference(directory)
            for _ in range(3):
                run_ticks(out, 1)
            self.assertEqual(snapshot(out), snapshot(self.out))

    def test_retry_does_not_replace_archive_or_repeat_week(self):
        with TemporaryDirectory() as directory, TemporaryDirectory() as comparison:
            out = copy_reference(directory)
            expected = copy_reference(comparison)
            run_ticks(expected, 1)
            original_write = tick.atomic_write

            def interrupt(path, data):
                if path == out / "crm.json":
                    raise OSError("interruption simulée")
                original_write(path, data)

            with patch("tick.atomic_write", side_effect=interrupt):
                with self.assertRaisesRegex(OSError, "interruption simulée"):
                    run_ticks(out, 1)
            run_ticks(out, 1)
            self.assertEqual(snapshot(out), snapshot(expected))

    def test_complete_review_chain_each_week(self):
        with TemporaryDirectory() as directory:
            out = copy_reference(directory)
            env = {**os.environ, "PYTHONPATH": str(ROOT)}
            for _ in range(3):
                run_ticks(out, 1)
                for module in ("review.facts", "review.render_raw", "review.evaluate"):
                    command = [sys.executable, "-m", module]
                    if module == "review.evaluate":
                        command.append("out/review_raw.md")
                    subprocess.run(command, cwd=directory, env=env, check=True, capture_output=True)
                score = read_json(out / "eval_review_raw.json")
                self.assertTrue(score["pass"], score)
                self.assertEqual(score["recall"], 1)
                self.assertEqual(score["invented_numbers"], 0)
                self.assertEqual(score["false_leurres"], 0)
