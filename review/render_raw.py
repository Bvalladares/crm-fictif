"""
review/render_raw.py — Render facts.json to Markdown. No LLM.

CLI: python3 -m review.render_raw [--facts out/facts.json] [--out out/review_raw.md]

Output format:
  [main message — ≤250 words]

  ---DETAIL---

  [detail section — full listing, no word limit]
"""

import argparse
import json
import os


SEPARATOR = "---DETAIL---"


def render(facts):
    as_of = facts["as_of"]
    team = facts["team"]
    totals = facts["totals"]
    patterns = facts.get("patterns", {})

    # Build a lookup: deal_id -> (owner_name, entry)
    deal_lookup = {}
    for owner in facts["by_owner"]:
        for entry in owner["flagged"]:
            deal_lookup[entry["deal_id"]] = (owner["owner_name"], entry)

    def render_deal_entry(entry, owner_name):
        """Render a single flagged deal block."""
        blk = []
        codes_str = ", ".join(entry["codes"])
        blk.append(
            f"**{entry['deal_name']}** ({entry['company']}) — {owner_name} — "
            f"{entry['stage']} — {entry['amount']} € — [{codes_str}]"
        )
        for fact in entry["facts"]:
            blk.append(f"- {fact}")
        la = entry.get("last_activity")
        if la:
            blk.append(
                f"  _Dernière activité : {la['date']} ({la['type']}) — {la['summary']}_"
            )
        return blk

    # ── MAIN MESSAGE ──────────────────────────────────────────────────────────
    main_lines = []

    # 1. Header
    main_lines.append(f"# Revue pipeline — {as_of} — {team}")
    main_lines.append("")

    # 2. Opening
    main_lines.append(
        f"{totals['open_deals']} deals ouverts pour {totals['open_amount']} € de pipeline. "
        f"{totals['flagged_deals']} deals signalés ({totals['flagged_amount']} €) nécessitent une attention."
    )
    main_lines.append("")

    # 3. Priorités — 3 priority deals, one key fact each
    main_lines.append("## Priorités")
    main_lines.append("")
    for did in facts["priorities"]:
        if did in deal_lookup:
            owner_name, entry = deal_lookup[did]
            codes_str = ", ".join(entry["codes"])
            key_fact = entry["facts"][0] if entry["facts"] else ""
            main_lines.append(
                f"**{entry['deal_name']}** ({entry['company']}) — {entry['stage']} — "
                f"{entry['amount']} € — [{codes_str}]"
            )
            if key_fact:
                main_lines.append(f"- {key_fact}")
            main_lines.append("")

    # 4. Tendances — from patterns
    main_lines.append("## Tendances")
    main_lines.append("")
    by_code = patterns.get("by_code", {})
    multi = patterns.get("multi_anomaly_deals", 0)
    a2_late = patterns.get("a2_in_late_stages", 0)
    a3_avg = patterns.get("a3_overdue_days_avg", 0)
    a5a7 = patterns.get("a5_a7_combined", 0)

    # Build trend bullets
    trend_bullets = []
    if by_code.get("A2", 0) > 0:
        a2_total = by_code["A2"]
        if a2_late > 0:
            trend_bullets.append(
                f"• {a2_total} deal(s) sans tâche planifiée (A2) dont {a2_late} en Proposition/Négociation"
            )
        else:
            trend_bullets.append(f"• {a2_total} deal(s) sans tâche planifiée (A2)")
    if by_code.get("A3", 0) > 0:
        a3_total = by_code["A3"]
        bullet = f"• {a3_total} deal(s) A3 — close_dates dépassées"
        if a3_avg > 0:
            bullet += f" (retard moyen {a3_avg} j)"
        trend_bullets.append(bullet)
    if multi > 0:
        trend_bullets.append(f"• {multi} deal(s) avec 2+ anomalies simultanées")
    if a5a7 > 0:
        trend_bullets.append(f"• {a5a7} deal(s) avec A5+A7 combinés (montant manquant en négociation)")
    if by_code.get("A1", 0) > 0:
        trend_bullets.append(f"• {by_code['A1']} deal(s) stagnants (A1)")

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
        n_flagged = stats.get("flagged", len(ow["flagged"]))
        flagged_amt = stats.get("flagged_amount", sum(e["amount"] for e in ow["flagged"]))
        main_lines.append(
            f"- {ow['owner_name']} : {n_flagged} deal(s) signalé(s) ({flagged_amt} €)"
        )
    main_lines.append("")

    # ── DETAIL SECTION ────────────────────────────────────────────────────────
    detail_lines = []

    # 1. Détail par AE
    detail_lines.append("## Détail par AE")
    detail_lines.append("")
    for owner in facts["by_owner"]:
        detail_lines.append(f"### {owner['owner_name']}")
        detail_lines.append("")
        for entry in owner["flagged"]:
            detail_lines.extend(render_deal_entry(entry, owner["owner_name"]))
            detail_lines.append("")

    # 2. Vus, pas inquiétants
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
