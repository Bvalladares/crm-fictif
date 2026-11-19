"""
review/publish.py — Publish a rendered review to Slack.

Usage:
    python3 -m review.publish out/review_hermes_<date>.md [--dry-run] [--force]

Configuration (checked in order):
  1. SLACK_BOT_TOKEN and SLACK_CHANNEL environment variables
  2. ~/.config/crm-fictif/slack.env  (KEY=VALUE lines, outside the repo)

The token is never printed, logged, or included in any error message.
"""

import argparse
import datetime
import json
import os
import re
import sys
import urllib.request
import urllib.error

SEPARATOR = "---DETAIL---"
SLACK_API_URL = "https://slack.com/api/chat.postMessage"
# Conservative limit: Slack text field allows 40 000 chars, but mrkdwn blocks
# cap at 3 000.  We use 3 900 to be safe while keeping threads readable.
_CHUNK_MAX = 3900


# ── configuration ────────────────────────────────────────────────────────────

def _load_config():
    """
    Return (token, channel).  Reads env vars first, then the config file.
    Raises RuntimeError with a helpful message if either value is missing.
    The token is *never* formatted into any log or error string here.
    """
    token = os.environ.get("SLACK_BOT_TOKEN", "").strip() or None
    channel = os.environ.get("SLACK_CHANNEL", "").strip() or None

    if not token or not channel:
        config_path = os.path.expanduser("~/.config/crm-fictif/slack.env")
        if os.path.exists(config_path):
            with open(config_path, encoding="utf-8") as fh:
                for raw in fh:
                    line = raw.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, _, v = line.partition("=")
                    k, v = k.strip(), v.strip()
                    if k == "SLACK_BOT_TOKEN" and not token:
                        token = v or None
                    elif k == "SLACK_CHANNEL" and not channel:
                        channel = v or None

    if not token:
        raise RuntimeError(
            "SLACK_BOT_TOKEN is not set.\n"
            "Set the environment variable or add it to ~/.config/crm-fictif/slack.env"
        )
    if not channel:
        raise RuntimeError(
            "SLACK_CHANNEL is not set.\n"
            "Set the environment variable or add it to ~/.config/crm-fictif/slack.env"
        )
    return token, channel


# ── review splitting ──────────────────────────────────────────────────────────

def split_review(text):
    """
    Split review text at the SINGLE ---DETAIL--- line.
    Returns (main_text, detail_text).
    Raises ValueError if the separator is absent or appears more than once.
    """
    count = text.count(SEPARATOR)
    if count == 0:
        raise ValueError(
            f"Review has no '{SEPARATOR}' separator — cannot split main from detail."
        )
    if count > 1:
        raise ValueError(
            f"Review has {count} occurrences of '{SEPARATOR}' — expected exactly 1."
        )
    main, _, detail = text.partition(SEPARATOR)
    return main.rstrip(), detail.lstrip()


# ── Markdown → Slack mrkdwn ───────────────────────────────────────────────────

def md_to_slack(text):
    """
    Convert GitHub-flavoured Markdown to Slack mrkdwn:
      # / ## / ### headings → *heading*
      **bold**             → *bold*
      _italic_             → _italic_  (unchanged)
      Bullet lists         → unchanged (Slack renders - and • naturally)
    """
    out = []
    for line in text.splitlines():
        m = re.match(r'^(#{1,6})\s+(.*)', line)
        if m:
            out.append(f"*{m.group(2).strip()}*")
            continue
        # **bold** → *bold*  (avoid matching *bold* that's already converted)
        line = re.sub(r'\*\*(.+?)\*\*', r'*\1*', line)
        out.append(line)
    return "\n".join(out)


# ── chunking ──────────────────────────────────────────────────────────────────

def chunk_text(text, max_chars=_CHUNK_MAX, keep_headings_with_next=False):
    """
    Split *text* into a list of strings each ≤ max_chars.
    Prefers splitting on blank lines (paragraph boundaries), then on newlines.

    If keep_headings_with_next is True, any paragraph that is a bare heading
    (a single *Name* bold line, as produced by md_to_slack for ### headings)
    is merged with the following paragraph so it is never left isolated at
    the end of a chunk.
    """
    if len(text) <= max_chars:
        return [text]

    paragraphs = re.split(r'\n{2,}', text)

    if keep_headings_with_next:
        # Merge standalone heading paragraphs (e.g. *Alice Moreau*) with next
        merged = []
        i = 0
        while i < len(paragraphs):
            p = paragraphs[i].strip()
            # Standalone bold: *Name* with no parens, no dashes, no extra content
            is_heading = bool(re.match(r'^\*[^*()\n\u2014\-]+\*\s*$', p))
            if is_heading and i + 1 < len(paragraphs):
                merged.append(paragraphs[i] + "\n\n" + paragraphs[i + 1])
                i += 2
            else:
                merged.append(paragraphs[i])
                i += 1
        paragraphs = merged

    chunks = []
    buf = ""

    for para in paragraphs:
        candidate = (buf + "\n\n" + para).lstrip() if buf else para
        if len(candidate) <= max_chars:
            buf = candidate
        else:
            if buf:
                chunks.append(buf)
            buf = ""
            if len(para) <= max_chars:
                buf = para
            else:
                for line in para.splitlines(keepends=True):
                    if len(buf) + len(line) <= max_chars:
                        buf += line
                    else:
                        if buf:
                            chunks.append(buf.rstrip())
                        buf = line

    if buf.strip():
        chunks.append(buf.rstrip())

    return chunks or [text[:max_chars]]


# ── Slack HTTP layer ──────────────────────────────────────────────────────────

