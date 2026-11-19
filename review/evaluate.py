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

SEPARATOR = "---DETAIL---"


# ── number extraction ───────────────────────────────────────────────────────

def _normalise_spaces(s):
    """Replace narrow non-breaking space and regular space sequences with single space."""
    s = s.replace("\u202f", " ").replace("\u00a0", " ")
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
        norm = re.sub(r' +', ' ', tok)
        found.add(norm)
        found.add(norm.replace(' ', ''))

    # Standalone single digits
    for m in re.finditer(r'\b\d\b', text):
        if _in_date(m):
            continue
        found.add(m.group(0))

    return found


# ── two-part split ──────────────────────────────────────────────────────────

def split_main_detail(text):
    """
    Split review into main message and detail section.
    Returns (main_text, detail_text).
    If no separator found, the whole text is main and detail is empty.
    """
    sep = SEPARATOR
    idx = text.find(sep)
    if idx == -1:
        return text, ""
    main_text = text[:idx].rstrip()
    detail_text = text[idx + len(sep):].lstrip()
    return main_text, detail_text


# ── scoring ─────────────────────────────────────────────────────────────────

def score_review(review_text, facts, truth_rows, review_file=None):
    """
    Score a review string.
    Returns dict with all metrics.
    """
    # Split into main and detail
    main_text, detail_text = split_main_detail(review_text)
    full_text = review_text  # for recall (search everywhere)

    # Build deal_id -> deal_name lookup from facts
    # (all_deal_names is {deal_id: deal_name})
    id_to_name = {}
    all_deal_names = facts.get("all_deal_names", {})
    if all_deal_names:
        id_to_name = dict(all_deal_names)
    else:
        for owner in facts.get("by_owner", []):
            for entry in owner.get("flagged", []):
                id_to_name[entry["deal_id"]] = entry["deal_name"]
        for excused in facts.get("excused", []):
            id_to_name[excused["deal_id"]] = excused["deal_name"]

    # Also build name -> deal_id for other lookups (may have duplicates — keep first)
    deal_name_to_id = {}
    for did, name in id_to_name.items():
        if name not in deal_name_to_id:
            deal_name_to_id[name] = did

    # 1. Recall — search full file (main + detail)
    signaler_rows = [r for r in truth_rows if r["attendu"] == "signaler"]
    total_signaler = len(signaler_rows)
    signaler_deal_ids = set(r["deal_id"] for r in signaler_rows)

    covered_ids = set()
    for did in signaler_deal_ids:
        name = id_to_name.get(did)
        if name and name in full_text:
            covered_ids.add(did)

    covered_rows = sum(1 for r in signaler_rows if r["deal_id"] in covered_ids)
    recall = covered_rows / total_signaler if total_signaler > 0 else 1.0
    missed_deals = sorted(signaler_deal_ids - covered_ids)

    # 2. False leurres — ignorer deal names found in MAIN MESSAGE ONLY
    ignorer_rows = [r for r in truth_rows if r["attendu"] == "ignorer"]
    ignorer_deal_ids = set(r["deal_id"] for r in ignorer_rows)

    false_leurre_deals = []
    for did in ignorer_deal_ids:
        name = id_to_name.get(did)
        if name and name in main_text:
            false_leurre_deals.append(did)

    false_leurres_count = len(false_leurre_deals)

    # 3. Invented numbers — in full file
    allowed = set(facts.get("allowed_numbers", []))
    allowed_normalised = set(_normalise_spaces(a) for a in allowed)

    review_numbers = extract_numbers(full_text)

    invented = []
    for tok in review_numbers:
        if tok not in allowed_normalised and tok.replace(' ', '') not in allowed_normalised:
            if tok == '0':
                continue
            invented.append(tok)

    invented_count = len(invented)

    # 4. Length — word count of main message only (before ---DETAIL---)
    length_words = len(main_text.split())

    # 5. Priorities present — all 3 priority deal names from facts["priorities"] in main message
    priorities = facts.get("priorities", [])
    missing_priorities = []
    for did in priorities:
        name = id_to_name.get(did)
        if not name or name not in main_text:
            missing_priorities.append(did)
    priorities_present = len(missing_priorities) == 0

    # 6. Patterns cited — at least 2 numeric values from facts["patterns"] in main message
    patterns = facts.get("patterns", {})
    # Collect all numeric values from patterns
    pattern_numbers = set()
    by_code = patterns.get("by_code", {})
    for code, cnt in by_code.items():
        pattern_numbers.add(str(cnt))
    for key in ["multi_anomaly_deals", "a2_in_late_stages", "a3_overdue_days_avg", "a5_a7_combined"]:
        v = patterns.get(key)
        if v is not None:
            pattern_numbers.add(str(v))
    by_owner_pats = patterns.get("by_owner", {})
    for oid, stats in by_owner_pats.items():
        pattern_numbers.add(str(stats.get("flagged", 0)))

    # Count how many pattern numbers appear in main message
    patterns_cited_count = sum(
        1 for n in pattern_numbers
        if n != "0" and re.search(r'\b' + re.escape(n) + r'\b', main_text)
    )
    patterns_cited = patterns_cited_count >= 2

    # 7. Anti-copy — only checked when input is NOT review_raw.md itself
    anticopy_score = None
    anticopy_lines_flagged = []

    # Determine if the file being evaluated is review_raw.md
    is_review_raw = False
    if review_file is not None:
        basename = os.path.basename(str(review_file))
        is_review_raw = (basename == "review_raw.md")

    if not is_review_raw:
        # Load review_raw.md if it exists
        review_raw_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "out", "review_raw.md"
        )
        if os.path.exists(review_raw_path):
            with open(review_raw_path, encoding="utf-8") as f:
                raw_lines = set(line.strip() for line in f if line.strip())

            # Check main message lines (non-empty, non-header)
            main_non_header_lines = [
                line.strip() for line in main_text.splitlines()
                if line.strip() and not line.strip().startswith("#")
            ]
            flagged_lines = [
                line for line in main_non_header_lines
                if line in raw_lines
            ]
            total_main_lines = len(main_non_header_lines)
            if total_main_lines > 0:
                anticopy_score = len(flagged_lines) / total_main_lines
            else:
                anticopy_score = 0.0
            anticopy_lines_flagged = flagged_lines[:10]

    anticopy_pass = anticopy_score is None or anticopy_score <= 0.30

    passed = (
        recall >= 0.90 and
        false_leurres_count <= 1 and
        invented_count == 0 and
        length_words <= 250 and
        priorities_present and
        patterns_cited and
        anticopy_pass
    )

    return {
        "recall": recall,
        "recall_covered": covered_rows,
        "recall_total": total_signaler,
        "false_leurres": false_leurres_count,
        "invented_numbers": invented_count,
        "length_words": length_words,
        "priorities_present": priorities_present,
        "patterns_cited": patterns_cited,
        "anticopy_score": anticopy_score,
        "pass": passed,
        "details": {
            "missed_deals": missed_deals,
            "false_leurre_deals": sorted(false_leurre_deals),
            "invented_number_tokens": sorted(invented),
            "missing_priorities": missing_priorities,
            "anticopy_lines_flagged": anticopy_lines_flagged,
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

    result = score_review(review_text, facts, truth_rows, review_file=args.review_file)

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
