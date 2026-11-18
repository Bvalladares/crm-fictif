"""
review/render_raw.py — Render facts.json to Markdown. No LLM.

CLI: python3 -m review.render_raw [--facts out/facts.json] [--out out/review_raw.md]
"""

import argparse
import json
import os


def render(facts):
    lines = []
    as_of = facts["as_of"]
    team = facts["team"]
    totals = facts["totals"]

    # 1. Header
    lines.append(f"# Revue pipeline — {as_of} — {team}")
    lines.append("")

    # 2. Opening
    lines.append(
        f"{totals['open_deals']} deals ouverts pour {totals['open_amount']} € de pipeline. "
        f"{totals['flagged_deals']} deals signalés ({totals['flagged_amount']} €) nécessitent une attention."
    )
    lines.append("")

    # Build a lookup: deal_id -> (owner_name, entry)
    deal_lookup = {}
    for owner in facts["by_owner"]:
        for entry in owner["flagged"]:
            deal_lookup[entry["deal_id"]] = (owner["owner_name"], entry)

    # Build a lookup for excused
    excused_lookup = {e["deal_id"]: e for e in facts.get("excused", [])}

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

    # 3. Priorités
    lines.append("## Priorités")
    lines.append("")
    for did in facts["priorities"]:
        if did in deal_lookup:
            owner_name, entry = deal_lookup[did]
            lines.extend(render_deal_entry(entry, owner_name))
            lines.append("")

    # 4. Par AE
    lines.append("## Par AE")
    lines.append("")
    for owner in facts["by_owner"]:
        lines.append(f"### {owner['owner_name']}")
        lines.append("")
        for entry in owner["flagged"]:
            lines.extend(render_deal_entry(entry, owner["owner_name"]))
            lines.append("")

    # 5. Vus, pas inquiétants
    lines.append("## Vus, pas inquiétants")
    lines.append("")
    for excused in facts.get("excused", []):
        lines.append(
            f"- {excused['deal_name']} ({excused['company']}, {excused['owner_name']}) — {excused['why']}"
        )
    lines.append("")

    return "\n".join(lines)


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
