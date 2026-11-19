"""
review/render_raw.py — Render facts.json to Markdown. No LLM.

CLI: python3 -m review.render_raw [--facts out/facts.json] [--out out/review_raw.md]
"""

import argparse
import datetime
import json
import os

SEPARATOR = "---DETAIL---"

MONTH_ABBR_FR = {
    1: "janv.", 2: "févr.", 3: "mars", 4: "avr.",
    5: "mai", 6: "juin", 7: "juil.", 8: "août",
    9: "sept.", 10: "oct.", 11: "nov.", 12: "déc.",
}


def _short_date_fr(date_str):
    """Return '6 oct.' style short French date from ISO date string."""
    try:
        d = datetime.date.fromisoformat(date_str[:10])
        return f"{d.day} {MONTH_ABBR_FR[d.month]}"
    except (ValueError, KeyError):
        return date_str


def fmt_amount(n):
    """Format an integer amount with space thousands separator: 51 500 €."""
    if not n:
        return "—"
    return f"{n:,}".replace(",", "\u202f") + "\u202f€"


def _plur(n, singular, plural=None):
    if plural is None:
        plural = singular + "s"
    return singular if n == 1 else plural


def _truncate(text, max_len=72):
    """Truncate text to max_len characters, appending '…' if cut."""
    if len(text) <= max_len:
        return text
    return text[:max_len].rstrip() + "…"


