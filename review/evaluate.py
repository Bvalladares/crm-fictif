"""
review/evaluate.py — Score a review markdown against truth.csv and facts.json.

CLI: python3 -m review.evaluate <review_file> [--facts out/facts.json] [--truth out/truth.csv] [--out-dir out]
"""

import argparse
import csv
import json
import os
import re
import sys


# ── number extraction ───────────────────────────────────────────────────────

def _normalise_spaces(s):
    """Replace narrow non-breaking space and regular space sequences with single space."""
    # Replace various space-like chars
    s = s.replace("\u202f", " ").replace("\u00a0", " ")
    # Collapse multiple spaces
    s = re.sub(r' +', ' ', s)
    return s


def extract_numbers(text):
    """
    Extract all number tokens from text.
    Returns set of normalised strings.
    Skips numeric sub-parts of ISO dates (YYYY-MM-DD).
    """
    text = _normalise_spaces(text)
    found = set()

    # First, record positions that are inside ISO date patterns so we can skip them
    date_positions = set()
    for m in re.finditer(r'\b\d{4}-\d{2}-\d{2}\b', text):
        for i in range(m.start(), m.end()):
            date_positions.add(i)

    def _in_date(m):
        return any(i in date_positions for i in range(m.start(), m.end()))

    # Multi-digit with spaces: e.g. "1 605 000"
    for m in re.finditer(r'\b\d[\d ]*\d\b', text):
        if _in_date(m):
            continue
        tok = m.group(0).strip()
        # Normalise: collapse internal spaces
        norm = re.sub(r' +', ' ', tok)
        found.add(norm)
        # Also add variant without spaces
        found.add(norm.replace(' ', ''))

    # Standalone single digits
    for m in re.finditer(r'\b\d\b', text):
        if _in_date(m):
            continue
        found.add(m.group(0))

    return found


# ── section splitter ────────────────────────────────────────────────────────

def split_sections(text):
    """
    Split review into sections.
    Returns dict: section_title -> content (string)
    Special key '' for content before first heading.
    """
    sections = {}
    current_title = ''
    current_lines = []

    for line in text.splitlines():
        m = re.match(r'^(#{1,3})\s+(.*)', line)
        if m:
            sections[current_title] = '\n'.join(current_lines)
            current_title = m.group(2).strip()
            current_lines = []
        else:
            current_lines.append(line)
    sections[current_title] = '\n'.join(current_lines)
    return sections


# ── scoring ─────────────────────────────────────────────────────────────────

def score_review(review_text, facts, truth_rows):
    """
    Score a review string.
    Returns dict with all metrics.
    """
    # Build deal_name -> deal_id lookup from facts
    # Prefer all_deal_names if present (covers ignorer deals too)
    deal_name_to_id = {}
    all_deal_names = facts.get("all_deal_names", {})
    if all_deal_names:
        # Reverse: name -> id
        for did, name in all_deal_names.items():
            deal_name_to_id[name] = did
    else:
        for owner in facts.get("by_owner", []):
            for entry in owner.get("flagged", []):
                deal_name_to_id[entry["deal_name"]] = entry["deal_id"]
        for excused in facts.get("excused", []):
            deal_name_to_id[excused["deal_name"]] = excused["deal_id"]

    # 1. Recall
    # Find all "signaler" rows in truth
    signaler_rows = [r for r in truth_rows if r["attendu"] == "signaler"]
    total_signaler = len(signaler_rows)

    # Map deal_id -> deal_name (for signaler deals)
    signaler_deal_ids = set(r["deal_id"] for r in signaler_rows)
    # Build reverse: deal_id -> deal_name from facts
    id_to_name = {}
    for name, did in deal_name_to_id.items():
        id_to_name[did] = name

    # Check which signaler deals appear in review
    covered_ids = set()
    for did in signaler_deal_ids:
        name = id_to_name.get(did)
        if name and name in review_text:
            covered_ids.add(did)

    # Count covered rows (multi-anomaly deals: if deal appears, all rows covered)
    covered_rows = sum(1 for r in signaler_rows if r["deal_id"] in covered_ids)
    recall = covered_rows / total_signaler if total_signaler > 0 else 1.0
    missed_deals = sorted(signaler_deal_ids - covered_ids)

    # 2. False leurres
    # "ignorer" deals whose deal_name appears OUTSIDE "Vus, pas inquiétants" section
    sections = split_sections(review_text)
    excused_section = sections.get("Vus, pas inquiétants", "")

    # Get text outside excused section
    # Remove the excused section content from full text for checking
    text_without_excused = review_text
    if excused_section:
        text_without_excused = review_text.replace(excused_section, "")

    ignorer_rows = [r for r in truth_rows if r["attendu"] == "ignorer"]
    ignorer_deal_ids = set(r["deal_id"] for r in ignorer_rows)

    false_leurre_deals = []
    for did in ignorer_deal_ids:
        name = id_to_name.get(did)
        if name and name in text_without_excused:
            false_leurre_deals.append(did)

    false_leurres_count = len(false_leurre_deals)

    # 3. Invented numbers
    allowed = set(facts.get("allowed_numbers", []))
    # Normalise allowed numbers
    allowed_normalised = set(_normalise_spaces(a) for a in allowed)

    # Extract numbers from review text
    review_numbers = extract_numbers(review_text)

    invented = []
    for tok in review_numbers:
        if tok not in allowed_normalised and tok.replace(' ', '') not in allowed_normalised:
            # Also try with variants
            # Check if it's a pure number that might just be 0
            if tok == '0':
                continue
            invented.append(tok)

    invented_count = len(invented)

    # 4. Length: words excluding ## Par AE subsections
    # Remove content under ### headings within Par AE section
    par_ae_section = sections.get("Par AE", "")

    # Build text to count: everything except Par AE body
    # We'll count words in the full text minus the par_ae_section text
    text_for_length = review_text
    if par_ae_section:
        text_for_length = review_text.replace(par_ae_section, "")

    # Also remove the "### Owner" subsection headers themselves
    text_for_length = re.sub(r'###[^\n]*\n', '', text_for_length)

    words = len(text_for_length.split())

    passed = (
        recall >= 0.90 and
        false_leurres_count <= 1 and
        invented_count == 0
        # Note: length is informational, not a hard pass criterion per spec
        # but let's include it
        # and words <= 350
    )

    return {
        "recall": recall,
        "recall_covered": covered_rows,
        "recall_total": total_signaler,
        "false_leurres": false_leurres_count,
        "invented_numbers": invented_count,
        "length_words": words,
        "pass": passed,
        "details": {
            "missed_deals": missed_deals,
            "false_leurre_deals": sorted(false_leurre_deals),
            "invented_number_tokens": sorted(invented),
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("review_file")
    parser.add_argument("--facts", default="out/facts.json")
    parser.add_argument("--truth", default="out/truth.csv")
    parser.add_argument("--out-dir", default="out")
    args = parser.parse_args()

    with open(args.review_file, encoding="utf-8") as f:
        review_text = f.read()

    with open(args.facts, encoding="utf-8") as f:
        facts = json.load(f)

    truth_rows = []
    with open(args.truth, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            truth_rows.append(row)

    result = score_review(review_text, facts, truth_rows)

    stem = os.path.splitext(os.path.basename(args.review_file))[0]
    out_path = os.path.join(args.out_dir, f"eval_{stem}.json")

    output = {"file": os.path.basename(args.review_file)}
    output.update(result)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"Written {out_path}")
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