def _slack_post(token, payload):
    """
    POST payload to chat.postMessage.  Returns the parsed JSON dict.
    Raises RuntimeError on HTTP error or Slack API error.
    The token is used only in the Authorization header and is never placed
    in any exception message or log line.
    """
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        SLACK_API_URL,
        data=data,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": "Bearer " + token,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read()
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code} from Slack API") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error reaching Slack API: {exc.reason}") from exc

    result = json.loads(body)
    if not result.get("ok"):
        raise RuntimeError(f"Slack API returned error: {result.get('error', 'unknown')}")
    return result


# ── score summary line ────────────────────────────────────────────────────────

def _build_score_line(eval_path):
    """Return a one-line Slack mrkdwn summary of the evaluation score, or ''."""
    if not os.path.exists(eval_path):
        return ""
    with open(eval_path, encoding="utf-8") as fh:
        ev = json.load(fh)
    passed = ev.get("pass", False)
    recall = ev.get("recall")
    inv = ev.get("invented_numbers")
    length = ev.get("length_words")
    icon = ":white_check_mark:" if passed else ":x:"
    parts = [f"{icon} {'OK' if passed else 'FAIL'}"]
    if recall is not None:
        parts.append(f"rappel {recall:.0%}")
    if inv is not None:
        noun = "chiffre inventé" if inv == 1 else "chiffres inventés"
        parts.append(f"{inv} {noun}")
    if length is not None:
        parts.append(f"{length} mots")
    return "_Score : " + " — ".join(parts) + "_"


# ── main publish logic ────────────────────────────────────────────────────────

def publish(review_file, dry_run=False, force=False, _post_fn=None):
    """
    Publish *review_file* to Slack.

    Parameters
    ----------
    review_file : str   Path to the review Markdown file.
    dry_run     : bool  If True, print what would be sent; no network calls.
    force       : bool  If True, republish even if already published.
    _post_fn    : callable  Injectable for testing.  Signature:
                            (token, payload) -> dict
                  Defaults to the real _slack_post.
    """
    if _post_fn is None:
        _post_fn = _slack_post

    review_file = os.path.abspath(review_file)
    out_dir = os.path.dirname(review_file)
    stem = os.path.splitext(os.path.basename(review_file))[0]
    published_path = os.path.join(out_dir, f"published_{stem}.json")
    eval_path = os.path.join(out_dir, f"eval_{stem}.json")

    # Anti-duplicate guard
    if os.path.exists(published_path) and not force:
        with open(published_path, encoding="utf-8") as fh:
            prev = json.load(fh)
        raise RuntimeError(
            f"Already published on {prev.get('published_at', '?')} "
            f"(ts={prev.get('ts', '?')}, channel={prev.get('channel', '?')}).\n"
            "Use --force to republish."
        )

    # Read and split the review
    with open(review_file, encoding="utf-8") as fh:
        raw = fh.read()
    main_md, detail_md = split_review(raw)

    # Build messages
    main_slack = md_to_slack(main_md)
    detail_slack = md_to_slack(detail_md)
    score_line = _build_score_line(eval_path)

    main_chunks = chunk_text(main_slack)
    detail_chunks = chunk_text(detail_slack, keep_headings_with_next=True)

    if dry_run:
        print("=== DRY RUN — nothing will be sent ===\n")
        print(f"File   : {os.path.basename(review_file)}")
        print(f"Eval   : {os.path.basename(eval_path) if os.path.exists(eval_path) else '(not found)'}")
        print(f"Main   : {len(main_chunks)} chunk(s)")
        print(f"Detail : {len(detail_chunks)} chunk(s) → thread")
        if score_line:
            print(f"Score  : {score_line} → thread")
        print()
        for i, c in enumerate(main_chunks, 1):
            print(f"--- main chunk {i}/{len(main_chunks)} ---")
            print(c)
            print()
        for i, c in enumerate(detail_chunks, 1):
            print(f"--- detail chunk {i}/{len(detail_chunks)} [thread] ---")
            print(c)
            print()
        if score_line:
            print(f"--- score [thread] ---")
            print(score_line)
            print()
        return None

    # Load credentials (after dry-run early return so they're not required for dry-run)
    token, channel = _load_config()

    # Post main message (first chunk creates the thread anchor)
    result = _post_fn(token, {"channel": channel, "text": main_chunks[0]})
    ts = result["ts"]
    print(f"Posted main message: ts={ts}")

    # Remaining main chunks in thread
    for chunk in main_chunks[1:]:
        _post_fn(token, {"channel": channel, "text": chunk, "thread_ts": ts})

    # Detail chunks in thread
    for chunk in detail_chunks:
        _post_fn(token, {"channel": channel, "text": chunk, "thread_ts": ts})

    # Score line in thread
    if score_line:
        _post_fn(token, {"channel": channel, "text": score_line, "thread_ts": ts})

    # Write anti-duplicate record
    published_data = {
        "ts": ts,
        "channel": channel,
        "published_at": datetime.datetime.utcnow().isoformat() + "Z",
        "file": os.path.basename(review_file),
    }
    with open(published_path, "w", encoding="utf-8") as fh:
        json.dump(published_data, fh, ensure_ascii=False, indent=2)

    print(f"Written: {published_path}")
    return published_data


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Publish a CRM review to Slack."
    )
    parser.add_argument("review_file", help="Path to the review Markdown file")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print what would be sent without making any network calls"
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Republish even if already published"
    )
    args = parser.parse_args()

    try:
        publish(args.review_file, dry_run=args.dry_run, force=args.force)
    except (RuntimeError, ValueError, FileNotFoundError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