def render(facts):
    as_of = facts["as_of"]
    team = facts["team"]
    totals = facts["totals"]
    patterns = facts.get("patterns", {})
    one_on_one = facts.get("one_on_one", [])

    # Build a lookup: deal_id -> (owner_name, entry)
    deal_lookup = {}
    for owner in facts["by_owner"]:
        for entry in owner["flagged"]:
            deal_lookup[entry["deal_id"]] = (owner["owner_name"], entry)

    def render_last_activity(entry):
        """Return the last-activity line or None. Suppressed when A4 is in codes
        (A4 fact phrase already names the last activity)."""
        if "A4" in entry.get("codes", []):
            return None
        la = entry.get("last_activity")
        if not la:
            return None
        short_date = _short_date_fr(la["date"])
        summary = _truncate(la.get("summary", ""), 72)
        return f"  _{short_date} ({la['type']}) — {summary}_"

    def render_deal_entry(entry, owner_name):
        """Render a single flagged deal block."""
        blk = []
        blk.append(
            f"**{entry['deal_name']}** ({entry['company']}) — {owner_name} — "
            f"{entry['stage']} — {fmt_amount(entry['amount'])}"
        )
        for fact in entry["facts"]:
            blk.append(f"- {fact}")
        la_line = render_last_activity(entry)
        if la_line:
            blk.append(la_line)
        return blk

    # ── MAIN MESSAGE ──────────────────────────────────────────────────────────
    main_lines = []

    # 1. Header
    main_lines.append(f"# Revue pipeline — {as_of} — {team}")
    main_lines.append("")

    # 2. Opening
    n_open = totals["open_deals"]
    n_flagged = totals["flagged_deals"]
    main_lines.append(
        f"{n_open} deals ouverts pour {fmt_amount(totals['open_amount'])} de pipeline. "
        f"{n_flagged} {_plur(n_flagged, 'deal')} "
        f"{'signalé' if n_flagged == 1 else 'signalés'} "
        f"({fmt_amount(totals['flagged_amount'])}) nécessitent une attention."
    )
    main_lines.append("")

    # 3. Priorités — no anomaly codes
    main_lines.append("## Priorités")
    main_lines.append("")
    for did in facts["priorities"]:
        if did in deal_lookup:
            owner_name, entry = deal_lookup[did]
            key_fact = entry["facts"][0] if entry["facts"] else ""
            main_lines.append(
                f"**{entry['deal_name']}** ({entry['company']}) — {entry['stage']} — "
                f"{fmt_amount(entry['amount'])}"
            )
            if key_fact:
                main_lines.append(f"- {key_fact}")
            main_lines.append("")

    # 4. Tendances
    main_lines.append("## Tendances")
    main_lines.append("")
    by_code = patterns.get("by_code", {})
    multi = patterns.get("multi_anomaly_deals", 0)
    a2_late = patterns.get("a2_in_late_stages", 0)
    a3_avg = patterns.get("a3_overdue_days_avg", 0)
    a5a7 = patterns.get("a5_a7_combined", 0)
    contract_cases = patterns.get("contract_mention_no_amount", [])
    n_contract = len(contract_cases) if isinstance(contract_cases, list) else 0

    trend_bullets = []
    if n_contract > 0:
        trend_bullets.append(
            f"• {n_contract} {_plur(n_contract, 'deal')} en phase avancée : "
            "activité mentionnant un contrat ou devis, montant absent"
        )
    if a5a7 > 0:
        trend_bullets.append(
            f"• {a5a7} {_plur(a5a7, 'deal')} sans montant en Négociation avec un seul interlocuteur"
        )
    if a2_late > 0:
        a2_total = by_code.get("A2", 0)
        trend_bullets.append(
            f"• {a2_total} {_plur(a2_total, 'deal')} sans prochaine tâche planifiée, "
            f"dont {a2_late} en Proposition ou Négociation"
        )
    elif by_code.get("A2", 0) > 0:
        a2_total = by_code["A2"]
        trend_bullets.append(
            f"• {a2_total} {_plur(a2_total, 'deal')} sans prochaine tâche planifiée"
        )
    if by_code.get("A3", 0) > 0:
        a3_total = by_code["A3"]
        bullet = f"• {a3_total} {_plur(a3_total, 'deal')} avec date de clôture dépassée"
        if a3_avg > 0:
            bullet += f" (retard moyen {a3_avg} j)"
        trend_bullets.append(bullet)
    if multi > 0:
        trend_bullets.append(
            f"• {multi} {_plur(multi, 'deal')} "
            f"{'cumule' if multi == 1 else 'cumulent'} deux alertes ou plus"
        )
    if by_code.get("A1", 0) > 0 and len(trend_bullets) < 3:
        a1_total = by_code["A1"]
        trend_bullets.append(
            f"• {a1_total} {_plur(a1_total, 'deal')} "
            f"bloqué{'' if a1_total == 1 else 's'} à la même étape trop longtemps"
        )
    for bullet in trend_bullets[:3]:
        main_lines.append(bullet)
    main_lines.append("")

    # 5. Résumé par AE
    main_lines.append("## Résumé par AE")
    main_lines.append("")
    patterns_by_owner = patterns.get("by_owner", {})
    for ow in facts["by_owner"]:
        oid = ow["owner_id"]
        stats = patterns_by_owner.get(oid, {})
        n_flagged_ow = stats.get("flagged", len(ow["flagged"]))
        flagged_amt = stats.get("flagged_amount", sum(e["amount"] for e in ow["flagged"]))
        adj = "signalé" if n_flagged_ow == 1 else "signalés"
        main_lines.append(
            f"- {ow['owner_name']} : {n_flagged_ow} {_plur(n_flagged_ow, 'deal')} "
            f"{adj} ({fmt_amount(flagged_amt)})"
        )
    main_lines.append("")

    # 6. Questions pour vos 1:1
    main_lines.append("## Questions pour vos 1:1")
    main_lines.append("")
    # Concentration note
    concentrations = patterns.get("concentrations_ae", {})
    for owner_name, cnt in concentrations.items():
        main_lines.append(
            f"_{owner_name} porte {cnt} des 3 priorités._"
        )
    if concentrations:
        main_lines.append("")
    for item in one_on_one:
        main_lines.append(f"- {item['question']}")
    main_lines.append("")

    # ── DETAIL SECTION ────────────────────────────────────────────────────────
    detail_lines = []

    detail_lines.append("## Détail par AE")
    detail_lines.append("")
    for owner in facts["by_owner"]:
        detail_lines.append(f"### {owner['owner_name']}")
        detail_lines.append("")
        for entry in owner["flagged"]:
            detail_lines.extend(render_deal_entry(entry, owner["owner_name"]))
            detail_lines.append("")

    detail_lines.append("## Vus, pas inquiétants")
    detail_lines.append("")
    for excused in facts.get("excused", []):
        detail_lines.append(
            f"- {excused['deal_name']} ({excused['company']}, {excused['owner_name']}) — {excused['why']}"
        )
    detail_lines.append("")

    main_text = "\n".join(main_lines)
    detail_text = "\n".join(detail_lines)

    return f"{main_text}\n{SEPARATOR}\n\n{detail_text}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--facts", default="out/facts.json")
    parser.add_argument("--out", default="out/review_raw.md")
    args = parser.parse_args()

    with open(args.facts, encoding="utf-8") as f:
        facts = json.load(f)

    md = render(facts)

    with open(args.out, "w", encoding="utf-8") as f:
        f.write(md)

    print(f"Written {args.out}")


if __name__ == "__main__":
    main()
